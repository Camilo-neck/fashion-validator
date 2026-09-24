"""¿Los bordes cortos son defectos o artefactos de vertice que un CAD fusiona?

    python research/fusion_vertices.py data/garmentcodedata_0

Un borde de 0,2 mm en un patron neto puede ser un vertice casi duplicado que
cualquier CAD fusionaria al importar, no algo imposible de cortar. Este script
colapsa, en cada panel, los bordes mas cortos que eps (sus dos vertices pasan a
ser uno, en el punto medio) y vuelve a validar. Una costura que usaba un borde
colapsado desaparece, porque ya no tiene nada que coser; se cuentan aparte.

Escribe `docs/paper/figs/fusion.json`.
"""
import copy
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "src")
from hilvan import DUROS, Limites, validar
from hilvan.geometry import longitud

EPS = (0.05, 0.1, 0.25, 0.5)
LIM = Limites()


def fusionar(pattern, eps):
    """Copia del patron con los bordes < eps colapsados. Devuelve (patron, costuras_perdidas)."""
    pat = copy.deepcopy(pattern)
    perdidas = 0
    for nombre, panel in pat["panels"].items():
        while True:
            corto = next((i for i in range(len(panel["edges"]))
                          if len(panel["edges"]) > 3 and longitud(panel, i) < eps), None)
            if corto is None:
                break
            a, b = panel["edges"][corto]["endpoints"]
            va, vb = panel["vertices"][a], panel["vertices"][b]
            panel["vertices"][a] = [(va[0] + vb[0]) / 2, (va[1] + vb[1]) / 2]
            del panel["edges"][corto]
            for e in panel["edges"]:
                e["endpoints"] = [a if v == b else v for v in e["endpoints"]]
            # las costuras: la del borde colapsado se va, las demas se renumeran
            nuevas = []
            for st in pat.get("stitches", []):
                lados = [s for s in st if isinstance(s, dict)]
                if any(l["panel"] == nombre and l["edge"] == corto for l in lados):
                    perdidas += 1
                    continue
                for l in lados:
                    if l["panel"] == nombre and l["edge"] > corto:
                        l["edge"] -= 1
                nuevas.append(st)
            pat["stitches"] = nuevas
    return pat, perdidas


def clases(pattern):
    return {h.codigo for h in validar({"pattern": pattern}, LIM)
            if h.severidad == "error" and h.codigo in DUROS}


def demo():
    """Un cuadrado con un borde de 0,1 mm: con eps 0,05 cm queda en cuatro bordes."""
    pan = {"vertices": [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0.01]],
           "edges": [{"endpoints": [0, 1]}, {"endpoints": [1, 2]}, {"endpoints": [2, 3]},
                     {"endpoints": [3, 4]}, {"endpoints": [4, 0]}]}
    pat = {"panels": {"p": pan, "q": copy.deepcopy(pan)},
           "stitches": [[{"panel": "p", "edge": 4}, {"panel": "q", "edge": 4}],
                        [{"panel": "p", "edge": 1}, {"panel": "q", "edge": 3}]]}
    assert "borde_degenerado" in clases(pat)
    f, perdidas = fusionar(pat, 0.05)
    assert len(f["panels"]["p"]["edges"]) == 4 and perdidas == 1
    assert f["stitches"] == [[{"panel": "p", "edge": 1}, {"panel": "q", "edge": 3}]]
    assert "borde_degenerado" not in clases(f)
    print("demo ok")


if __name__ == "__main__":
    if sys.argv[1] == "--demo":
        sys.exit(demo())
    rutas = sorted(Path(sys.argv[1]).glob("*specification.json"))
    pats = [json.loads(r.read_text(encoding="utf-8")) for r in rutas]
    pats = [p.get("pattern", p) for p in pats]
    base = [clases(p) for p in pats]
    salida = {"patrones": len(pats),
              "eps_0": {"pct_duro": round(100 * sum(map(bool, base)) / len(pats), 2),
                        "por_clase": dict(Counter(c for b in base for c in b))}}
    for eps in EPS:
        res, perdidas, afectados = [], 0, 0
        for p in pats:
            f, n = fusionar(p, eps)
            perdidas += n
            afectados += n > 0
            res.append(clases(f))
        salida[f"eps_{eps}"] = {
            "pct_duro": round(100 * sum(map(bool, res)) / len(pats), 2),
            "por_clase": dict(Counter(c for b in res for c in b)),
            "costuras_perdidas": perdidas, "patrones_con_costura_perdida": afectados}
        print(eps, salida[f"eps_{eps}"], flush=True)
    Path("docs/paper/figs/fusion.json").write_text(json.dumps(salida, indent=1), encoding="utf-8")
    print(json.dumps(salida, indent=1))
