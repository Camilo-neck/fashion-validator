"""Dos preguntas que la tabla de porcentajes deja abiertas.

1. Imagen contra texto esta pareado -- la misma prenda por las dos vias -- asi que
   la comparacion correcta es McNemar sobre los casos discordantes, no dos
   porcentajes puestos uno al lado del otro.
2. "Errores por patron" premia al patron con menos costuras. La tasa por costura
   dice si AIpparel cose peor o solo cose mas.

Una prenda sin salida, o con una salida ilegible, cuenta como patron con defecto
duro en el McNemar: el modelo no entrego nada utilizable. En la tasa por costura
no entra, porque no tiene costuras que contar.

Uso: python aipparel_contraste.py <dir_salida> <indice.json> <dir_corpus>
"""
import json
import math
import sys
from pathlib import Path

from hilvan import DUROS, validar
from hilvan.model import Limites

LIM = Limites()


def mirar(ruta: Path):
    """(sin defecto duro, n de costuras, n de costuras desajustadas), o None.

    None es una salida que falta, no se puede leer o tumba al validador.
    """
    try:
        spec = json.loads(ruta.read_text(encoding="utf-8"))
        hallazgos = validar(spec, LIM)
    except Exception:  # noqa: BLE001 - una salida inservible es un dato
        return None
    codigos = {h.codigo for h in hallazgos}
    costuras = len(spec.get("pattern", spec).get("stitches", []))
    desajustes = sum(1 for h in hallazgos
                     if h.codigo in ("desajuste_no_declarado", "fruncido_no_declarado"))
    return not (DUROS & codigos), costuras, desajustes


def binomial_dos_colas(k, n):
    """p exacto de McNemar: bajo H0 los discordantes se reparten al 50%."""
    if n == 0:
        return 1.0
    cola = sum(math.comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2 ** n
    return min(1.0, 2 * cola)


def discordantes(por_prenda: dict, a: str = "image", b: str = "description"):
    """(solo `a` sin defecto duro, solo `b`), con las salidas inservibles como fallo."""
    hdf = lambda v, m: v.get(m) is not None and v[m][0]
    solo_a = sum(1 for v in por_prenda.values() if hdf(v, a) and not hdf(v, b))
    solo_b = sum(1 for v in por_prenda.values() if hdf(v, b) and not hdf(v, a))
    return solo_a, solo_b


def main(salida: Path, ruta_indice: Path, corpus: Path) -> None:
    indice = json.loads(ruta_indice.read_text())
    por_prenda: dict = {}
    for e in indice:
        pred = salida / f"sample_{e['sample']}" / "NNSewingPattern_pred_specification.json"
        por_prenda.setdefault(e["prenda"], {})[e["modo"]] = mirar(pred)
    for pid in por_prenda:
        por_prenda[pid]["corpus"] = mirar(corpus / f"rand_{pid}_specification.json")

    # 1. McNemar sobre "sin defecto duro", imagen contra texto
    solo_img, solo_txt = discordantes(por_prenda)
    disc = solo_img + solo_txt
    p = binomial_dos_colas(min(solo_img, solo_txt), disc)
    inservibles = sum(1 for v in por_prenda.values() for m in ("image", "description")
                      if v.get(m) is None)
    print(f"imagen vs texto (sin defecto duro), {len(por_prenda)} prendas pareadas; "
          f"{inservibles} salidas inservibles cuentan como fallo")
    print(f"  solo la imagen sale limpia: {solo_img}   solo el texto: {solo_txt}   "
          f"discordantes: {disc}")
    print(f"  McNemar exacto: p = {p:.3f}  ->  "
          f"{'diferencia real' if p < 0.05 else 'indistinguible de ruido'}")

    # 2. Tasa de desajuste por costura, solo sobre salidas legibles
    print("\ncosturas y desajustes")
    print(f"  {'grupo':8} {'legibles':>9} {'costuras/patron':>16} {'desajustes/costura':>20}")
    for modo, nombre in (("image", "imagen"), ("description", "texto"), ("corpus", "corpus")):
        datos = [v[modo] for v in por_prenda.values() if v.get(modo) is not None]
        if not datos:
            continue
        cost = sum(d[1] for d in datos)
        des = sum(d[2] for d in datos)
        print(f"  {nombre:8} {len(datos):>9} {cost / len(datos):>16.1f} "
              f"{des / cost if cost else 0:>20.2f}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
