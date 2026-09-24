"""Los scripts de research/ que producen cifras del paper.

No necesitan el corpus: se prueban sobre los fixtures y archivos temporales.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).parents[1]
sys.path.insert(0, str(RAIZ / "research"))
FIXTURE = RAIZ / "tests" / "fixtures" / "tshirt.json"

import aipparel_contraste  # noqa: E402
import aipparel_medir  # noqa: E402


def test_aipparel_cuenta_las_salidas_inservibles(tmp_path):
    """Faltante, ilegible y legible: el denominador es 3, no 1."""
    bueno = tmp_path / "bueno.json"
    bueno.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    basura = tmp_path / "basura.json"
    basura.write_text("{esto no es json", encoding="utf-8")

    d = aipparel_medir.medir([bueno, basura, tmp_path / "no_existe.json"])
    assert d["n_esperado"] == 3
    assert d["n_presente"] == 2
    assert d["n_legible"] == 1
    assert d["sin_defecto_duro"] == 1
    assert d["por_codigo"]["sin_salida"] == 1


def test_mcnemar_trata_la_salida_faltante_como_fallo(tmp_path):
    assert aipparel_contraste.mirar(tmp_path / "no_existe.json") is None
    sano = aipparel_contraste.mirar(FIXTURE)
    por_prenda = {"a": {"image": sano, "description": None},
                  "b": {"image": None, "description": sano},
                  "c": {"image": None, "description": None}}
    assert aipparel_contraste.discordantes(por_prenda) == (1, 1)


def test_supuesto_de_errores_del_paper():
    """Solo duros y desajustes no declarados; cualquier otro error para el script."""
    import pytest
    from numeros_paper import comprobar_supuesto

    comprobar_supuesto({"borde_degenerado", "esquina_aguda", "desajuste_no_declarado"})
    with pytest.raises(SystemExit, match="ease_incongruente"):
        comprobar_supuesto({"borde_degenerado", "ease_incongruente"})


def _costura(largo_b):
    """Dos paneles cosidos por un lado de 100 cm contra otro de `largo_b`."""
    aristas = [{"endpoints": [0, 1]}, {"endpoints": [1, 2]},
               {"endpoints": [2, 3]}, {"endpoints": [3, 0]}]
    return {"pattern": {
        "panels": {"a": {"vertices": [[0, 0], [20, 0], [20, 100], [0, 100]],
                         "edges": [dict(e) for e in aristas]},
                   "b": {"vertices": [[0, 0], [20, 0], [20, largo_b], [0, largo_b]],
                         "edges": [dict(e) for e in aristas]}},
        "stitches": [[{"panel": "a", "edge": 1}, {"panel": "b", "edge": 3}]]}}


def test_desajuste_en_zona_de_error_se_cuenta_por_codigo(tmp_path):
    """15,004% es fruncido (aviso), aunque desajuste_rel redondee a 0.15."""
    import json

    import numeros_paper

    (tmp_path / "x_specification.json").write_text(json.dumps(_costura(84.996)),
                                                   encoding="utf-8")
    r = numeros_paper.resumen(numeros_paper.medir(tmp_path))
    assert r["desajuste_error_rel"] == {}
    assert r["desajuste_todos_rel"]["n"] == 1
