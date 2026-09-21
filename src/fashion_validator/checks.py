"""Los chequeos de los niveles 0 y 1.

Nivel 0 mira cada panel por separado: que el contorno cierre, que todo sea
cortable y cosible, que no se cruce consigo mismo y que quepa en el rollo.

Nivel 1 mira el grafo de costuras entre paneles: que las referencias existan,
que las longitudes calcen o el desajuste este declarado, que ningun borde se
cosa dos veces y que la prenda sea una sola pieza.
"""

from __future__ import annotations

import math

import numpy as np

from .geometry import (a_complejo, segmento, longitud, radio_curvatura_min,
                       tangente_saliente, cruce_real)
from .model import Hallazgo, Limites

__all__ = ["nivel0", "nivel1"]


def _es_pico_de_pinza(edges: list[dict], panel: dict, i0: int, i1: int,
                      lim: Limites) -> bool:
    """Un pico de pinza: dos bordes rectos de longitud practicamente igual.

    Es la firma geometrica de una pinza, que es agudo a proposito. Sin esta
    excepcion el validador marca como defecto toda falda y todo pantalon.
    """
    if edges[i0].get("curvature") or edges[i1].get("curvature"):
        return False
    L0, L1 = longitud(panel, i0), longitud(panel, i1)
    mayor = max(L0, L1)
    if mayor < 1e-9:
        return False
    return abs(L0 - L1) / mayor <= lim.tol_simetria_pinza


def nivel0(pattern: dict, lim: Limites) -> list[Hallazgo]:
    """Validez geometrica de cada panel, por separado."""
    out: list[Hallazgo] = []

    for nombre, panel in pattern["panels"].items():
        verts, edges = panel["vertices"], panel["edges"]
        n_v = len(verts)

        # --- las referencias de vertices existen
        ref_rota = False
        for i, e in enumerate(edges):
            for vi in e["endpoints"]:
                if not (0 <= vi < n_v):
                    out.append(Hallazgo(0, "vertice_inexistente", "error",
                                        f"el borde apunta al vertice {vi}, que no existe "
                                        f"(el panel tiene {n_v})",
                                        panel=nombre, borde=i))
                    ref_rota = True
        if ref_rota:
            continue

        # --- el contorno es un ciclo cerrado
        grado: dict[int, int] = {}
        for e in edges:
            for vi in e["endpoints"]:
                grado[vi] = grado.get(vi, 0) + 1
        malos = [v for v, g in grado.items() if g != 2]
        if malos:
            out.append(Hallazgo(0, "contorno_abierto", "error",
                                f"el contorno no cierra: los vertices {malos[:6]} no tienen "
                                f"exactamente dos bordes",
                                panel=nombre, medido={"vertices_malos": malos[:6]}))
        huerfanos = [i for i in range(n_v) if i not in grado]
        if huerfanos:
            out.append(Hallazgo(0, "vertice_huerfano", "aviso",
                                f"los vertices {huerfanos[:6]} no los usa ningun borde",
                                panel=nombre, medido={"vertices": huerfanos[:6]}))

        segs = [segmento(panel, e) for e in edges]

        # --- bordes cortables y curvatura cosible
        for i, s in enumerate(segs):
            L = float(s.length())
            if L < lim.largo_min_borde:
                out.append(Hallazgo(0, "borde_degenerado", "error",
                                    f"mide {L:.2f} cm, por debajo del minimo de "
                                    f"{lim.largo_min_borde} cm",
                                    panel=nombre, borde=i, medido={"largo_cm": round(L, 3)}))
            r = radio_curvatura_min(s)
            if r < lim.radio_min_curva:
                out.append(Hallazgo(0, "curvatura_excesiva", "error",
                                    f"radio de curvatura minimo {r:.2f} cm, por debajo de "
                                    f"{lim.radio_min_curva} cm",
                                    panel=nombre, borde=i, medido={"radio_cm": round(r, 3)}))

        # --- esquinas cosibles, reconociendo las pinzas
        incidencias: dict[int, list[tuple[int, bool]]] = {}
        for i, e in enumerate(edges):
            a, b = e["endpoints"]
            incidencias.setdefault(a, []).append((i, True))
            incidencias.setdefault(b, []).append((i, False))

        for vi, inc in incidencias.items():
            if len(inc) != 2:
                continue
            (i0, ini0), (i1, ini1) = inc
            u0 = tangente_saliente(segs[i0], ini0)
            u1 = tangente_saliente(segs[i1], ini1)
            dot = max(-1.0, min(1.0, u0.real * u1.real + u0.imag * u1.imag))
            ang = math.degrees(math.acos(dot))
            if ang >= lim.angulo_min_esquina:
                continue
            if lim.permitir_pinzas and _es_pico_de_pinza(edges, panel, i0, i1, lim):
                out.append(Hallazgo(0, "pico_de_pinza", "info",
                                    f"el vertice {vi} forma {ang:.1f} grados entre dos bordes "
                                    f"rectos de igual longitud: se interpreta como pinza",
                                    panel=nombre, borde=i0,
                                    medido={"vertice": vi, "angulo_grados": round(ang, 2)}))
                continue
            out.append(Hallazgo(0, "esquina_aguda", "error",
                                f"el vertice {vi} forma {ang:.1f} grados, por debajo de "
                                f"{lim.angulo_min_esquina}",
                                panel=nombre, borde=i0,
                                medido={"vertice": vi, "angulo_grados": round(ang, 2)}))

        # --- auto-interseccion entre bordes
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                comparte = set(edges[i]["endpoints"]) & set(edges[j]["endpoints"])
                extremos = [a_complejo(verts[vi]) for vi in comparte]
                p = cruce_real(segs[i], segs[j], extremos, lim)
                if p is not None:
                    out.append(Hallazgo(0, "auto_interseccion", "error",
                                        f"el borde {i} cruza al borde {j} fuera de un vertice",
                                        panel=nombre, borde=i,
                                        medido={"otro_borde": j,
                                                "punto": [round(p.real, 2), round(p.imag, 2)]}))

        # --- cabe en el ancho del rollo
        pts = np.array([[p.real, p.imag]
                        for s in segs
                        for p in (s.point(t) for t in np.linspace(0, 1, 12))])
        if len(pts):
            ancho = float(pts[:, 0].max() - pts[:, 0].min())
            alto = float(pts[:, 1].max() - pts[:, 1].min())
            if min(ancho, alto) > lim.ancho_rollo:
                out.append(Hallazgo(0, "excede_ancho_rollo", "error",
                                    f"el panel mide {ancho:.0f} x {alto:.0f} cm y no cabe en un "
                                    f"rollo de {lim.ancho_rollo} cm ni girandolo",
                                    panel=nombre,
                                    medido={"ancho_cm": round(ancho, 1),
                                            "alto_cm": round(alto, 1)}))
    return out


