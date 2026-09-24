"""Muestra para la auditoria manual de precision del validador.

    python research/muestra_auditoria.py data/garmentcodedata_0 docs/auditoria

Extrae una muestra estratificada de hallazgos del corpus con semilla fija: 30
bordes cortos, 30 esquinas agudas, 30 desajustes no declarados y 10 del resto de
clases duras (auto-interseccion y exceso de ancho de rollo). Por cada uno
escribe un SVG del panel (o de los dos paneles de la costura) con el elemento
resaltado en rojo, y una fila en `auditoria.csv` con las columnas

    id, clase, valor, archivo, ubicacion, veredicto_humano, nota

`veredicto_humano` y `nota` quedan vacias: las rellena quien audita, con
`defecto` si el hallazgo impide cortar o coser la prenda tal como esta, o
`falso_positivo` si no.
"""
import csv
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "src")
from hilvan import Limites, validar
from hilvan.geometry import segmento

SEMILLA = 2026
CUOTAS = {"borde_degenerado": 30, "esquina_aguda": 30, "desajuste_no_declarado": 30,
          "auto_interseccion": 5, "excede_ancho_rollo": 5}
VALOR = {"borde_degenerado": ("largo_cm", "cm"), "esquina_aguda": ("angulo_grados", "deg"),
         "desajuste_no_declarado": ("desajuste_rel", "rel"),
         "auto_interseccion": ("otro_borde", "borde"), "excede_ancho_rollo": ("ancho_cm", "cm")}
GRIS, ROJO = "#8a8984", "#d62f2f"


def puntos(seg, n=24):
    return [seg.point(t) for t in np.linspace(0, 1, n)]


def svg_paneles(paneles, resaltar, marcas, texto):
    """paneles: [(nombre, panel, dx)]; resaltar: {(nombre, borde)}; marcas: [(nombre, punto)]."""
    trazos, todos = [], []
    for nombre, panel, dx in paneles:
        for i, e in enumerate(panel["edges"]):
            pts = [p + dx for p in puntos(segmento(panel, e))]
            todos += pts
            rojo = (nombre, i) in resaltar
            trazos.append((pts, ROJO if rojo else GRIS, 0.6 if rojo else 0.25))
    xs = [p.real for p in todos]
    ys = [p.imag for p in todos]
    x0, x1, y0, y1 = min(xs) - 5, max(xs) + 5, min(ys) - 5, max(ys) + 5
    # el panel esta en cm con y hacia arriba; el SVG tiene y hacia abajo
    f = lambda p: f"{p.real - x0:.3f},{y1 - p.imag:.3f}"
    cuerpo = [f'<polyline points="{" ".join(f(p) for p in pts)}" fill="none" '
              f'stroke="{c}" stroke-width="{w}"/>' for pts, c, w in trazos]
    desplaz = {n: dx for n, _, dx in paneles}
    for nombre, p in marcas:
        q = p + desplaz[nombre]
        cuerpo.append(f'<circle cx="{q.real - x0:.3f}" cy="{y1 - q.imag:.3f}" r="2.5" '
                      f'fill="none" stroke="{ROJO}" stroke-width="0.4"/>')
    ancho, alto = x1 - x0, y1 - y0
    cuerpo.append(f'<text x="1" y="{alto - 1:.1f}" font-size="3" font-family="sans-serif">'
                  f'{texto}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho:.2f} {alto:.2f}" '
            f'width="{ancho * 4:.0f}" height="{alto * 4:.0f}">'
            f'<rect width="100%" height="100%" fill="white"/>{"".join(cuerpo)}</svg>')


def dibujar(pat, h):
    panels = pat["panels"]
    if h.codigo == "desajuste_no_declarado":
        lados = [s for s in pat["stitches"][h.costura] if isinstance(s, dict)]
        a, b = lados[0]["panel"], lados[1]["panel"]
        ancho_a = max(v[0] for v in panels[a]["vertices"]) - min(v[0] for v in panels[b]["vertices"])
        paneles = [(a, panels[a], 0)] + ([(b, panels[b], ancho_a + 10)] if b != a else [])
        resaltar = {(l["panel"], l["edge"]) for l in lados}
        texto = (f"{a}.{lados[0]['edge']} = {h.medido['largo_a_cm']} cm, "
                 f"{b}.{lados[1]['edge']} = {h.medido['largo_b_cm']} cm")
        return svg_paneles(paneles, resaltar, [], texto)
    panel = panels[h.panel]
    resaltar, marcas = set(), []
    if h.codigo == "borde_degenerado":
        resaltar = {(h.panel, h.borde)}
        marcas = [(h.panel, segmento(panel, panel["edges"][h.borde]).point(0.5))]
    elif h.codigo == "esquina_aguda":
        v = h.medido["vertice"]
        resaltar = {(h.panel, i) for i, e in enumerate(panel["edges"]) if v in e["endpoints"]}
        marcas = [(h.panel, complex(*panel["vertices"][v]))]
    elif h.codigo == "auto_interseccion":
        resaltar = {(h.panel, h.borde), (h.panel, h.medido["otro_borde"])}
        marcas = [(h.panel, complex(*h.medido["punto"]))]
    return svg_paneles([(h.panel, panel, 0)], resaltar, marcas, f"{h.panel}: {h.mensaje}")


def ubicacion(h):
    if h.costura is not None:
        return f"costura {h.costura}"
    return f"{h.panel}" + (f".{h.borde}" if h.borde is not None else "")


if __name__ == "__main__":
    origen, destino = Path(sys.argv[1]), Path(sys.argv[2])
    destino.mkdir(parents=True, exist_ok=True)
    candidatos = {c: [] for c in CUOTAS}
    for r in sorted(origen.glob("*specification.json")):
        spec = json.loads(r.read_text(encoding="utf-8"))
        for k, h in enumerate(validar(spec, Limites())):
            if h.codigo in candidatos:
                candidatos[h.codigo].append((r, k))

    rng = random.Random(SEMILLA)
    filas = []
    for clase, cuota in CUOTAS.items():
        for r, k in sorted(rng.sample(candidatos[clase], min(cuota, len(candidatos[clase])))):
            spec = json.loads(r.read_text(encoding="utf-8"))
            h = validar(spec, Limites())[k]
            ident = f"{clase[:4]}_{len(filas):03d}"
            (destino / f"{ident}.svg").write_text(dibujar(spec.get("pattern", spec), h),
                                                  encoding="utf-8")
            campo, unidad = VALOR[clase]
            filas.append({"id": ident, "clase": clase,
                          "valor": f"{h.medido[campo]} {unidad}", "archivo": r.name,
                          "ubicacion": ubicacion(h), "veredicto_humano": "", "nota": ""})

    with open(destino / "auditoria.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    print(f"{len(filas)} hallazgos -> {destino}")
    print({c: sum(f['clase'] == c for f in filas) for c in CUOTAS})
