"""Geometria de paneles y bordes, sin dependencia de pygarment.

Un borde del formato GarmentCode es un par de vertices mas una curvatura
opcional. Este modulo lo convierte en un segmento de svgpathtools y responde
las preguntas que necesitan los chequeos: cuanto mide, como de cerrada es su
curvatura y donde cruza a otro borde.
"""

from __future__ import annotations

import math

import numpy as np
from svgpathtools import Line, QuadraticBezier, CubicBezier, Arc

from .model import Limites

__all__ = ["a_complejo", "rel_a_abs_2d", "segmento", "longitud",
           "radio_curvatura_min", "tangente_saliente", "angulo_entre",
           "ciclos", "angulos_interiores", "angulo_interior",
           "linealizar", "caja", "solapan", "cruce_real"]


def a_complejo(p) -> complex:
    return complex(float(p[0]), float(p[1]))


def rel_a_abs_2d(inicio, fin, punto_rel):
    """Pasa un punto de control del marco local del borde al marco del panel.

    Equivale a `pygarment.pattern.utils.rel_to_abs_2d`, reimplementado aqui
    para que el validador no dependa de GarmentCode.
    """
    inicio, fin = np.asarray(inicio, dtype=float), np.asarray(fin, dtype=float)
    borde = fin - inicio
    perpendicular = np.array([-borde[1], borde[0]])
    return inicio + punto_rel[0] * borde + punto_rel[1] * perpendicular


def segmento(panel: dict, edge: dict):
    """Segmento svgpathtools de un borde, respetando su curvatura."""
    v = panel["vertices"]
    a, b = edge["endpoints"]
    inicio, fin = a_complejo(v[a]), a_complejo(v[b])
    curv = edge.get("curvature")

    if not curv:
        return Line(inicio, fin)

    tipo = curv["type"] if isinstance(curv, dict) else "cubic"
    params = curv["params"] if isinstance(curv, dict) else curv

    if tipo == "circle":
        # mismo convenio que SVG: [radio, large_arc, sweep]
        rad, large_arc, sweep = params[0], bool(params[1]), bool(params[2])
        cuerda = abs(fin - inicio)
        # un radio menor que media cuerda no define un arco: se sube al minimo
        rad = max(float(rad), cuerda / 2 + 1e-9)
        return Arc(inicio, complex(rad, rad), 0.0, large_arc, sweep, fin)

    va, vb = np.asarray(v[a], dtype=float), np.asarray(v[b], dtype=float)

    def control(rel):
        p = rel_a_abs_2d(va, vb, np.asarray(rel, dtype=float))
        return complex(p[0], p[1])

    if tipo == "cubic":
        return CubicBezier(inicio, control(params[0]), control(params[1]), fin)
    if tipo in ("quadratic", "quad"):
        return QuadraticBezier(inicio, control(params[0]), fin)
    return Line(inicio, fin)


def longitud(panel: dict, idx: int) -> float:
    """Longitud real del borde `idx`, siguiendo su curvatura."""
    return float(segmento(panel, panel["edges"][idx]).length())


def radio_curvatura_min(seg, muestras: int = 24) -> float:
    """Radio de curvatura minimo del segmento. Infinito para una recta."""
    if isinstance(seg, Line):
        return math.inf
    if isinstance(seg, Arc):
        return float(min(abs(seg.radius.real), abs(seg.radius.imag)))
    if seg.length() < 1e-9:
        return math.inf

    peor = math.inf
    ts = np.linspace(0.02, 0.98, muestras)
    for t0, t1 in zip(ts[:-1], ts[1:]):
        try:
            u0, u1 = seg.unit_tangent(t0), seg.unit_tangent(t1)
        except Exception:
            continue
        # angulo girado entre dos tangentes / arco recorrido = curvatura
        dot = max(-1.0, min(1.0, u0.real * u1.real + u0.imag * u1.imag))
        dtheta = math.acos(dot)
        ds = abs(seg.point(t1) - seg.point(t0))
        if ds < 1e-9 or dtheta < 1e-9:
            continue
        peor = min(peor, ds / dtheta)
    return peor


def tangente_saliente(seg, en_inicio: bool) -> complex:
    """Tangente unitaria apuntando hacia afuera del vertice."""
    try:
        u = seg.unit_tangent(0.0 if en_inicio else 1.0)
    except Exception:
        d = seg.end - seg.start
        u = d / abs(d) if abs(d) > 1e-12 else complex(1, 0)
    return u if en_inicio else -u


def angulo_entre(u0: complex, u1: complex) -> float:
    """Angulo en grados entre dos tangentes unitarias."""
    dot = max(-1.0, min(1.0, u0.real * u1.real + u0.imag * u1.imag))
    return math.degrees(math.acos(dot))


