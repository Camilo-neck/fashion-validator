"""Prueba de discriminacion: el validador debe aceptar lo sano y marcar lo roto.

Las dos direcciones importan por igual. Un validador que marca todo no sirve
para nada, que es como empezo este: rechazaba el 100% de los patrones porque
leia las pinzas como defecto.
"""

import copy
import json
from pathlib import Path

import pytest

from fashion_validator import validar, longitud, Limites, Cuerpo, bucles_libres

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


# --- continuidad al cruzar una costura --------------------------------------

def _dos_paneles(vertices_b):
    """Dos paneles cosidos por un costado. El contorno libre cruza esa costura."""
    rect = [[0, 0], [20, 0], [20, 40], [0, 40]]
    aristas = [{"endpoints": [0, 1]}, {"endpoints": [1, 2]},
               {"endpoints": [2, 3]}, {"endpoints": [3, 0]}]
    return {"pattern": {
        "panels": {"a": {"vertices": rect, "edges": [dict(e) for e in aristas]},
                   "b": {"vertices": vertices_b, "edges": [dict(e) for e in aristas]}},
        "stitches": [[{"panel": "a", "edge": 1}, {"panel": "b", "edge": 3}]],
    }}


# el vertice 1 de `b` bajado inclina el borde vecino a la costura y quiebra el
# contorno; el borde de la costura no se toca, asi que las longitudes calzan
RECTO = [[0, 0], [20, 0], [20, 40], [0, 40]]
QUEBRADO = [[0, 0], [20, -15], [20, 40], [0, 40]]


def test_cruce_suave_no_se_reporta():
    """Dos paneles rectos cosidos: el contorno sigue recto, no hay nada que decir."""
    codigos = {h.codigo for h in validar(_dos_paneles(RECTO))}
    assert "quiebre_en_cruce" not in codigos
    assert "esquina_de_diseno" not in codigos


def test_quiebre_en_cruce_se_detecta():
    """Con el contorno quebrado 37 grados, el cruce se reporta como aviso."""
    hallazgos = validar(_dos_paneles(QUEBRADO),
                        Limites(permitir_esquinas_rectas=False))
    quiebres = [h for h in hallazgos if h.codigo == "quiebre_en_cruce"]
    assert len(quiebres) == 1
    assert quiebres[0].severidad == "aviso"
    assert quiebres[0].medido["desviacion_grados"] == pytest.approx(36.87, abs=0.1)


def test_esquina_entre_rectas_se_interpreta_como_diseno():
    """El mismo quiebre entre dos bordes rectos es una esquina dibujada.

    Es el bajo de un godet o una abertura, no un escote que deberia fluir. Sin
    esta excepcion toda falda con godets sale marcada.
    """
    codigos = {h.codigo: h for h in validar(_dos_paneles(QUEBRADO))}
    assert "quiebre_en_cruce" not in codigos
    assert codigos["esquina_de_diseno"].severidad == "info"


# --- acabado de los bordes libres -------------------------------------------

def _bordes_cosidos(spec):
    return {(l["panel"], l["edge"]) for st in spec["pattern"]["stitches"] for l in st}


def _rematar_todo(spec, tipo="hem"):
    """Declara un acabado en cada borde que no se cose."""
    cosidos = _bordes_cosidos(spec)
    for nombre, panel in spec["pattern"]["panels"].items():
        for i, e in enumerate(panel["edges"]):
            if (nombre, i) not in cosidos:
                e["finish"] = {"type": tipo}
    return spec


def test_borde_libre_sin_acabado_es_aviso(sano):
    """El hueco de formato: un dobladillo y un borde olvidado son el mismo dato."""
    codigos = {h.codigo: h for h in validar(sano)}
    assert codigos["acabado_no_declarado"].severidad == "aviso"
    assert codigos["acabado_no_declarado"].medido["cuantos"] == 12


def test_acabado_declarado_quita_el_aviso(sano):
    codigos = {h.codigo for h in validar(_rematar_todo(sano))}
    assert "acabado_no_declarado" not in codigos


def test_acabado_sobre_borde_cosido_es_error(sano):
    """Un borde cosido no lleva acabado: las dos cosas se excluyen."""
    st = sano["pattern"]["stitches"][0][0]
    sano["pattern"]["panels"][st["panel"]]["edges"][st["edge"]]["finish"] = {"type": "hem"}
    assert "acabado_incongruente" in errores(sano)


def test_acabado_de_tipo_desconocido_es_error(sano):
    assert "acabado_incongruente" in errores(_rematar_todo(sano, tipo="pegamento"))


# --- secuencia de ensamblaje ------------------------------------------------

def test_costuras_en_redondo_se_cuentan(sano):
    """8 paneles y 16 costuras dejan 16 - 8 + 1 = 9 tubos que cerrar."""
    codigos = {h.codigo: h for h in validar(sano)}
    assert codigos["costuras_en_redondo"].medido["cuantas"] == 9


def test_dos_paneles_se_cosen_en_plano():
    """Una sola costura no cierra ningun tubo: todo se cose en plano."""
    codigos = {h.codigo for h in validar(_dos_paneles(RECTO))}
    assert "costuras_en_redondo" not in codigos


# --- orientacion de la costura ----------------------------------------------

def test_orientacion_declarada_se_usa(sano):
    """Declarada, el hallazgo deja de ser una cota inferior."""
    for st in sano["pattern"]["stitches"]:
        st[0]["orient"] = "reversed"
    quiebres = [h for h in validar(sano) if h.codigo == "quiebre_en_cruce"]
    assert quiebres
    assert all(h.medido["emparejamiento"] == "declarado" for h in quiebres)


