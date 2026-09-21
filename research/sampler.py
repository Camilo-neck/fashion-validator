"""Fase 1: medir la tasa de patrones válidos de GarmentCode sobre el cuerpo neutro."""
import random, copy, json, traceback, sys
from collections import Counter
import yaml

from assets.garment_programs.meta_garment import MetaGarment, IncorrectElementConfiguration
from assets.bodies.body_params import BodyParameters
from pattern_sampler import assert_param_combinations


def randomize(node):
    """Recorre el arbol de parametros y asigna un valor aleatorio a cada hoja."""
    if not isinstance(node, dict):
        return
    if 'type' in node and 'range' in node:
        t, rng = node['type'], node['range']
        if t == 'float':
            node['v'] = random.uniform(rng[0], rng[1])
        elif t == 'int':
            node['v'] = random.randint(rng[0], rng[1])
        elif t == 'bool':
            node['v'] = random.random() < 0.5
        elif t in ('select', 'select_null'):
            p = node.get('default_prob')
            if p is not None and random.random() < p:
                node['v'] = node.get('default', rng[0])
            else:
                node['v'] = random.choice(rng)
        return
    for v in node.values():
        randomize(v)


def classify(exc):
    m = str(exc)
    if isinstance(exc, IncorrectElementConfiguration):
        return 'config_invalida:' + m.split('::')[-1][:40]
    return type(exc).__name__ + ': ' + m[:60]


def main(n):
    design_tpl = yaml.safe_load(open('./assets/design_params/default.yaml'))['design']
    body = BodyParameters('./assets/bodies/mean_all.yaml')

    counts = Counter()
    reasons = Counter()
    panel_counts = []

    for i in range(n):
        d = copy.deepcopy(design_tpl)
        randomize(d)
        try:
            assert_param_combinations(d)
            piece = MetaGarment(f's{i}', body, d)
            piece.assert_total_length()
            if piece.is_self_intersecting():
                counts['auto_interseccion'] += 1
                continue
            pattern = piece.assembly()
            spec = pattern.spec if hasattr(pattern, 'spec') else None
            counts['ok'] += 1
            try:
                panel_counts.append(len(pattern.pattern['panels']))
            except Exception:
                pass
        except BaseException as e:
            counts['error'] += 1
            reasons[classify(e)] += 1

    total = sum(counts.values())
    print(json.dumps({
        'total': total,
        'counts': dict(counts),
        'tasa_ok': round(counts['ok'] / total, 3) if total else 0,
        'top_errores': reasons.most_common(12),
        'paneles_prom': round(sum(panel_counts) / len(panel_counts), 1) if panel_counts else None,
        'paneles_max': max(panel_counts) if panel_counts else None,
    }, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    random.seed(42)
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 100)
