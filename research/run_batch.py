"""Corre el validador sobre patrones que GarmentCode ya dio por validos.

Todo lo que aparezca aqui es algo que GarmentCode no detecta.
"""
import random, copy, json, sys
from collections import Counter

import yaml

from assets.garment_programs.meta_garment import MetaGarment
from assets.bodies.body_params import BodyParameters
from pattern_sampler import assert_param_combinations
from sampler import randomize


from fashion_validator import validar, Limites, resumen


def main(n, seed=11):
    random.seed(seed)
    design_tpl = yaml.safe_load(open('./assets/design_params/default.yaml'))['design']
    body = BodyParameters('./assets/bodies/mean_all.yaml')
    lim = Limites()

    codigos = Counter()
    patrones_con_error = 0
    hechos = 0
    intentos = 0
    ejemplos = {}

    while hechos < n and intentos < n * 30:
        intentos += 1
        d = copy.deepcopy(design_tpl)
        randomize(d)
        try:
            assert_param_combinations(d)
            piece = MetaGarment(f'v{intentos}', body, d)
            piece.assert_total_length()
            if piece.is_self_intersecting():
                continue
            pattern = piece.assembly()
        except BaseException:
            continue

        hechos += 1
        spec = {'pattern': pattern.pattern}
        hs = validar(spec, lim)
        r = resumen(hs)
        if not r['valido']:
            patrones_con_error += 1
        for h in hs:
            if h.severidad in ('error', 'aviso'):
                codigos[f'{h.severidad}:{h.codigo}'] += 1
                if h.codigo not in ejemplos:
                    ejemplos[h.codigo] = str(h)

    print(json.dumps({
        'patrones_validos_para_garmentcode': hechos,
        'de_esos_con_error_para_el_validador': patrones_con_error,
        'pct_rechazados': round(100 * patrones_con_error / hechos, 1) if hechos else 0,
        'hallazgos_por_codigo': dict(codigos.most_common()),
    }, indent=1, ensure_ascii=False))
    print('\n--- un ejemplo de cada tipo ---')
    for c, e in ejemplos.items():
        print(' ', e[:150])


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
