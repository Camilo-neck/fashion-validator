"""Prueba de discriminacion: el validador debe aceptar lo sano y marcar lo roto.

Las dos direcciones importan por igual. Un validador que marca todo no sirve
para nada, que es como empezo este: rechazaba el 100% de los patrones porque
leia las pinzas como defecto.
"""

import copy
import json
from pathlib import Path

import pytest

from hilvan import validar, longitud, Limites, Cuerpo, bucles_libres

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


# --- auto-interseccion ------------------------------------------------------

def test_auto_interseccion():
    """Un panel en pajarita: las dos diagonales se cruzan fuera de un vertice."""
    panel = {
        "vertices": [[0, 0], [20, 20], [20, 0], [0, 20]],
        "edges": [{"endpoints": [0, 1]}, {"endpoints": [1, 2]},
                  {"endpoints": [2, 3]}, {"endpoints": [3, 0]}],
    }
    spec = {"pattern": {"panels": {"p": panel}, "stitches": []}}
    assert "auto_interseccion" in errores(spec)


def test_panel_convexo_no_se_cruza(sano):
    """El descarte por caja envolvente no puede inventar cruces ni perderlos."""
    assert "auto_interseccion" not in errores(sano)


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


def test_sin_orient_el_veredicto_baja_a_aviso(sano):
    """El convenio por defecto sostiene el hallazgo, pero el patron no lo afirma.

    El convenio esta medido sobre el corpus (docs/hallazgos-corpus.md), asi que
    callarse seria desperdiciarlo; pero sin declaracion el hallazgo no puede
    ser un error.
    """
    _declarar_abertura(sano, 42.1, fits="head")
    hallazgos = [h for h in validar(sano, cuerpo=Cuerpo()) if h.nivel == 2]
    assert any(h.codigo == "montaje_supuesto" for h in hallazgos)
    assert not [h for h in hallazgos if h.severidad == "error"]
    insuf = [h for h in hallazgos if h.codigo == "abertura_insuficiente"]
    assert len(insuf) == 1 and insuf[0].severidad == "aviso"


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


# --- barrido de un corpus ---------------------------------------------------

def test_barrido_separa_sano_de_roto(tmp_path, sano):
    """El manifiesto es lo que se pasa al entrenamiento: solo lo que pasa limpio."""
    from hilvan.corpus import barrer

    (tmp_path / "bueno.json").write_text(json.dumps(sano), encoding="utf-8")
    roto = copy.deepcopy(sano)
    roto["pattern"]["stitches"][0][0]["edge"] = 999
    (tmp_path / "malo.json").write_text(json.dumps(roto), encoding="utf-8")

    informe = barrer(tmp_path, patron="*.json")
    assert informe["medidos"] == 2
    assert informe["sanos"] == 1 and informe["rotos"] == 1
    assert informe["pct_rechazados"] == 50.0
    assert [Path(x).name for x in informe["manifiesto_sanos"]] == ["bueno.json"]


def test_barrido_no_se_cae_con_basura(tmp_path, sano):
    """Un archivo ilegible es un resultado, no una excepcion que corta el barrido."""
    from hilvan.corpus import barrer

    (tmp_path / "bueno.json").write_text(json.dumps(sano), encoding="utf-8")
    (tmp_path / "trozo.json").write_text("{esto no es json", encoding="utf-8")
    (tmp_path / "otro.json").write_text('{"pattern": {}}', encoding="utf-8")

    informe = barrer(tmp_path, patron="*.json")
    assert informe["medidos"] == 1
    assert len(informe["ilegibles"]) == 2
    assert not informe["fallos_del_validador"]


def _emitidos() -> set[str]:
    """Los codigos que el paquete construye de verdad, leidos de su fuente."""
    import re

    import hilvan

    emitidos = set()
    for f in Path(hilvan.__file__).parent.glob("*.py"):
        emitidos |= set(re.findall(r'Hallazgo\(\s*\d+,\s*"([a-z_]+)"',
                                   f.read_text(encoding="utf-8")))
    assert emitidos, "no se encontro ningun Hallazgo construido"
    return emitidos


def test_duros_son_codigos_que_el_validador_emite():
    """DUROS decide que se filtra de un corpus: un codigo mal escrito ahi no
    falla, simplemente deja pasar el defecto. Este test ata la lista a los
    codigos que checks.py construye de verdad.
    """
    from hilvan import DUROS

    emitidos = _emitidos()
    assert DUROS <= emitidos, f"codigos inexistentes en DUROS: {sorted(DUROS - emitidos)}"


