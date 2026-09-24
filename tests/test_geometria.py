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
