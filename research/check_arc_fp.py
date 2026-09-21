"""Contrastar interseccion con arco exacto contra arco linealizado."""
import random, copy, sys, json
import numpy as np
import yaml
from svgpathtools import Line, Arc

from assets.garment_programs.meta_garment import MetaGarment
from assets.bodies.body_params import BodyParameters
from pattern_sampler import assert_param_combinations
from sampler import randomize


from fashion_validator import validar, Limites, segmento


def linealizar(seg, n=40):
    pts = [seg.point(t) for t in np.linspace(0, 1, n)]
    return [Line(a, b) for a, b in zip(pts[:-1], pts[1:])]


def cruza_linealizado(s1, s2, tol_punta=1e-6):
    """True si algun tramo lineal de s1 cruza alguno de s2, ignorando extremos."""
    L1 = linealizar(s1) if not isinstance(s1, Line) else [s1]
    L2 = linealizar(s2) if not isinstance(s2, Line) else [s2]
    p_ini1, p_fin1 = s1.point(0), s1.point(1)
    p_ini2, p_fin2 = s2.point(0), s2.point(1)
    for a in L1:
        for b in L2:
            try:
                xs = a.intersect(b)
            except Exception:
                continue
            for t1, t2 in xs:
                p = a.point(t1)
                # descartar cruces que caen sobre un extremo compartido
                if min(abs(p - p_ini1), abs(p - p_fin1),
                       abs(p - p_ini2), abs(p - p_fin2)) < 0.05:
                    continue
                return True, p
    return False, None


def main(n=30, seed=11):
    random.seed(seed)
    design_tpl = yaml.safe_load(open('./assets/design_params/default.yaml'))['design']
    body = BodyParameters('./assets/bodies/mean_all.yaml')
    hechos = intentos = 0
    reportes = []
    while hechos < n and intentos < n * 30:
        intentos += 1
        d = copy.deepcopy(design_tpl)
        randomize(d)
        try:
            assert_param_combinations(d)
            piece = MetaGarment(f'a{intentos}', body, d)
            piece.assert_total_length()
            if piece.is_self_intersecting():
                continue
            pattern = piece.assembly()
        except BaseException:
            continue
        hechos += 1
        pat = pattern.pattern
        for h in validar({'pattern': pat}, Limites()):
            if h.codigo != 'auto_interseccion':
                continue
            p = pat['panels'][h.panel]
            i, j = h.borde, h.medido['otro_borde']
            s1, s2 = segmento(p, p['edges'][i]), segmento(p, p['edges'][j])
            cruza, punto = cruza_linealizado(s1, s2)
            # comprobar tambien si el radio fue recortado por mi codigo
            recorte = []
            for k in (i, j):
                c = p['edges'][k].get('curvature')
                if isinstance(c, dict) and c.get('type') == 'circle':
                    v = p['vertices']
                    a, b = p['edges'][k]['endpoints']
                    cuerda = abs(complex(*v[a]) - complex(*v[b]))
                    recorte.append({'borde': k, 'radio_json': round(c['params'][0], 2),
                                    'media_cuerda': round(cuerda / 2, 2),
                                    'recortado': bool(c['params'][0] < cuerda / 2)})
            reportes.append({'panel': h.panel, 'bordes': [i, j],
                             'cruces_exactos': h.medido['cruces'],
                             'confirmado_linealizando': cruza,
                             'arcos': recorte})
    print(json.dumps({
        'patrones': hechos,
        'casos_auto_interseccion': len(reportes),
        'confirmados': sum(1 for r in reportes if r['confirmado_linealizando']),
        'detalle': reportes,
    }, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
