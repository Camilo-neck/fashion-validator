"""Medir cuanto se desajustan las longitudes de los bordes cosidos.

Este fue el banco que destapo el hueco del formato: GarmentCode produce
muchas costuras con longitudes distintas y no dice cuales son fruncidos
buscados y cuales defectos.

Uso (desde el clon de GarmentCode):
    python /ruta/a/research/seamcheck.py 25
"""
import copy
import json
import random
import sys
from collections import Counter

import numpy as np
import yaml

from assets.garment_programs.meta_garment import MetaGarment
from assets.bodies.body_params import BodyParameters
from pattern_sampler import assert_param_combinations
from sampler import randomize

from hilvan import longitud


def check_pattern(pat):
    """Desajuste relativo de cada costura del patron."""
    panels = pat["panels"]
    out = []
    for st in pat["stitches"]:
        lados = [s for s in st if isinstance(s, dict)]
        if len(lados) != 2:
            out.append(("grado_distinto_de_2", None))
            continue
        try:
            L = [longitud(panels[l["panel"]], l["edge"]) for l in lados]
        except (KeyError, IndexError):
            out.append(("referencia_rota", None))
            continue
        mayor = max(L)
        if mayor < 1e-6:
            out.append(("borde_nulo", None))
            continue
        out.append(("medido", abs(L[0] - L[1]) / mayor))
    return out


def generar(n, body, tpl, seed, transformar=None):
    """Genera n patrones que GarmentCode da por validos."""
    random.seed(seed)
    hechos = intentos = 0
    while hechos < n and intentos < n * 25:
        intentos += 1
        d = copy.deepcopy(tpl)
        randomize(d)
        if transformar:
            transformar(d)
        try:
            assert_param_combinations(d)
            piece = MetaGarment(f"s{intentos}", body, d)
            piece.assert_total_length()
            if piece.is_self_intersecting():
                continue
            pattern = piece.assembly()
        except BaseException:
            continue
        hechos += 1
        yield pattern


def main(n, seed=7):
    tpl = yaml.safe_load(open("./assets/design_params/default.yaml"))["design"]
    body = BodyParameters("./assets/bodies/mean_all.yaml")

    estado = Counter()
    rels = []
    patrones = 0
    for pattern in generar(n, body, tpl, seed):
        patrones += 1
        for tag, rel in check_pattern(pattern.pattern):
            estado[tag] += 1
            if rel is not None:
                rels.append(rel)

    a = np.array(rels) if rels else np.array([0.0])
    print(json.dumps({
        "patrones_analizados": patrones,
        "costuras_por_estado": dict(estado),
        "desajuste_relativo": {
            "mediana": round(float(np.median(a)), 6),
            "p90": round(float(np.percentile(a, 90)), 6),
            "max": round(float(a.max()), 6),
            "pct_sobre_1pct": round(float((a > 0.01).mean()) * 100, 2),
            "pct_sobre_5pct": round(float((a > 0.05).mean()) * 100, 2),
            "pct_sobre_15pct": round(float((a > 0.15).mean()) * 100, 2),
        },
    }, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 25)