def test_sin_declarar_el_emparejamiento_es_deducido(sano):
    quiebres = [h for h in validar(sano) if h.codigo == "quiebre_en_cruce"]
    assert all(h.medido["emparejamiento"] == "deducido" for h in quiebres)


def test_orientacion_contradicha_por_la_topologia(sano):
    """La camiseta encaja en 12 cruces con `reversed` y solo en 4 con `direct`."""
    for st in sano["pattern"]["stitches"]:
        st[0]["orient"] = "direct"
    dudosas = [h for h in validar(sano) if h.codigo == "orientacion_dudosa"]
    assert dudosas
    assert dudosas[0].severidad == "aviso"


def test_orientacion_coherente_no_se_reporta(sano):
    for st in sano["pattern"]["stitches"]:
        st[0]["orient"] = "reversed"
    assert "orientacion_dudosa" not in {h.codigo for h in validar(sano)}


def test_orientacion_desconocida_es_error(sano):
    sano["pattern"]["stitches"][0][0]["orient"] = "al_reves"
    assert "orientacion_incongruente" in errores(sano)


def test_orientacion_declarada_puede_destapar_un_quiebre():
    """Deducir elige el emparejamiento mas favorable; declarar lo fija."""
    spec = _dos_paneles(QUEBRADO)
    lim = Limites(permitir_esquinas_rectas=False)
    por_defecto = len([h for h in validar(spec, lim) if h.codigo == "quiebre_en_cruce"])
    spec["pattern"]["stitches"][0][0]["orient"] = "direct"
    directo = len([h for h in validar(spec, lim) if h.codigo == "quiebre_en_cruce"])
    spec["pattern"]["stitches"][0][0]["orient"] = "reversed"
    invertido = len([h for h in validar(spec, lim) if h.codigo == "quiebre_en_cruce"])
    assert por_defecto <= max(directo, invertido)


# --- nivel 2 sin simulacion: vestibilidad -----------------------------------

def _montada(spec):
    """Declara la orientacion en todas las costuras: sin eso no se juzga nada."""
    for st in spec["pattern"]["stitches"]:
        st[0]["orient"] = "reversed"
    return spec


def _declarar_abertura(spec, contorno_aprox, **campos):
    """Pone una declaracion `finish` en el bucle cuyo contorno se parece al dado."""
    panels = spec["pattern"]["panels"]
    for bucle in bucles_libres(spec["pattern"]):
        largo = sum(longitud(panels[n], i) for n, i in bucle)
        if abs(largo - contorno_aprox) < 1.0:
            n, i = bucle[0]
            panels[n]["edges"][i]["finish"] = {"type": "opening", **campos}
            return spec
    raise AssertionError(f"no hay ningun bucle de {contorno_aprox} cm")


def _errores_vestibilidad(spec) -> set[str]:
    """Los chequeos contra el cuerpo solo corren si se aporta un cuerpo."""
    return {h.codigo for h in validar(spec, cuerpo=Cuerpo()) if h.severidad == "error"}


def test_aberturas_de_la_camiseta(sano):
    """Dos punos, escote y bajo: cuatro bucles del contorno libre."""
    panels = sano["pattern"]["panels"]
    contornos = sorted(round(sum(longitud(panels[n], i) for n, i in b), 1)
                       for b in bucles_libres(sano["pattern"]))
    assert contornos == [42.1, 42.1, 70.1, 104.8]


def test_sin_orient_se_mide_pero_no_se_juzga(sano):
    """El montaje supuesto informa contornos y no emite ningun veredicto."""
    _declarar_abertura(sano, 42.1, fits="head")
    hallazgos = [h for h in validar(sano, cuerpo=Cuerpo()) if h.nivel == 2]
    assert any(h.codigo == "montaje_supuesto" for h in hallazgos)
    assert not [h for h in hallazgos if h.severidad == "error"]


def test_abertura_insuficiente(sano):
    """Un puno de 42 cm declarado para pasar una cabeza de 57 no pasa."""
    _declarar_abertura(_montada(sano), 42.1, fits="head")
    assert "abertura_insuficiente" in _errores_vestibilidad(sano)


def test_el_estiramiento_declarado_evita_el_error(sano):
    """42 cm de punto que estira a 1.5 dan 63 cm utiles: pasa."""
    _declarar_abertura(_montada(sano), 42.1, fits="head", stretch=1.5)
    assert "abertura_insuficiente" not in _errores_vestibilidad(sano)


def test_el_cierre_declarado_evita_el_error(sano):
    _declarar_abertura(_montada(sano), 42.1, fits="head", closure="zip")
    assert "abertura_insuficiente" not in _errores_vestibilidad(sano)


def test_abertura_holgada_no_es_error(sano):
    """El bajo de 104.8 cm sobre una cadera de 100 pasa con holgura."""
    _declarar_abertura(_montada(sano), 104.8, fits="hip")
    assert "abertura_insuficiente" not in _errores_vestibilidad(sano)


def test_prenda_sellada():
    """Cuatro costuras cierran los dos paneles: no hay por donde entrar."""
    rect = [[0, 0], [20, 0], [20, 40], [0, 40]]
    aristas = [{"endpoints": [0, 1]}, {"endpoints": [1, 2]},
               {"endpoints": [2, 3]}, {"endpoints": [3, 0]}]
    spec = {"pattern": {
        "panels": {"a": {"vertices": rect, "edges": [dict(e) for e in aristas]},
                   "b": {"vertices": rect, "edges": [dict(e) for e in aristas]}},
        "stitches": [[{"panel": "a", "edge": k}, {"panel": "b", "edge": k}]
                     for k in range(4)],
    }}
    assert "prenda_sellada" in errores(spec)
