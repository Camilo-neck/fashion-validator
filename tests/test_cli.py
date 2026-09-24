"""El CLI: 0 validado, 1 no validado, 2 error de uso o de lectura."""

import json
from pathlib import Path

from hilvan.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
CAMISETA = str(FIXTURES / "tshirt.json")
FALDA = str(FIXTURES / "Configured_design_specification.json")


def test_patron_validado_sale_con_0():
    assert main([CAMISETA]) == 0


def test_patron_no_validado_sale_con_1():
    assert main([FALDA]) == 1


def test_archivo_inexistente_sale_con_2_y_una_linea(tmp_path, capsys):
    assert main([str(tmp_path / "no_existe.json")]) == 2
    err = capsys.readouterr().err
    assert err.startswith("hilvan: error:") and err.count("\n") == 1


def test_json_invalido_sale_con_2(tmp_path):
    roto = tmp_path / "roto.json"
    roto.write_text("{esto no es json", encoding="utf-8")
    assert main([str(roto)]) == 2


def test_limites_desde_archivo(tmp_path):
    """Con un borde minimo de 100 cm, la camiseta deja de pasar."""
    lim = tmp_path / "lim.json"
    lim.write_text(json.dumps({"largo_min_borde": 100}), encoding="utf-8")
    assert main([CAMISETA, "--limites", str(lim)]) == 1


def test_limite_desconocido_sale_con_2(tmp_path, capsys):
    lim = tmp_path / "lim.json"
    lim.write_text(json.dumps({"largo_minimo": 1}), encoding="utf-8")
    assert main([CAMISETA, "--limites", str(lim)]) == 2
    assert "largo_minimo" in capsys.readouterr().err


def test_limite_de_tipo_equivocado_sale_con_2(tmp_path):
    lim = tmp_path / "lim.json"
    lim.write_text(json.dumps({"tol_costura": "mucho"}), encoding="utf-8")
    assert main([CAMISETA, "--limites", str(lim)]) == 2


def test_lote_sobre_algo_que_no_es_directorio_sale_con_2():
    assert main([CAMISETA, "--lote"]) == 2
