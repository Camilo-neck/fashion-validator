"""Aislar casos concretos para distinguir hallazgo real de falso positivo."""
import random, copy, sys, json
import numpy as np
import yaml

from assets.garment_programs.meta_garment import MetaGarment
from assets.bodies.body_params import BodyParameters
from pattern_sampler import assert_param_combinations
from sampler import randomize


from hilvan import validar, Limites, segmento, longitud


def buscar(codigo, n=40, seed=11):
    random.seed(seed)
    design_tpl = yaml.safe_load(open('./assets/design_params/default.yaml'))['design']
    body = BodyParameters('./assets/bodies/mean_all.yaml')
    hechos = intentos = 0
    casos = []
    while hechos < n and intentos < n * 30:
        intentos += 1
        d = copy.deepcopy(design_tpl)
        randomize(d)
        try:
            assert_param_combinations(d)
            piece = MetaGarment(f'i{intentos}', body, d)
            piece.assert_total_length()
            if piece.is_self_intersecting():
                continue
            pattern = piece.assembly()
        except BaseException:
            continue
        hechos += 1
        pat = pattern.pattern
        for h in validar({'pattern': pat}, Limites()):
            if h.codigo == codigo:
                casos.append((h, pat))
    return casos


def detalle_esquina(h, pat):
    p = pat['panels'][h.panel]
    vi = h.medido['vertice']
    inc = [(i, e) for i, e in enumerate(p['edges']) if vi in e['endpoints']]
    print(f"  panel={h.panel} vertice={vi} angulo={h.medido['angulo_grados']}")
    for i, e in inc:
        L = longitud(p, i)
        print(f"    borde {i}: endpoints={e['endpoints']} label={e.get('label','-')} "
              f"largo={L:.2f}cm curv={(e.get('curvature') or {}).get('type','recta')}")
    # un pico de pinza: los dos bordes incidentes son cortos y el vertice es convexo
    otros = [set(e['endpoints']) - {vi} for _, e in inc]
    print(f"    vecinos={[list(o)[0] for o in otros]}")


def detalle_interseccion(h, pat):
    p = pat['panels'][h.panel]
    i, j = h.borde, h.medido['otro_borde']
    print(f"  panel={h.panel} bordes {i} y {j} cruces={h.medido['cruces']}")
    for k in (i, j):
        e = p['edges'][k]
        c = e.get('curvature')
        print(f"    borde {k}: endpoints={e['endpoints']} "
              f"curv={(c or {}).get('type','recta')} params={(c or {}).get('params')}")
        print(f"      largo={longitud(p,k):.2f}cm")


if __name__ == '__main__':
    cod = sys.argv[1]
    casos = buscar(cod, n=int(sys.argv[2]) if len(sys.argv) > 2 else 40)
    print(f'=== {cod}: {len(casos)} casos ===')
    for h, pat in casos[:6]:
        print('-' * 60)
        if cod == 'esquina_aguda':
            detalle_esquina(h, pat)
        elif cod == 'auto_interseccion':
            detalle_interseccion(h, pat)
        else:
            print(' ', h)
    if cod == 'esquina_aguda':
        angs = [h.medido['angulo_grados'] for h, _ in casos]
        a = np.array(angs)
        print('\ndistribucion de angulos:',
              json.dumps({'min': round(float(a.min()), 1),
                          'mediana': round(float(np.median(a)), 1),
                          'p90': round(float(np.percentile(a, 90)), 1),
                          'bajo_5grados': int((a < 5).sum()),
                          'total': len(a)}))
