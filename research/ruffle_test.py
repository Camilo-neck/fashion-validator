"""Comprobar si los desajustes de costura vienen de fruncidos intencionales."""
import random, copy, json, sys
import numpy as np
import yaml
from collections import Counter

from assets.garment_programs.meta_garment import MetaGarment
from assets.bodies.body_params import BodyParameters
from pattern_sampler import assert_param_combinations
from sampler import randomize
from seamcheck import check_pattern


def force_no_ruffle(node):
    """Fija a 1.0 (sin fruncido) todo parametro cuyo nombre contenga 'ruffle'."""
    if not isinstance(node, dict):
        return
    for k, v in node.items():
        if isinstance(v, dict):
            if 'ruffle' in k.lower() and 'type' in v and 'range' in v:
                if v['type'] == 'float':
                    v['v'] = 1.0
                elif v['type'] == 'bool':
                    v['v'] = False
            else:
                force_no_ruffle(v)


def run(n, kill_ruffles, seed):
    random.seed(seed)
    design_tpl = yaml.safe_load(open('./assets/design_params/default.yaml'))['design']
    body = BodyParameters('./assets/bodies/mean_all.yaml')
    rels, done, attempts = [], 0, 0
    while done < n and attempts < n * 25:
        attempts += 1
        d = copy.deepcopy(design_tpl)
        randomize(d)
        if kill_ruffles:
            force_no_ruffle(d)
        try:
            assert_param_combinations(d)
            piece = MetaGarment(f'r{attempts}', body, d)
            piece.assert_total_length()
            if piece.is_self_intersecting():
                continue
            pattern = piece.assembly()
        except BaseException:
            continue
        done += 1
        for tag, rel in check_pattern(pattern.pattern):
            if rel is not None:
                rels.append(rel)
    a = np.array(rels) if rels else np.array([0.0])
    return {
        'patrones': done,
        'costuras_medidas': len(rels),
        'pct_sobre_1pct': round(float((a > 0.01).mean()) * 100, 2),
        'pct_sobre_5pct': round(float((a > 0.05).mean()) * 100, 2),
        'max': round(float(a.max()), 4),
    }


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    print(json.dumps({
        'con_fruncidos': run(n, False, 7),
        'sin_fruncidos': run(n, True, 7),
    }, indent=1, ensure_ascii=False))