def test_estructurales_son_codigos_que_el_validador_emite():
    """Igual que DUROS: ESTRUCTURALES decide que es 'valido' en el paper."""
    from hilvan import ESTRUCTURALES

    emitidos = _emitidos()
    assert ESTRUCTURALES <= emitidos, sorted(ESTRUCTURALES - emitidos)


def test_resumen_en_tres_niveles(sano):
    """Un desajuste sin declarar: valido y sin defecto duro, pero no validado."""
    from hilvan import resumen

    r = resumen(validar(_desajustar(sano)))
    assert (r["valido"], r["sin_defecto_duro"], r["validado"]) == (True, True, False)
    sano["pattern"]["stitches"][0][0]["edge"] = 999
    assert resumen(validar(sano))["valido"] is False


def test_barrido_da_el_manifiesto_sin_defecto_duro(tmp_path, sano):
    """El manifiesto para entrenar: el desajuste no descarta, el defecto duro si."""
    from hilvan.corpus import barrer

    (tmp_path / "desajustado.json").write_text(
        json.dumps(_desajustar(copy.deepcopy(sano))), encoding="utf-8")
    duro = copy.deepcopy(sano)
    panel = next(iter(duro["pattern"]["panels"].values()))
    a, b = panel["edges"][0]["endpoints"]
    panel["vertices"][b] = [panel["vertices"][a][0] + 0.02, panel["vertices"][a][1] + 0.02]
    (tmp_path / "duro.json").write_text(json.dumps(duro), encoding="utf-8")

    informe = barrer(tmp_path, patron="*.json")
    assert informe["sanos"] == 0
    assert informe["validos"] == 2
    assert [Path(x).name for x in informe["manifiesto_sin_defecto_duro"]] == ["desajustado.json"]


# --- esquinas convexas y concavas -------------------------------------------

def _panel_solo(vertices, **extra):
    n = len(vertices)
    panel = {"vertices": vertices,
             "edges": [{"endpoints": [i, (i + 1) % n]} for i in range(n)], **extra}
    return {"pattern": {"panels": {"p": panel}, "stitches": []}}


# un cuadrado de 40 cm con una muesca asimetrica hacia dentro desde el borde
# inferior: en (20, 12) la tela da la vuelta a 354 grados, no a 6
MUESCA = [[0, 0], [20, 0], [20, 12], [21, 3], [21, 0], [40, 0], [40, 40], [0, 40]]


def test_muesca_concava_no_es_esquina_aguda():
    """Sin signo, la muesca mide 6.3 grados, igual que una punta: no es lo mismo."""
    hallazgos = {h.codigo: h for h in validar(_panel_solo(MUESCA))}
    assert "esquina_aguda" not in hallazgos
    muesca = hallazgos["muesca_aguda"]
    assert muesca.severidad == "aviso"
    assert muesca.medido["angulo_grados"] == pytest.approx(6.34, abs=0.05)
    assert muesca.medido["angulo_interior_grados"] == pytest.approx(353.66, abs=0.05)


def test_muesca_es_igual_en_los_dos_sentidos_de_recorrido():
    """La orientacion del contorno sale del area, no del orden de los vertices."""
    horario = list(reversed(MUESCA))
    codigos = {h.codigo for h in validar(_panel_solo(horario))}
    assert "muesca_aguda" in codigos and "esquina_aguda" not in codigos


def test_punta_convexa_es_esquina_aguda():
    """Una lengueta de 8 grados con lados distintos: defecto duro, no pinza."""
    hallazgos = [h for h in validar(_panel_solo([[0, 0], [30, 0], [40, 5.62]]))
                 if h.codigo == "esquina_aguda"]
    assert len(hallazgos) == 1
    assert hallazgos[0].severidad == "error"
    assert hallazgos[0].medido["angulo_interior_grados"] == pytest.approx(8.0, abs=0.1)


