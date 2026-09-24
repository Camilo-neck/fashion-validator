"""Geometria del contorno: lo que los chequeos dan por hecho."""

import pytest

from hilvan.geometry import angulo_interior, ciclos, segmento

CUADRADO = [[0, 0], [10, 0], [10, 10], [0, 10]]


def _panel(vertices):
    n = len(vertices)
    return {"vertices": vertices,
            "edges": [{"endpoints": [i, (i + 1) % n]} for i in range(n)]}


@pytest.mark.parametrize("vertices", [CUADRADO, list(reversed(CUADRADO))])
def test_angulo_interior_de_un_cuadrado(vertices):
    panel = _panel(vertices)
    segs = [segmento(panel, e) for e in panel["edges"]]
    for v in range(4):
        assert angulo_interior(panel, segs, v) == pytest.approx(90.0)


def test_angulo_interior_de_una_esquina_concava():
    """Una L: el vertice del codo interior mide 270 grados."""
    panel = _panel([[0, 0], [20, 0], [20, 10], [10, 10], [10, 20], [0, 20]])
    segs = [segmento(panel, e) for e in panel["edges"]]
    assert angulo_interior(panel, segs, 3) == pytest.approx(270.0)
    assert angulo_interior(panel, segs, 0) == pytest.approx(90.0)


def test_ciclos_de_un_contorno_sano():
    assert len(ciclos(_panel(CUADRADO))) == 1


def _cuadratica(h):
    """Cuadratica de (0,0) a (10,0) con el control relativo en [0.5, h]."""
    return {"vertices": [[0, 0], [10, 0], [10, -10], [0, -10]],
            "edges": [{"endpoints": [0, 1],
                       "curvature": {"type": "quadratic", "params": [[0.5, h]]}},
                      {"endpoints": [1, 2]}, {"endpoints": [2, 3]}, {"endpoints": [3, 0]}]}


@pytest.mark.parametrize("h, radio", [(10, 0.25), (20, 0.125)])
def test_radio_de_curvatura_analitico(h, radio):
    """El pico de la cuadratica: k = |B' x B''| / |B'|^3 = 4000 / 1000 para h = 10."""
    from hilvan.geometry import radio_curvatura_min

    panel = _cuadratica(h)
    seg = segmento(panel, panel["edges"][0])
    assert radio_curvatura_min(seg) == pytest.approx(radio, abs=0.01)


def test_curva_cerrada_se_reporta():
    """Con el estimador viejo daba 0.300 cm y no llegaba al umbral de 0.3."""
    from hilvan import validar

    spec = {"pattern": {"panels": {"p": _cuadratica(10)}, "stitches": []}}
    curvas = [h for h in validar(spec) if h.codigo == "curvatura_excesiva"]
    assert len(curvas) == 1
    assert curvas[0].severidad == "error"
    assert curvas[0].medido["radio_cm"] == pytest.approx(0.25, abs=0.01)


def _borde(curvatura):
    panel = {"vertices": [[0, 0], [10, 0]],
             "edges": [{"endpoints": [0, 1], "curvature": curvatura}]}
    return segmento(panel, panel["edges"][0])


def test_formato_antiguo_de_cuadratica():
    """[x, y] es el control de una cuadratica, como lo lee pygarment."""
    antiguo = _borde([0.5, 0.2])
    nuevo = _borde({"type": "quadratic", "params": [[0.5, 0.2]]})
    assert antiguo.point(0.5) == pytest.approx(nuevo.point(0.5))
    assert antiguo.point(0.5) == pytest.approx(complex(5, 1))


def test_formato_antiguo_de_cubica():
    antiguo = _borde([[0.3, 0.2], [0.7, -0.2]])
    nuevo = _borde({"type": "cubic", "params": [[0.3, 0.2], [0.7, -0.2]]})
    assert antiguo.point(0.25) == pytest.approx(nuevo.point(0.25))


# Arco de (0, 0) a (10, 0) con radio 10, en las cuatro combinaciones de
# large_arc y sweep. Referencia: pygarment/meshgen/boxmeshgen.py construye
# Arc(start, r + 1j*r, rotation=0, large_arc=large_arc, sweep=right, end) en el
# marco del panel. (core._edge_as_curve invierte sweep y el control porque
# dibuja en el marco SVG, con la y hacia abajo.) Valores analiticos: centros en
# (5, +-8.66), arco corto de 60 grados y largo de 300.
ARCOS = {
    (0, 1): (10.471976, complex(5, -1.339746)),
    (0, 0): (10.471976, complex(5, 1.339746)),
    (1, 1): (52.359878, complex(5, -18.660254)),
    (1, 0): (52.359878, complex(5, 18.660254)),
}


@pytest.mark.parametrize("large_arc, sweep", list(ARCOS))
def test_arco_como_pygarment(large_arc, sweep):
    largo, medio = ARCOS[(large_arc, sweep)]
    seg = _borde({"type": "circle", "params": [10, large_arc, sweep]})
    assert seg.length() == pytest.approx(largo, abs=1e-4)
    assert seg.point(0.5).real == pytest.approx(medio.real, abs=1e-4)
    assert seg.point(0.5).imag == pytest.approx(medio.imag, abs=1e-4)


def test_cuadratica_punto_medio_y_largo():
    """B(0.5) = (P0 + 2 P1 + P2) / 4 con el control en (5, 10)."""
    seg = _borde({"type": "quadratic", "params": [[0.5, 1.0]]})
    assert seg.point(0.5) == pytest.approx(complex(5, 5))
    assert seg.length() == pytest.approx(14.789, abs=1e-3)
