"""Las cifras del texto del paper, medidas sobre el corpus y no copiadas.

    python research/numeros_paper.py data/garmentcodedata_0 data/garmentcodedata_0_random

Complementa a `figuras_paper.py`, que produce los numeros de las figuras. Este
cubre el resto: la tabla de resultados, las clases de defecto duro, los
margenes contra el umbral, la comparacion pareada entre cuerpos, el convenio
de orientacion y las aberturas del nivel 2. Escribe
`docs/paper/figs/numeros_texto.json`.
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, "src")
from hilvan import DUROS, Limites, validar
from hilvan.checks import PARES, _esquina
from hilvan.geometry import segmento

LIM = Limites()
DESAJUSTE = ("desajuste_no_declarado", "fruncido_no_declarado")


def cruces_libres(pattern):
    """Cruces de contorno libre que explica cada orientacion, sumados por patron.

    Un borde libre solo puede continuar en otro borde libre, asi que la
    orientacion que case mas vecinos libres a traves de las costuras es la
    fisicamente coherente. Es el mismo criterio que `checks._continuidad`.
    """
    panels = pattern["panels"]
    uso = {(s["panel"], s["edge"]) for st in pattern.get("stitches", [])
           for s in st if isinstance(s, dict)}
    segs = {n: [segmento(p, e) for e in p["edges"]] for n, p in panels.items()}
    total = {"direct": 0, "reversed": 0}
    for st in pattern.get("stitches", []):
        lados = [s for s in st if isinstance(s, dict)]
        if len(lados) != 2:
            continue
        try:
            datos = [(l["panel"], l["edge"],
                      panels[l["panel"]]["edges"][l["edge"]]["endpoints"]) for l in lados]
            esq = [[_esquina(panels[n], segs[n], v, i) for v in eps] for n, i, eps in datos]
        except (KeyError, IndexError, TypeError):
            continue
        if any(e is None for par in esq for e in par):
            continue
        (nA, _, _), (nB, _, _) = datos
        for nombre, par in PARES.items():
            total[nombre] += sum(1 for ia, ib in par
                                 if (nA, esq[0][ia][1]) not in uso
                                 and (nB, esq[1][ib][1]) not in uso)
    return total


def medir(carpeta, orientacion=False):
    filas = {}
    for r in sorted(Path(carpeta).glob("*specification.json")):
        spec = json.loads(r.read_text(encoding="utf-8"))
        pat = spec.get("pattern", spec)
        hs = validar(spec, LIM)
        errs = [h for h in hs if h.severidad == "error"]
        fila = {
            "costuras": len(pat.get("stitches", [])),
            "errores": len(errs),
            "duros": Counter(h.codigo for h in errs if h.codigo in DUROS),
            "bordes_cortos": [h.medido["largo_cm"] for h in hs if h.codigo == "borde_degenerado"],
            "esquinas": [h.medido["angulo_grados"] for h in hs if h.codigo == "esquina_aguda"],
            "desajustes": [h.medido["desajuste_rel"] for h in hs if h.codigo in DESAJUSTE],
            "aberturas": [h.medido["contorno_cm"] for h in hs
                          if h.nivel == 2 and h.codigo == "abertura"],
            "montaje_incoherente": any(h.codigo == "montaje_incoherente" for h in hs),
        }
        if orientacion:
            fila["orient"] = cruces_libres(pat)
        filas[r.name.replace("_specification.json", "")] = fila
    return filas


def pct(a, b):
    return round(100 * a / b, 2) if b else None


def cuantiles(v, qs=(10, 25, 50, 75, 90)):
    return {f"p{q}": round(float(np.percentile(v, q)), 4) for q in qs} | {
        "min": round(float(min(v)), 4), "n": len(v)} if v else {}


def mcnemar_exacto(b, c):
    n = b + c
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def resumen(filas):
    n = len(filas)
    duro = [k for k, f in filas.items() if f["duros"]]
    limpio = [k for k, f in filas.items() if f["errores"] == 0]
    por_clase = Counter()
    casos = Counter()
    for f in filas.values():
        for c, m in f["duros"].items():
            por_clase[c] += 1
            casos[c] += m
    todos = lambda campo: [x for f in filas.values() for x in f[campo]]
    cortos, esquinas, desaj = todos("bordes_cortos"), todos("esquinas"), todos("desajustes")
    desaj_err = [x for x in desaj if x <= LIM.umbral_fruncido]
    return {
        "patrones": n,
        "con_defecto_duro": len(duro), "pct_defecto_duro": pct(len(duro), n),
        "solo_intencion": n - len(duro) - len(limpio),
        "pct_solo_intencion": pct(n - len(duro) - len(limpio), n),
        "cero_errores": len(limpio), "pct_cero_errores": pct(len(limpio), n),
        "clases_duras": {c: {"patrones": por_clase[c], "casos": casos[c]}
                         for c in sorted(DUROS)},
        "errores_por_costura": round(sum(f["errores"] for f in filas.values())
                                     / sum(max(f["costuras"], 1) for f in filas.values()), 4),
        "borde_corto_cm": cuantiles(cortos),
        "esquina_aguda_grados": cuantiles(esquinas),
        # desajuste_no_declarado es la zona de error (1-15%): la de la tabla de margenes
        "desajuste_error_rel": cuantiles(desaj_err),
        "desajuste_todos_rel": cuantiles(desaj) | {
            "frac_sobre_umbral_fruncido": round(sum(x > LIM.umbral_fruncido for x in desaj)
                                                / len(desaj), 4)},
    }


def orientacion(filas):
    rev = dire = emp = 0
    ventaja = []
    for f in filas.values():
        d, r = f["orient"]["direct"], f["orient"]["reversed"]
        if r > d:
            rev += 1
            ventaja.append(r - d)
        elif d > r:
            dire += 1
        else:
            emp += 1
    n = len(filas)
    return {"favorecen_reversed": rev, "favorecen_direct": dire, "empate": emp,
            "pct_reversed": pct(rev, n), "pct_empate": pct(emp, n),
            "mediana_ventaja_reversed": float(np.median(ventaja)) if ventaja else None}


def pareado(neutro, aleatorio):
    comunes = sorted(set(neutro) & set(aleatorio))
    n = len(comunes)
    a = lambda k, d: bool(d[k]["duros"])
    ambos = sum(1 for k in comunes if a(k, neutro) and a(k, aleatorio))
    solo_n = sum(1 for k in comunes if a(k, neutro) and not a(k, aleatorio))
    solo_a = sum(1 for k in comunes if a(k, aleatorio) and not a(k, neutro))
    ninguno = n - ambos - solo_n - solo_a
    # diferencia pareada de proporciones (aleatorio - neutro), IC de Wald
    dif = (solo_a - solo_n) / n
    ee = math.sqrt((solo_a + solo_n) - (solo_a - solo_n) ** 2 / n) / n
    tasa_n, tasa_a = (solo_n + ambos) / n, (solo_a + ambos) / n
    esperado = n * tasa_n * tasa_a
    return {
        "disenos_pareados": n, "limpios_ambos": ninguno, "rotos_ambos": ambos,
        "solo_neutro": solo_n, "solo_aleatorio": solo_a,
        "rotos_alguno": ambos + solo_n + solo_a,
        "mcnemar_p": round(mcnemar_exacto(solo_a, solo_n), 4),
        "dif_pareada_pp": round(100 * dif, 3),
        "ic95_pp": [round(100 * (dif - 1.96 * ee), 3), round(100 * (dif + 1.96 * ee), 3)],
        "tasa_neutro_pct": round(100 * tasa_n, 2), "tasa_aleatorio_pct": round(100 * tasa_a, 2),
        "esperado_ambos_si_independiente": round(esperado, 1),
        "observado_sobre_esperado": round(ambos / esperado, 2),
    }


def aberturas(filas):
    coherentes = [f for f in filas.values() if not f["montaje_incoherente"]]
    minimo = [min(f["aberturas"]) for f in coherentes if f["aberturas"]]
    maximo = [max(f["aberturas"]) for f in coherentes if f["aberturas"]]
    cuerpo = __import__("hilvan").Cuerpo()
    return {
        "montaje_coherente": len(coherentes), "pct_coherente": pct(len(coherentes), len(filas)),
        "aberturas_por_patron_mediana": float(np.median([len(f["aberturas"]) for f in coherentes])),
        "menor_abertura_cm": cuantiles(minimo), "mayor_abertura_cm": cuantiles(maximo),
        "patrones_con_abertura_bajo_mano": sum(1 for m in minimo if m < cuerpo.hand),
        "patrones_mayor_abertura_bajo_cabeza": sum(1 for m in maximo if m < cuerpo.head),
        "cuerpo_referencia_cm": {"head": cuerpo.head, "hand": cuerpo.hand},
    }


if __name__ == "__main__":
    neutro = medir(sys.argv[1], orientacion=True)
    aleatorio = medir(sys.argv[2])
    numeros = {"neutro": resumen(neutro), "aleatorio": resumen(aleatorio),
               "pareado": pareado(neutro, aleatorio),
               "orientacion": orientacion(neutro),
               "nivel2_neutro": aberturas(neutro)}
    destino = Path("docs/paper/figs/numeros_texto.json")
    destino.write_text(json.dumps(numeros, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(numeros, indent=1, ensure_ascii=False))