def nivel1(pattern: dict, lim: Limites) -> list[Hallazgo]:
    """Coherencia del grafo de costuras entre paneles."""
    out: list[Hallazgo] = []
    panels = pattern["panels"]
    stitches = pattern.get("stitches", [])

    uso: dict[tuple[str, int], list[int]] = {}

    for si, st in enumerate(stitches):
        lados = [s for s in st if isinstance(s, dict)]
        if len(lados) != 2:
            out.append(Hallazgo(1, "costura_no_binaria", "error",
                                f"une {len(lados)} bordes; una costura une exactamente dos",
                                costura=si, medido={"lados": len(lados)}))
            continue

        # --- las referencias existen
        ok = True
        for lado in lados:
            p = panels.get(lado["panel"])
            if p is None:
                out.append(Hallazgo(1, "panel_inexistente", "error",
                                    f"apunta al panel '{lado['panel']}', que no esta en el patron",
                                    costura=si))
                ok = False
            elif not (0 <= lado["edge"] < len(p["edges"])):
                out.append(Hallazgo(1, "borde_inexistente", "error",
                                    f"apunta al borde {lado['edge']} de '{lado['panel']}', "
                                    f"que solo tiene {len(p['edges'])}",
                                    costura=si))
                ok = False
        if not ok:
            continue

        for lado in lados:
            uso.setdefault((lado["panel"], lado["edge"]), []).append(si)

        # --- longitudes: calzan, o el desajuste esta declarado
        L = [longitud(panels[l["panel"]], l["edge"]) for l in lados]
        mayor, menor = max(L), min(L)
        if mayor < 1e-6:
            out.append(Hallazgo(1, "costura_nula", "error",
                                "los dos bordes tienen longitud cero", costura=si))
            continue

        rel = abs(L[0] - L[1]) / mayor
        declaracion = next((l["ease"] for l in lados if isinstance(l.get("ease"), dict)), None)

        if declaracion is None:
            if rel > lim.umbral_fruncido:
                # tan grande que casi seguro es deliberado, pero nadie lo declaro
                out.append(Hallazgo(
                    1, "fruncido_no_declarado", "aviso",
                    f"los bordes miden {L[0]:.2f} y {L[1]:.2f} cm ({rel * 100:.1f}% de "
                    f"diferencia): parece un fruncido intencional, pero el patron no lo "
                    f"declara y no hay forma de distinguirlo de un defecto",
                    costura=si,
                    medido={"largo_a_cm": round(L[0], 2), "largo_b_cm": round(L[1], 2),
                            "desajuste_rel": round(rel, 4),
                            "ratio": round(mayor / menor, 3) if menor > 1e-9 else None}))
            elif rel > lim.tol_costura:
                # demasiado grande para ser redondeo, demasiado chico para ser fruncido
                out.append(Hallazgo(
                    1, "desajuste_no_declarado", "error",
                    f"los bordes miden {L[0]:.2f} y {L[1]:.2f} cm ({rel * 100:.1f}% de "
                    f"diferencia) y no hay declaracion de fruncido o embebido",
                    costura=si,
                    medido={"largo_a_cm": round(L[0], 2), "largo_b_cm": round(L[1], 2),
                            "desajuste_rel": round(rel, 4)}))
        else:
            ratio_decl = float(declaracion.get("ratio", 1.0))
            tol = float(declaracion.get("tol", lim.tol_ease_default))
            ratio_real = mayor / menor if menor > 1e-9 else math.inf
            if abs(ratio_real - ratio_decl) > tol * max(1.0, ratio_decl):
                out.append(Hallazgo(
                    1, "ease_incongruente", "error",
                    f"declara un {declaracion.get('type', 'ease')} de {ratio_decl:.2f} pero la "
                    f"geometria da {ratio_real:.2f}",
                    costura=si,
                    medido={"ratio_declarado": round(ratio_decl, 3),
                            "ratio_real": round(ratio_real, 3)}))

    # --- ningun borde cosido dos veces
    for (pn, ei), sis in uso.items():
        if len(sis) > 1:
            out.append(Hallazgo(1, "borde_multicosido", "error",
                                f"este borde aparece en las costuras {sis}; un borde se cose "
                                f"una sola vez",
                                panel=pn, borde=ei, medido={"costuras": sis}))

    # --- paneles sin ninguna costura
    cosidos = {p for (p, _) in uso}
    for nombre in panels:
        if nombre not in cosidos:
            out.append(Hallazgo(1, "panel_suelto", "error",
                                "el panel no esta cosido a nada", panel=nombre))

    # --- la prenda es una sola pieza conectada
    padre: dict[str, str] = {n: n for n in panels}

    def raiz(x: str) -> str:
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    for st in stitches:
        lados = [s for s in st if isinstance(s, dict)]
        if len(lados) == 2 and all(l["panel"] in padre for l in lados):
            ra, rb = raiz(lados[0]["panel"]), raiz(lados[1]["panel"])
            if ra != rb:
                padre[ra] = rb

    grupos: dict[str, list[str]] = {}
    for n in panels:
        grupos.setdefault(raiz(n), []).append(n)
    if len(grupos) > 1:
        tam = sorted((len(v) for v in grupos.values()), reverse=True)
        out.append(Hallazgo(1, "prenda_desconectada", "aviso",
                            f"los paneles forman {len(grupos)} grupos separados (tamanos {tam}); "
                            f"puede ser un conjunto de varias prendas o un error de costura",
                            medido={"grupos": len(grupos), "tamanos": tam}))

    # --- bordes libres, para revision humana
    libres = sum(1 for n, p in panels.items()
                 for i in range(len(p["edges"])) if (n, i) not in uso)
    total = sum(len(p["edges"]) for p in panels.values())
    if libres:
        out.append(Hallazgo(1, "bordes_libres", "info",
                            f"{libres} de {total} bordes no estan cosidos; deberian ser "
                            f"dobladillos, aberturas o vistas",
                            medido={"libres": libres, "total": total}))
    return out
