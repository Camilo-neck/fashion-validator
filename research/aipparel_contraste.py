"""Dos preguntas que la tabla de porcentajes deja abiertas.

1. Imagen contra texto esta pareado -- la misma prenda por las dos vias -- asi que
   la comparacion correcta es McNemar sobre los casos discordantes, no dos
   porcentajes puestos uno al lado del otro.
2. "Errores por patron" premia al patron con menos costuras. La tasa por costura
   dice si AIpparel cose peor o solo cose mas.

Uso: python contrastar.py <dir_salida> <indice.json> <dir_corpus>
"""
import json, math, sys
from pathlib import Path

from hilvan import validar
from hilvan.model import Limites

DUROS = {"borde_degenerado", "esquina_aguda", "curvatura_excesiva",
         "excede_ancho_rollo", "auto_interseccion"}
SALIDA, INDICE, CORPUS = (Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
lim = Limites()


def mirar(ruta):
    """(sin defecto duro, nº de costuras, nº de costuras que no cierran)."""
    spec = json.loads(ruta.read_text(encoding="utf-8"))
    hallazgos = validar(spec, lim)
    codigos = {h.codigo for h in hallazgos}
    costuras = len(spec.get("pattern", spec).get("stitches", []))
    desajustes = sum(1 for h in hallazgos
                     if h.codigo in ("desajuste_no_declarado", "fruncido_no_declarado"))
    return not (DUROS & codigos), costuras, desajustes


def binomial_dos_colas(k, n):
    """p exacto de McNemar: bajo H0 los discordantes se reparten al 50%."""
    if n == 0:
        return 1.0
    comb = lambda a, b: math.comb(a, b)
    cola = sum(comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2 ** n
    return min(1.0, 2 * cola)


indice = json.loads(INDICE.read_text())
por_prenda = {}
for e in indice:
    pred = SALIDA / f"sample_{e['sample']}" / "NNSewingPattern_pred_specification.json"
    if pred.exists():
        por_prenda.setdefault(e["prenda"], {})[e["modo"]] = mirar(pred)
for pid in list(por_prenda):
    orig = CORPUS / f"rand_{pid}_specification.json"
    if orig.exists():
        por_prenda[pid]["corpus"] = mirar(orig)

# 1. McNemar sobre "sin defecto duro", imagen contra texto
solo_img = sum(1 for v in por_prenda.values()
               if "image" in v and "description" in v and v["image"][0] and not v["description"][0])
solo_txt = sum(1 for v in por_prenda.values()
               if "image" in v and "description" in v and v["description"][0] and not v["image"][0])
disc = solo_img + solo_txt
p = binomial_dos_colas(min(solo_img, solo_txt), disc)
print(f"imagen vs texto (sin defecto duro), {len(por_prenda)} prendas pareadas")
print(f"  solo la imagen sale limpia: {solo_img}   solo el texto: {solo_txt}   "
      f"discordantes: {disc}")
print(f"  McNemar exacto: p = {p:.3f}  ->  "
      f"{'diferencia real' if p < 0.05 else 'indistinguible de ruido'}")

# 2. Tasa de desajuste por costura
print("\ncosturas y desajustes")
print(f"  {'grupo':8} {'costuras/patron':>16} {'desajustes/costura':>20}")
for modo, nombre in (("image", "imagen"), ("description", "texto"), ("corpus", "corpus")):
    datos = [v[modo] for v in por_prenda.values() if modo in v]
    if not datos:
        continue
    cost = sum(d[1] for d in datos)
    des = sum(d[2] for d in datos)
    print(f"  {nombre:8} {cost/len(datos):>16.1f} "
          f"{des/cost if cost else 0:>20.2f}")
