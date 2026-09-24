"""Mide con la misma vara los patrones de AIpparel y los del corpus que los inspiro.

Tres grupos sobre las mismas 100 prendas: AIpparel desde el render, AIpparel desde
una descripcion de texto, y el patron original de GarmentCodeData. Que el ground
truth pase por el mismo validador es lo que hace comparable el numero: sin esa
columna, un 0% de AIpparel no dice si el modelo falla o si la vara es imposible.

Toda muestra esperada cuenta en el denominador. Una salida que no existe, que no
se puede leer o que tumba al validador es un patron que no sirve: si se sacara
del denominador, el porcentaje favoreceria al modelo justo en sus peores casos.

Uso: python aipparel_medir.py <dir_salida_inferencia> <indice.json> <dir_corpus>
"""
import json
import sys
from collections import Counter
from pathlib import Path

from hilvan import DUROS, Limites
from hilvan.corpus import validar_archivo

LIM = Limites()


def medir(rutas: list[Path]) -> dict:
    """Recuento de un grupo sobre todas las rutas esperadas, existan o no."""
    presentes = legibles = limpios = sin_duro = errores = 0
    codigos: Counter = Counter()
    for r in rutas:
        if not r.exists():
            codigos["sin_salida"] += 1
            continue
        presentes += 1
        res = validar_archivo(r, LIM)
        if "ilegible" in res or "fallo" in res:
            codigos[res.get("ilegible") or "fallo_validador"] += 1
            continue
        legibles += 1
        errores += res["errores"]
        codigos.update(res["por_codigo"])
        limpios += res["valido"]
        sin_duro += not (DUROS & set(res["por_codigo"]))
    return {"n_esperado": len(rutas), "n_presente": presentes, "n_legible": legibles,
            "validado": limpios, "sin_defecto_duro": sin_duro,
            "errores_por_patron_legible": round(errores / legibles, 1) if legibles else None,
            "por_codigo": dict(codigos.most_common())}


def grupos(salida: Path, indice: list[dict], corpus: Path) -> dict[str, list[Path]]:
    """Las rutas que deberian existir, una por muestra pedida y una por prenda."""
    out = {"imagen": [], "texto": [], "corpus": []}
    for e in indice:
        pred = salida / f"sample_{e['sample']}" / "NNSewingPattern_pred_specification.json"
        out["imagen" if e["modo"] == "image" else "texto"].append(pred)
    # el ground truth va una sola vez por prenda, no dos
    for pid in sorted({e["prenda"] for e in indice}):
        out["corpus"].append(corpus / f"rand_{pid}_specification.json")
    return out


def main(salida: Path, ruta_indice: Path, corpus: Path) -> None:
    indice = json.loads(ruta_indice.read_text())
    informe = {nombre: medir(rutas)
               for nombre, rutas in grupos(salida, indice, corpus).items()}

    print(f"{'grupo':8} {'esperado':>8} {'presente':>8} {'legible':>8} "
          f"{'sin defecto duro':>18} {'validado':>12}")
    for nombre, d in informe.items():
        n = d["n_esperado"]
        print(f"{nombre:8} {n:>8} {d['n_presente']:>8} {d['n_legible']:>8} "
              f"{d['sin_defecto_duro']:>8} ({100 * d['sin_defecto_duro'] / n:4.1f}%) "
              f"{d['validado']:>4} ({100 * d['validado'] / n:4.1f}%)")

    print("\ncodigos mas frecuentes por grupo")
    for nombre, d in informe.items():
        top = list(d["por_codigo"].items())[:6]
        print(f"  {nombre:8}", ", ".join(f"{k} x{v}" for k, v in top))

    destino = ruta_indice.parent / "informe_aipparel.json"
    destino.write_text(json.dumps(informe, indent=1, ensure_ascii=False))
    print("\n->", destino)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