def ciclos(panel: dict) -> list[list[tuple[int, bool]]]:
    """Los ciclos del contorno, como listas de (borde, recorrido_hacia_adelante).

    Supone que cada vertice tiene exactamente dos bordes; si no, el contorno
    esta abierto y devuelve []. Un contorno sano es un solo ciclo con todos
    los bordes; mas de uno es un panel con agujeros o dos piezas en una.
    """
    por_vertice: dict[int, list[int]] = {}
    for i, e in enumerate(panel["edges"]):
        for v in e["endpoints"]:
            por_vertice.setdefault(v, []).append(i)
    if any(len(inc) != 2 for inc in por_vertice.values()):
        return []

    pendientes = set(range(len(panel["edges"])))
    out = []
    while pendientes:
        inicio = min(pendientes)
        ciclo, borde, adelante = [], inicio, True
        while borde in pendientes:
            pendientes.discard(borde)
            ciclo.append((borde, adelante))
            a, b = panel["edges"][borde]["endpoints"]
            llegada = b if adelante else a
            inc = por_vertice[llegada]
            borde = inc[1] if inc[0] == borde else inc[0]
            adelante = panel["edges"][borde]["endpoints"][0] == llegada
        out.append(ciclo)
    return out


def _area_con_signo(segs: list, ciclo: list[tuple[int, bool]]) -> float:
    """Area del ciclo muestreando cada segmento en el sentido del recorrido."""
    pts = []
    for i, adelante in ciclo:
        ts = np.linspace(0.0, 1.0, 9)[:-1] if adelante else np.linspace(1.0, 0.0, 9)[:-1]
        pts += [segs[i].point(t) for t in ts]
    z = np.array(pts)
    return 0.5 * float(np.sum(z.real * np.roll(z.imag, -1) - np.roll(z.real, -1) * z.imag))


def angulos_interiores(panel: dict, segs: list) -> dict[int, float]:
    """Angulo interior de cada vertice, en grados en [0, 360).

    Menor de 180 es una esquina convexa (una punta); mayor, una concava (una
    muesca o el fondo de una pinza). El interior se decide con la orientacion
    del ciclo: el signo de su area. Cada ciclo se orienta por separado, asi
    que en un panel con varios ciclos los angulos son los de la region que
    encierra cada uno. Vacio si el contorno no cierra.
    """
    out: dict[int, float] = {}
    for ciclo in ciclos(panel):
        antihorario = _area_con_signo(segs, ciclo) >= 0
        for k, (i_ent, adelante_ent) in enumerate(ciclo):
            i_sal, adelante_sal = ciclo[(k + 1) % len(ciclo)]
            e_ent = panel["edges"][i_ent]["endpoints"]
            v = e_ent[1] if adelante_ent else e_ent[0]
            # tangentes que salen del vertice por cada uno de sus dos bordes
            t_ent = tangente_saliente(segs[i_ent], en_inicio=not adelante_ent)
            t_sal = tangente_saliente(segs[i_sal], en_inicio=adelante_sal)
            giro = math.degrees(math.atan2(t_ent.imag, t_ent.real)
                                - math.atan2(t_sal.imag, t_sal.real))
            # recorriendo en sentido antihorario el interior queda a la
            # izquierda: se barre de la salida a la llegada en ese sentido
            out[v] = (giro if antihorario else -giro) % 360.0
    return out


def angulo_interior(panel: dict, segs: list, v: int) -> float | None:
    """Angulo interior con signo del vertice `v`, o None si el contorno no cierra."""
    return angulos_interiores(panel, segs).get(v)


def linealizar(seg, n: int) -> list[Line]:
    """Aproxima un segmento por tramos rectos.

    La interseccion exacta de arcos en svgpathtools no es fiable (su propio
    issue 121), asi que los cruces se calculan sobre esta aproximacion, igual
    que hace GarmentCode, pero con mas resolucion.
    """
    if isinstance(seg, Line):
        return [seg]
    pts = [seg.point(t) for t in np.linspace(0.0, 1.0, n)]
    return [Line(a, b) for a, b in zip(pts[:-1], pts[1:]) if abs(b - a) > 1e-12]


def caja(poli: list[Line]) -> tuple[float, float, float, float]:
    """Caja envolvente de una polilinea: (xmin, xmax, ymin, ymax)."""
    xs = [c.real for l in poli for c in (l.start, l.end)]
    ys = [c.imag for l in poli for c in (l.start, l.end)]
    return min(xs), max(xs), min(ys), max(ys)


def solapan(c1, c2, holgura: float = 0.0) -> bool:
    """Si dos cajas no se tocan, lo que hay dentro tampoco puede cruzarse."""
    return not (c1[1] < c2[0] - holgura or c2[1] < c1[0] - holgura
                or c1[3] < c2[2] - holgura or c2[3] < c1[2] - holgura)


def cruce_real(poli1: list[Line], poli2: list[Line], extremos: list[complex],
               lim: Limites):
    """Punto donde dos polilineas se cruzan lejos de los vertices dados, o None.

    Recibe las polilineas ya calculadas, no los segmentos: linealizar es caro y
    cada borde se compara contra todos los demas del panel.

    `extremos` son los vertices que los dos bordes comparten: un cruce ahi es
    como se unen, no un defecto.
    """
    cajas2 = [caja([b]) for b in poli2]
    for a in poli1:
        ca = caja([a])
        for b, cb in zip(poli2, cajas2):
            if not solapan(ca, cb, lim.eps_vertice):
                continue
            try:
                cruces = a.intersect(b)
            except Exception:
                continue
            for t, _ in cruces:
                p = a.point(t)
                if any(abs(p - v) < lim.eps_vertice for v in extremos):
                    continue
                return p
    return None
