"""Mide con la misma vara los patrones de AIpparel y los del corpus que los inspiro.

Tres grupos sobre las mismas 100 prendas: AIpparel desde el render, AIpparel desde
una descripcion de texto, y el patron original de GarmentCodeData. Que el ground
truth pase por el mismo validador es lo que hace comparable el numero: sin esa
columna, un 0% de AIpparel no dice si el modelo falla o si la vara es imposible.

Uso: python medir_lote.py <dir_salida_inferencia> <indice.json> <dir_corpus>
"""
import json, sys
from collections import Counter
from pathlib import Path

from hilvan.corpus import validar_archivo
from hilvan.model import Limites

# Defectos que dependen solo de la geometria del panel, no de una intencion que
# el formato no guarda. Un desajuste de costura puede ser un fruncido legitimo;
# un borde de 0,18 mm no se puede cortar en ninguna lectura.
DUROS = {"borde_degenerado", "esquina_aguda", "curvatura_excesiva",
         "excede_ancho_rollo", "auto_interseccion"}

SALIDA, INDICE, CORPUS = (Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
lim = Limites()


def medir(rutas):
    """Devuelve (n, limpios, sin_defecto_duro, codigos, errores_totales)."""
    limpios = blandos = n = 0
    codigos = Counter()
    errores = 0
    for r in rutas:
        res = validar_archivo(r, lim)
        if "ilegible" in res or "fallo" in res:
            codigos[res.get("ilegible") or "fallo_validador"] += 1
            continue
        n += 1
        errores += res["errores"]
        codigos.update(res["por_codigo"])
        if res["valido"]:
            limpios += 1
        if not (DUROS & set(res["por_codigo"])):
            blandos += 1
    return n, limpios, blandos, codigos, errores


indice = json.loads(INDICE.read_text())
grupos = {"imagen": [], "texto": [], "corpus": []}
for e in indice:
    pred = SALIDA / f"sample_{e['sample']}" / "NNSewingPattern_pred_specification.json"
    if pred.exists():
        grupos["imagen" if e["modo"] == "image" else "texto"].append(pred)
# el ground truth va una sola vez por prenda, no dos
for pid in sorted({e["prenda"] for e in indice}):
    orig = CORPUS / f"rand_{pid}_specification.json"
    if orig.exists():
        grupos["corpus"].append(orig)

print(f"{'grupo':10} {'n':>4} {'manufacturable':>15} {'sin defecto duro':>18} {'errores/patron':>15}")
informe = {}
for nombre, rutas in grupos.items():
    n, limpios, blandos, codigos, errores = medir(rutas)
    if not n:
        print(f"{nombre:10} {0:>4}  (sin patrones)")
        continue
    informe[nombre] = {"n": n, "limpios": limpios, "sin_duro": blandos,
                       "errores_por_patron": round(errores / n, 1),
                       "por_codigo": dict(codigos.most_common())}
    print(f"{nombre:10} {n:>4} {limpios:>9} ({100*limpios/n:4.1f}%) "
          f"{blandos:>10} ({100*blandos/n:4.1f}%) {errores/n:>15.1f}")

print("\ncodigos mas frecuentes por grupo")
for nombre, d in informe.items():
    top = list(d["por_codigo"].items())[:6]
    print(f"  {nombre:8}", ", ".join(f"{k} x{v}" for k, v in top))

destino = INDICE.parent / "informe_aipparel.json"
destino.write_text(json.dumps(informe, indent=1, ensure_ascii=False))
print("\n->", destino)