def test_pinzas_del_fixture_son_concavas():
    """Las cuatro pinzas de cintura de la falda con godets apuntan hacia dentro.

    Sus dos piernas se cosen entre si en el propio archivo (bordes 3-4, 6-7,
    9-10 y 12-13 de `skirt_back`), asi que son pinzas y se quedan como tales.
    Las ranuras de los godets, abajo, forman unos 25 grados y no se reportan.
    """
    spec = json.loads((FIXTURE.parent / "Configured_design_specification.json")
                      .read_text(encoding="utf-8"))
    pinzas = [h for h in validar(spec) if h.codigo == "pico_de_pinza"]
    assert len(pinzas) == 4
    assert all(h.medido["angulo_interior_grados"] > 340 for h in pinzas)


def test_punta_isosceles_no_es_pinza():
    """Piernas rectas e iguales no bastan: una pinza apunta hacia dentro."""
    codigos = {h.codigo for h in validar(_panel_solo([[0, 0], [40, -2.8], [40, 2.8]]))}
    assert "esquina_aguda" in codigos
    assert "pico_de_pinza" not in codigos


def test_desajuste_expone_el_valor_exacto(sano):
    """desajuste_rel va redondeado para leerlo; el exacto es el que decide."""
    h = next(h for h in validar(_desajustar(sano)) if h.codigo == "desajuste_no_declarado")
    assert h.medido["desajuste_rel"] == round(h.medido["desajuste_rel_exacto"], 4)


def test_contorno_con_dos_ciclos():
    """Grado 2 en todos los vertices, pero dos cuadrados: no es un contorno."""
    cuadrado = [[0, 0], [10, 0], [10, 10], [0, 10]]
    vertices = cuadrado + [[x + 20, y] for x, y in cuadrado]
    edges = ([{"endpoints": [i, (i + 1) % 4]} for i in range(4)]
             + [{"endpoints": [4 + i, 4 + (i + 1) % 4]} for i in range(4)])
    spec = {"pattern": {"panels": {"p": {"vertices": vertices, "edges": edges}},
                        "stitches": []}}
    from hilvan import ESTRUCTURALES, resumen

    assert "contorno_multiple" in errores(spec)
    assert "contorno_multiple" in ESTRUCTURALES
    assert resumen(validar(spec))["valido"] is False


def test_borde_que_se_cruza_consigo_mismo():
    """Una cubica con los controles cruzados hace un bucle sobre si misma."""
    panel = {"vertices": [[0, 0], [10, 0], [10, -10], [0, -10]],
             "edges": [{"endpoints": [0, 1],
                        "curvature": {"type": "cubic", "params": [[1.5, 1], [-0.5, 1]]}},
                       {"endpoints": [1, 2]}, {"endpoints": [2, 3]}, {"endpoints": [3, 0]}]}
    spec = {"pattern": {"panels": {"p": panel}, "stitches": []}}
    bucles = [h for h in validar(spec)
              if h.codigo == "auto_interseccion" and h.medido["otro_borde"] == h.borde]
    assert len(bucles) == 1 and bucles[0].borde == 0


def test_cubica_sin_bucle_no_se_cruza():
    panel = {"vertices": [[0, 0], [10, 0], [10, -10], [0, -10]],
             "edges": [{"endpoints": [0, 1],
                        "curvature": {"type": "cubic", "params": [[0.3, 0.2], [0.7, 0.2]]}},
                       {"endpoints": [1, 2]}, {"endpoints": [2, 3]}, {"endpoints": [3, 0]}]}
    spec = {"pattern": {"panels": {"p": panel}, "stitches": []}}
    assert "auto_interseccion" not in errores(spec)


def _rectangulo_girado(largo, ancho, grados):
    import math

    c, s = math.cos(math.radians(grados)), math.sin(math.radians(grados))
    return [[x * c - y * s, x * s + y * c]
            for x, y in [[0, 0], [largo, 0], [largo, ancho], [0, ancho]]]


def test_panel_girado_que_cabe_en_el_rollo():
    """200 x 100 cm girado 30 grados: su caja mide 223 x 187, pero cabe de lado."""
    assert "excede_ancho_rollo" not in errores(_panel_solo(_rectangulo_girado(200, 100, 30)))


def test_panel_girado_que_no_cabe():
    hallazgos = [h for h in validar(_panel_solo(_rectangulo_girado(200, 160, 30)))
                 if h.codigo == "excede_ancho_rollo"]
    assert len(hallazgos) == 1
    assert hallazgos[0].medido["ancho_cm"] == pytest.approx(160.0, abs=0.1)


