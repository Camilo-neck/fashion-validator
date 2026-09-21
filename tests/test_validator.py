"""Prueba de discriminacion: el validador debe aceptar lo sano y marcar lo roto.

Las dos direcciones importan por igual. Un validador que marca todo no sirve
para nada, que es como empezo este: rechazaba el 100% de los patrones porque
leia las pinzas como defecto.
"""

import copy
import json
from pathlib import Path

import pytest

from fashion_validator import validar, longitud

FIXTURE = Path(__file__).parent / "fixtures" / "tshirt.json"


@pytest.fixture
def sano():
    """Una camiseta generada por GarmentCode, sin defectos."""
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def errores(spec) -> set[str]:
    return {h.codigo for h in validar(spec) if h.severidad == "error"}


# --- el punto de partida: lo sano pasa limpio -------------------------------

def test_patron_sano_no_tiene_errores(sano):
    assert errores(sano) == set()


def test_patron_sano_reporta_bordes_libres(sano):
    """Los dobladillos y aberturas se informan, no se penalizan."""
    codigos = {h.codigo: h for h in validar(sano)}
    assert "bordes_libres" in codigos
    assert codigos["bordes_libres"].severidad == "info"


# --- referencias rotas ------------------------------------------------------

def test_panel_inexistente(sano):
    sano["pattern"]["stitches"][0][0]["panel"] = "panel_fantasma"
    assert "panel_inexistente" in errores(sano)


def test_borde_inexistente(sano):
    sano["pattern"]["stitches"][0][0]["edge"] = 999
    assert "borde_inexistente" in errores(sano)


# --- la extension de formato: declarar la intencion -------------------------

def _desajustar(spec, indice_costura=1, factor=1.08, desplazamiento=1.5):
    """Mueve un vertice para que los dos bordes de una costura dejen de calzar."""
    st = spec["pattern"]["stitches"][indice_costura]
    panel = spec["pattern"]["panels"][st[0]["panel"]]
    vi = panel["edges"][st[0]["edge"]]["endpoints"][1]
    x, y = panel["vertices"][vi]
    panel["vertices"][vi] = [x * factor + desplazamiento, y * factor + desplazamiento]
    return spec


def _ratio_real(spec, indice_costura=1):
    L = [longitud(spec["pattern"]["panels"][l["panel"]], l["edge"])
         for l in spec["pattern"]["stitches"][indice_costura]]
    return max(L) / min(L)


def test_desajuste_sin_declarar_es_error(sano):
    assert "desajuste_no_declarado" in errores(_desajustar(sano))


def test_desajuste_declarado_es_valido(sano):
    """El mismo desajuste deja de ser error al declararlo como fruncido."""
    _desajustar(sano)
    st = sano["pattern"]["stitches"][1]
    st[0]["ease"] = {"type": "gather", "ratio": round(_ratio_real(sano), 4), "tol": 0.02}
    assert errores(sano) == set()


def test_declaracion_falsa_se_detecta(sano):
    """Declarar un ratio que la geometria no respalda no salva el patron."""
    _desajustar(sano)
    sano["pattern"]["stitches"][1][0]["ease"] = {"type": "gather", "ratio": 3.0, "tol": 0.02}
    assert "ease_incongruente" in errores(sano)


def test_fruncido_grande_sin_declarar_es_aviso(sano):
    """Un desajuste enorme es casi seguro deliberado: aviso, no error."""
    _desajustar(sano, factor=1.9, desplazamiento=14.0)
    hallazgos = {h.codigo: h for h in validar(sano)}
    assert "fruncido_no_declarado" in hallazgos
    assert hallazgos["fruncido_no_declarado"].severidad == "aviso"


# --- geometria del panel ----------------------------------------------------

def test_contorno_abierto(sano):
    primer_panel = next(iter(sano["pattern"]["panels"].values()))
    primer_panel["edges"].pop()
    assert "contorno_abierto" in errores(sano)


def test_borde_degenerado(sano):
    panel = next(iter(sano["pattern"]["panels"].values()))
    a, b = panel["edges"][0]["endpoints"]
    panel["vertices"][b] = [panel["vertices"][a][0] + 0.02,
                            panel["vertices"][a][1] + 0.02]
    assert "borde_degenerado" in errores(sano)


def test_excede_ancho_rollo(sano):
    panel = next(iter(sano["pattern"]["panels"].values()))
    panel["vertices"] = [[v[0] * 12, v[1] * 12] for v in panel["vertices"]]
    assert "excede_ancho_rollo" in errores(sano)


# --- grafo de costuras ------------------------------------------------------

def test_borde_cosido_dos_veces(sano):
    st = sano["pattern"]["stitches"]
    st.append([copy.deepcopy(st[0][0]), copy.deepcopy(st[2][1])])
    assert "borde_multicosido" in errores(sano)


def test_panel_suelto(sano):
    nombre = next(iter(sano["pattern"]["panels"]))
    sano["pattern"]["stitches"] = [
        st for st in sano["pattern"]["stitches"]
        if all(lado["panel"] != nombre for lado in st)
    ]
    assert "panel_suelto" in errores(sano)


# --- las pinzas no son defectos --------------------------------------------

def test_pinza_no_se_marca_como_esquina_aguda():
    """Un panel cuadrado con una pinza en V: valida, pese al pico agudo."""
    panel = {
        "vertices": [[0, 0], [40, 0], [40, 60], [22, 60], [21, 20], [20, 60], [0, 60]],
        "edges": [{"endpoints": [0, 1]}, {"endpoints": [1, 2]}, {"endpoints": [2, 3]},
                  {"endpoints": [3, 4]}, {"endpoints": [4, 5]}, {"endpoints": [5, 6]},
                  {"endpoints": [6, 0]}],
    }
    spec = {"pattern": {"panels": {"p": panel}, "stitches": []}}
    codigos = {h.codigo for h in validar(spec)}
    assert "pico_de_pinza" in codigos
    assert "esquina_aguda" not in codigos
