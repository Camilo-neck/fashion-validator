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
           "radio_curvatura_min", "tangente_saliente", "linealizar", "cruce_real"]


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


def cruce_real(s1, s2, extremos: list[complex], lim: Limites):
    """Punto donde s1 cruza a s2 lejos de los vertices dados, o None.

    `extremos` son los vertices que los dos bordes comparten: un cruce ahi es
    como se unen, no un defecto.
    """
    for a in linealizar(s1, lim.muestras_linealizacion):
        for b in linealizar(s2, lim.muestras_linealizacion):
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