def test_ease_se_mide_desde_el_lado_que_lo_declara():
    """Costura de 100 contra 75 cm: 0.75 desde el lado corto, 1.33 desde el largo."""
    from test_research import _costura

    for lado, ratio, bien in ((1, 0.75, True), (0, 100 / 75, True), (1, 100 / 75, False)):
        spec = _costura(75)
        spec["pattern"]["stitches"][0][lado]["ease"] = {"type": "gather", "ratio": ratio}
        assert ("ease_incongruente" not in errores(spec)) is bien, (lado, ratio)


@pytest.mark.parametrize("largo_b, esperado", [
    (99.0, []),                                            # 1% exacto: pasa
    (98.9, [("desajuste_no_declarado", "error")]),         # 1.1%: error
    (85.0, [("desajuste_no_declarado", "error")]),         # 15% exacto: todavia error
    (84.99, [("fruncido_no_declarado", "aviso")]),         # 15.01%: se presume fruncido
])
def test_frontera_de_las_zonas_de_desajuste(largo_b, esperado):
    from test_research import _costura

    hallazgos = [h for h in validar(_costura(largo_b))
                 if h.codigo in ("desajuste_no_declarado", "fruncido_no_declarado")]
    assert [(h.codigo, h.severidad) for h in hallazgos] == esperado
    for h in hallazgos:
        if h.codigo == "fruncido_no_declarado":
            assert h.medido["presunto"] == "fruncido"
            assert h.medido["umbral_fruncido"] == 0.15
            assert "umbral_fruncido" in h.mensaje


def test_mensajes_sin_cifras_de_un_corpus(sano):
    """El mensaje sale para cualquier patron, tambien uno de AIpparel: no puede
    citar datos de GarmentCodeData como si fueran del patron."""
    import re

    for h in validar(sano):
        assert not re.search(r"\d\.\d{3}\b", h.mensaje), h.mensaje


# --- una sola resolucion de la orientacion ----------------------------------

def test_orientaciones_declarada_por_defecto_y_deducida(sano):
    from hilvan.checks import orientaciones

    pat = sano["pattern"]
    origenes = {o for _, o in orientaciones(pat, Limites()).values()}
    assert origenes == {"por_defecto"}

    deducidas = orientaciones(pat, Limites(orientacion_por_defecto=None))
    assert {o for _, o in deducidas.values()} == {"deducida"}
    # en la camiseta la topologia elige lo mismo que el convenio de GarmentCode
    assert {o for o, _ in deducidas.values()} == {"reversed"}

    pat["stitches"][0][0]["orient"] = "direct"
    assert orientaciones(pat, Limites())[0] == ("direct", "declarada")


def test_nivel2_usa_la_orientacion_deducida(sano):
    """Sin convenio por defecto el montaje deduce, y la camiseta sale igual."""
    panels = sano["pattern"]["panels"]
    lim = Limites(orientacion_por_defecto=None)
    contornos = sorted(round(sum(longitud(panels[n], i) for n, i in b), 1)
                       for b in bucles_libres(sano["pattern"], lim))
    assert contornos == [42.1, 42.1, 70.1, 104.8]


def test_cli_acepta_la_orientacion_deducida(capsys):
    from hilvan.cli import main

    main([str(FIXTURE), "--orientacion", "deducida"])
    assert "deduce por topologia para el patron entero" in capsys.readouterr().out


# --- regresion sobre los fixtures -------------------------------------------

@pytest.mark.parametrize("archivo, esperado", [
    ("tshirt.json", {"abertura": 4, "acabado_no_declarado": 1, "bordes_libres": 1,
                     "costuras_en_redondo": 1, "montaje_supuesto": 1,
                     "quiebre_en_cruce": 2}),
    ("Configured_design_specification.json", {
        "abertura": 2, "acabado_no_declarado": 1, "borde_degenerado": 1,
        "bordes_libres": 1, "costuras_en_redondo": 1, "desajuste_no_declarado": 2,
        "esquina_aguda": 1, "esquina_de_diseno": 19, "montaje_supuesto": 1,
        "pico_de_pinza": 4}),
])
def test_recuento_exacto_por_codigo(archivo, esperado):
    """Un cambio de comportamiento en los fixtures no puede pasar sin verse."""
    from collections import Counter

    spec = json.loads((FIXTURE.parent / archivo).read_text(encoding="utf-8"))
    assert dict(Counter(h.codigo for h in validar(spec))) == esperado
