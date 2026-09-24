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
