"""Los chequeos de los niveles 0 y 1.

Nivel 0 mira cada panel por separado: que el contorno cierre, que todo sea
cortable y cosible, que no se cruce consigo mismo y que quepa en el rollo.

Nivel 1 mira el grafo de costuras entre paneles: que las referencias existan,
que las longitudes calcen o el desajuste este declarado, que ningun borde se
cosa dos veces y que la prenda sea una sola pieza.
"""

from __future__ import annotations

import math

import numpy as np

from .geometry import (a_complejo, segmento, longitud, radio_curvatura_min,
                       angulos_interiores, ciclos, linealizar, caja,
                       solapan, cruce_real)
from .model import Hallazgo, Limites

__all__ = ["nivel0", "nivel1"]


def _es_pico_de_pinza(edges: list[dict], panel: dict, i0: int, i1: int,
                      lim: Limites) -> bool:
    """Un pico de pinza: dos bordes rectos de longitud practicamente igual.

    Es la firma geometrica de una pinza, que es aguda a proposito. Solo se
    consulta en esquinas concavas: con el angulo interior con signo una pinza
    ya no puede confundirse con una punta, asi que la excepcion no evita
    errores sino avisos. Se mantiene porque las pinzas son construccion
    corriente en faldas y pantalones, y como `muesca_aguda` ahogarian el aviso
    que si importa, el de la ranura asimetrica.
    """
    if edges[i0].get("curvature") or edges[i1].get("curvature"):
        return False
    L0, L1 = longitud(panel, i0), longitud(panel, i1)
    mayor = max(L0, L1)
    if mayor < 1e-9:
        return False
    return abs(L0 - L1) / mayor <= lim.tol_simetria_pinza


def nivel0(pattern: dict, lim: Limites) -> list[Hallazgo]:
    """Validez geometrica de cada panel, por separado."""
    out: list[Hallazgo] = []

    for nombre, panel in pattern["panels"].items():
        verts, edges = panel["vertices"], panel["edges"]
        n_v = len(verts)

        # --- las referencias de vertices existen
        ref_rota = False
        for i, e in enumerate(edges):
            for vi in e["endpoints"]:
                if not (0 <= vi < n_v):
                    out.append(Hallazgo(0, "vertice_inexistente", "error",
                                        f"el borde apunta al vertice {vi}, que no existe "
                                        f"(el panel tiene {n_v})",
                                        panel=nombre, borde=i))
                    ref_rota = True
        if ref_rota:
            continue

        # --- el contorno es un ciclo cerrado
        grado: dict[int, int] = {}
        for e in edges:
            for vi in e["endpoints"]:
                grado[vi] = grado.get(vi, 0) + 1
        malos = [v for v, g in grado.items() if g != 2]
        if malos:
            out.append(Hallazgo(0, "contorno_abierto", "error",
                                f"el contorno no cierra: los vertices {malos[:6]} no tienen "
                                f"exactamente dos bordes",
                                panel=nombre, medido={"vertices_malos": malos[:6]}))
        else:
            # grado 2 en todos los vertices no basta: un panel con un agujero,
            # o dos piezas en una, son dos ciclos y no un contorno
            anillos = ciclos(panel)
            if len(anillos) > 1:
                out.append(Hallazgo(0, "contorno_multiple", "error",
                                    f"los bordes forman {len(anillos)} ciclos separados, no un "
                                    f"solo contorno cerrado",
                                    panel=nombre,
                                    medido={"ciclos": len(anillos),
                                            "bordes_por_ciclo": [len(c) for c in anillos]}))
        huerfanos = [i for i in range(n_v) if i not in grado]
        if huerfanos:
            out.append(Hallazgo(0, "vertice_huerfano", "aviso",
                                f"los vertices {huerfanos[:6]} no los usa ningun borde",
                                panel=nombre, medido={"vertices": huerfanos[:6]}))

        segs = [segmento(panel, e) for e in edges]

        # --- bordes cortables y curvatura cosible
        for i, s in enumerate(segs):
            L = float(s.length())
            if L < lim.largo_min_borde:
                out.append(Hallazgo(0, "borde_degenerado", "error",
                                    f"mide {L:.2f} cm, por debajo del minimo de "
                                    f"{lim.largo_min_borde} cm",
                                    panel=nombre, borde=i, medido={"largo_cm": round(L, 3)}))
            r = radio_curvatura_min(s)
            if r < lim.radio_min_curva:
                out.append(Hallazgo(0, "curvatura_excesiva", "error",
                                    f"radio de curvatura minimo {r:.2f} cm, por debajo de "
                                    f"{lim.radio_min_curva} cm",
                                    panel=nombre, borde=i, medido={"radio_cm": round(r, 3)}))

        # --- esquinas cosibles, reconociendo las pinzas
        incidencias: dict[int, list[tuple[int, bool]]] = {}
        for i, e in enumerate(edges):
            a, b = e["endpoints"]
            incidencias.setdefault(a, []).append((i, True))
            incidencias.setdefault(b, []).append((i, False))

        # El angulo entre las dos tangentes no basta: una punta convexa de 6
        # grados y una muesca concava de 354 dan el mismo valor sin signo, y en
        # patronaje son opuestas. La punta es una lengueta de tela que no se
        # puede coser limpia: defecto duro. La muesca es una ranura hacia
        # dentro del panel, construccion normal (el fondo de una pinza, una
        # abertura): se avisa, porque puede ser un tajo accidental, pero no
        # impide fabricar y queda fuera de DUROS.
        interiores = angulos_interiores(panel, segs)
        for vi, inc in incidencias.items():
            if len(inc) != 2 or vi not in interiores:
                continue
            (i0, _), (i1, _) = inc
            interior = interiores[vi]
            convexa = interior < 180.0
            ang = interior if convexa else 360.0 - interior
            if ang >= lim.angulo_min_esquina:
                continue
            medido = {"vertice": vi, "angulo_grados": round(ang, 2),
                      "angulo_interior_grados": round(interior, 2)}
            # Una pinza apunta hacia dentro del panel: su pico es concavo. Una
            # punta convexa de piernas iguales es una lengueta, no una pinza.
            if (not convexa and lim.permitir_pinzas
                    and _es_pico_de_pinza(edges, panel, i0, i1, lim)):
                out.append(Hallazgo(0, "pico_de_pinza", "info",
                                    f"el vertice {vi} forma {ang:.1f} grados entre dos bordes "
                                    f"rectos de igual longitud: se interpreta como pinza",
                                    panel=nombre, borde=i0, medido=medido))
                continue
            if convexa:
                out.append(Hallazgo(0, "esquina_aguda", "error",
                                    f"el vertice {vi} es una punta de {ang:.1f} grados, por "
                                    f"debajo de {lim.angulo_min_esquina}",
                                    panel=nombre, borde=i0, medido=medido))
            else:
                out.append(Hallazgo(0, "muesca_aguda", "aviso",
                                    f"el vertice {vi} es una muesca hacia dentro de "
                                    f"{ang:.1f} grados de abertura: construccion normal si "
                                    f"es una ranura o una pinza, un tajo si no",
                                    panel=nombre, borde=i0, medido=medido))

        # --- auto-interseccion entre bordes
        #
        # Cada borde se lineariza una sola vez y las parejas cuyas cajas no se
        # tocan se descartan sin mirarlas: era el 96% del tiempo del validador.
        polis = [linealizar(s, lim.muestras_linealizacion) for s in segs]
        cajas = [caja(p) for p in polis]
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                if not solapan(cajas[i], cajas[j], lim.eps_vertice):
                    continue
                comparte = set(edges[i]["endpoints"]) & set(edges[j]["endpoints"])
                extremos = [a_complejo(verts[vi]) for vi in comparte]
                p = cruce_real(polis[i], polis[j], extremos, lim)
                if p is not None:
                    out.append(Hallazgo(0, "auto_interseccion", "error",
                                        f"el borde {i} cruza al borde {j} fuera de un vertice",
                                        panel=nombre, borde=i,
                                        medido={"otro_borde": j,
                                                "punto": [round(p.real, 2), round(p.imag, 2)]}))

        # --- cabe en el ancho del rollo
        pts = np.array([[p.real, p.imag]
                        for s in segs
                        for p in (s.point(t) for t in np.linspace(0, 1, 12))])
        if len(pts):
            ancho = float(pts[:, 0].max() - pts[:, 0].min())
            alto = float(pts[:, 1].max() - pts[:, 1].min())
            if min(ancho, alto) > lim.ancho_rollo:
                out.append(Hallazgo(0, "excede_ancho_rollo", "error",
                                    f"el panel mide {ancho:.0f} x {alto:.0f} cm y no cabe en un "
                                    f"rollo de {lim.ancho_rollo} cm ni girandolo",
                                    panel=nombre,
                                    medido={"ancho_cm": round(ancho, 1),
                                            "alto_cm": round(alto, 1)}))
    return out


# Como se emparejan los extremos de los dos bordes de una costura. `direct`
# cose el primer extremo de uno con el primero del otro; `reversed`, con el
# segundo. No se puede contrastar contra la geometria -- por eso hay que
# declararlo -- asi que solo se valida que el valor exista.
PARES = {"direct": ((0, 0), (1, 1)), "reversed": ((0, 1), (1, 0))}


def _esquina(panel: dict, interiores: dict, v: int, idx: int):
    """El otro borde que llega al vertice `v`, y el angulo interior del panel ahi.

    El angulo es el interior con signo, no el que forman las dos tangentes: la
    suma alfa + beta de la continuidad solo vale 180 si cada termino dice de que
    lado queda la tela. Devuelve None si el vertice no tiene exactamente dos
    bordes: ese caso ya lo reporta el nivel 0 como contorno abierto.
    """
    inc = [i for i, e in enumerate(panel["edges"]) if v in e["endpoints"]]
    if len(inc) != 2 or idx not in inc or v not in interiores:
        return None
    vecino = inc[0] if inc[1] == idx else inc[1]
    return interiores[v], vecino


def _continuidad(pattern: dict, uso: dict, lim: Limites) -> list[Hallazgo]:
    """Continuidad del contorno libre en los cruces de costura.

    En la prenda montada los dos paneles de una costura quedan a lado y lado.
    Donde la costura termina, el contorno libre pasa del borde vecino de un
    panel al del otro, y el angulo que recorre es la suma de los dos angulos
    interiores: vale 180 grados cuando el escote sigue suave.

    El formato de GarmentCode no dice que extremo de un borde se cose con cual
    del otro, y no se puede deducir: la colocacion 3D del JSON es la posicion
    inicial para el simulador y deja los paneles separados. La costura puede
    declararlo con `orient`; sin declaracion se prueban los dos
    emparejamientos, se elige el que mejor deja al patron y solo se reporta el
    quiebre que ninguno explica. Cada hallazgo dice de cual de los dos casos
    viene, porque el deducido es una cota inferior y el declarado no.
    """
    out: list[Hallazgo] = []
    panels = pattern["panels"]
    cache: dict[str, dict] = {}

    def interiores(nombre: str) -> dict:
        if nombre not in cache:
            p = panels[nombre]
            cache[nombre] = angulos_interiores(p, [segmento(p, e) for e in p["edges"]])
        return cache[nombre]

    for si, st in enumerate(pattern.get("stitches", [])):
        lados = [s for s in st if isinstance(s, dict)]
        if len(lados) != 2:
            continue

        orient = next((l["orient"] for l in lados if l.get("orient") is not None), None)
        if orient is not None and orient not in PARES:
            out.append(Hallazgo(
                1, "orientacion_incongruente", "error",
                f"declara la orientacion '{orient}', que no es "
                f"{' ni '.join(PARES)}",
                costura=si, medido={"orient": orient}))
            orient = None

        try:
            datos = [(l["panel"], panels[l["panel"]], l["edge"],
                      panels[l["panel"]]["edges"][l["edge"]]["endpoints"])
                     for l in lados]
            esquinas = [[_esquina(p, interiores(n), v, i) for v in eps]
                        for n, p, i, eps in datos]
        except (KeyError, IndexError, TypeError):
            continue  # referencia rota: ya lo reporta el resto del nivel 1
        if any(e is None for par in esquinas for e in par):
            continue

        (nA, pA, _, _), (nB, pB, _, _) = datos

        def evaluar(par):
            res = []
            for ia, ib in par:
                angA, vecA = esquinas[0][ia]
                angB, vecB = esquinas[1][ib]
                # solo el contorno libre: si un vecino esta cosido, ese cruce
                # cae dentro de la prenda y no es el escote ni el bajo
                if (nA, vecA) in uso or (nB, vecB) in uso:
                    continue
                res.append((abs(angA + angB - 180.0), vecA, vecB, angA, angB))
            return res

        if orient is not None:
            otro = "reversed" if orient == "direct" else "direct"
            mejor, alterna = evaluar(PARES[orient]), evaluar(PARES[otro])
            # un borde libre solo puede continuar en otro borde libre: si la
            # otra orientacion encaja mas, la declarada contradice la topologia
            if len(alterna) > len(mejor):
                out.append(Hallazgo(
                    1, "orientacion_dudosa", "aviso",
                    f"declara '{orient}', pero con '{otro}' el contorno libre continua "
                    f"en {len(alterna)} cruces en vez de {len(mejor)}: un borde sin coser "
                    f"solo puede seguir en otro borde sin coser",
                    costura=si, medido={"declarada": orient, "cruces_declarada": len(mejor),
                                        "alternativa": otro, "cruces_alternativa": len(alterna)}))
        else:
            # un borde libre solo puede continuar en otro borde libre, asi que
            # el emparejamiento que case mas vecinos libres es el fisicamente
            # coherente; a igualdad, el que menos quiebre deje
            mejor = min((evaluar(PARES["direct"]), evaluar(PARES["reversed"])),
                        key=lambda r: (-len(r), sum(x[0] for x in r)))

        for desv, vecA, vecB, angA, angB in mejor:
            if desv <= lim.angulo_max_quiebre:
                continue
            medido = {"desviacion_grados": round(desv, 2),
                      "angulo_a_grados": round(angA, 2),
                      "angulo_b_grados": round(angB, 2),
                      "vecinos": [f"{nA}.{vecA}", f"{nB}.{vecB}"],
                      "emparejamiento": "declarado" if orient else "deducido"}
            recto = not (pA["edges"][vecA].get("curvature")
                         or pB["edges"][vecB].get("curvature"))
            if lim.permitir_esquinas_rectas and recto:
                out.append(Hallazgo(
                    1, "esquina_de_diseno", "info",
                    f"el contorno gira {desv:.1f} grados entre dos bordes rectos "
                    f"({nA}.{vecA} y {nB}.{vecB}): se interpreta como esquina "
                    f"dibujada, no como un quiebre accidental",
                    costura=si, medido=medido))
                continue
            out.append(Hallazgo(
                1, "quiebre_en_cruce", "aviso",
                f"al unir los paneles el contorno pasa de {nA}.{vecA} a {nB}.{vecB} "
                f"formando {angA + angB:.1f} grados en vez de 180 ({desv:.1f} de "
                f"quiebre): la linea no sigue suave al cruzar la costura",
                costura=si, medido=medido))
    return out


TIPOS_ACABADO = ("hem", "facing", "binding", "opening", "raw")



def _acabados(panels: dict, uso: dict) -> list[Hallazgo]:
    """Acabado declarado de los bordes que no se cosen.

    Un borde sin coser puede ser un dobladillo, una vista, un ribete, una
    abertura o un borde crudo a proposito, y el formato de GarmentCode no tiene
    donde decir cual. Es el mismo hueco que `ease` cierra para los fruncidos:
    sin la declaracion, un bajo bien rematado y un borde olvidado son el mismo
    dato.

    El borde declara su acabado en el propio panel:

        {"endpoints": [3, 4], "finish": {"type": "hem"}}

    Declarado y coherente, el patron es valido. Declarado sobre un borde que si
    se cose, se reporta `acabado_incongruente`. Sin declarar, queda un aviso.

    Sin declarar NO es error, a diferencia del desajuste de costura: alli hay un
    disparador geometrico (los largos no calzan) y aqui no, asi que marcarlo
    como error invalidaria el 100% de los patrones existentes de golpe, que es
    justo el fallo del que este validador ya salio una vez.
    """
    out: list[Hallazgo] = []
    sin_declarar: list[str] = []
    declarados = 0

    for nombre, panel in panels.items():
        for i, e in enumerate(panel["edges"]):
            acabado = e.get("finish")
            cosido = (nombre, i) in uso

            if acabado is None:
                if not cosido:
                    sin_declarar.append(f"{nombre}.{i}")
                continue

            tipo = acabado.get("type") if isinstance(acabado, dict) else None
            if cosido:
                out.append(Hallazgo(
                    1, "acabado_incongruente", "error",
                    f"declara el acabado '{tipo}' pero el borde esta cosido en la costura "
                    f"{uso[(nombre, i)][0]}: un borde cosido no lleva acabado",
                    panel=nombre, borde=i,
                    medido={"acabado": tipo, "costuras": uso[(nombre, i)]}))
            elif tipo not in TIPOS_ACABADO:
                out.append(Hallazgo(
                    1, "acabado_incongruente", "error",
                    f"declara el acabado '{tipo}', que no es ninguno de "
                    f"{', '.join(TIPOS_ACABADO)}",
                    panel=nombre, borde=i, medido={"acabado": tipo}))
            else:
                declarados += 1

    if sin_declarar:
        out.append(Hallazgo(
            1, "acabado_no_declarado", "aviso",
            f"{len(sin_declarar)} bordes no estan cosidos y no dicen como se rematan: "
            f"sin esa declaracion no hay forma de distinguir un dobladillo de un borde "
            f"olvidado",
            medido={"cuantos": len(sin_declarar), "bordes": sin_declarar[:12],
                    "declarados": declarados}))
    return out


def nivel1(pattern: dict, lim: Limites) -> list[Hallazgo]:
    """Coherencia del grafo de costuras entre paneles."""
    out: list[Hallazgo] = []
    panels = pattern["panels"]
    stitches = pattern.get("stitches", [])

    uso: dict[tuple[str, int], list[int]] = {}

    for si, st in enumerate(stitches):
        lados = [s for s in st if isinstance(s, dict)]
        if len(lados) != 2:
            out.append(Hallazgo(1, "costura_no_binaria", "error",
                                f"une {len(lados)} bordes; una costura une exactamente dos",
                                costura=si, medido={"lados": len(lados)}))
            continue

        # --- las referencias existen
        ok = True
        for lado in lados:
            p = panels.get(lado["panel"])
            if p is None:
                out.append(Hallazgo(1, "panel_inexistente", "error",
                                    f"apunta al panel '{lado['panel']}', que no esta en el patron",
                                    costura=si))
                ok = False
            elif not (0 <= lado["edge"] < len(p["edges"])):
                out.append(Hallazgo(1, "borde_inexistente", "error",
                                    f"apunta al borde {lado['edge']} de '{lado['panel']}', "
                                    f"que solo tiene {len(p['edges'])}",
                                    costura=si))
                ok = False
        if not ok:
            continue

        for lado in lados:
            uso.setdefault((lado["panel"], lado["edge"]), []).append(si)

        # --- longitudes: calzan, o el desajuste esta declarado
        L = [longitud(panels[l["panel"]], l["edge"]) for l in lados]
        mayor, menor = max(L), min(L)
        if mayor < 1e-6:
            out.append(Hallazgo(1, "costura_nula", "error",
                                "los dos bordes tienen longitud cero", costura=si))
            continue

        rel = abs(L[0] - L[1]) / mayor
        declaracion = next((l["ease"] for l in lados if isinstance(l.get("ease"), dict)), None)

        if declaracion is None:
            if rel > lim.umbral_fruncido:
                # tan grande que casi seguro es deliberado, pero nadie lo declaro
                out.append(Hallazgo(
                    1, "fruncido_no_declarado", "aviso",
                    f"los bordes miden {L[0]:.2f} y {L[1]:.2f} cm ({rel * 100:.1f}% de "
                    f"diferencia): parece un fruncido intencional, pero el patron no lo "
                    f"declara y no hay forma de distinguirlo de un defecto",
                    costura=si,
                    medido={"largo_a_cm": round(L[0], 2), "largo_b_cm": round(L[1], 2),
                            "desajuste_rel": round(rel, 4), "desajuste_rel_exacto": rel,
                            "ratio": round(mayor / menor, 3) if menor > 1e-9 else None}))
            elif rel > lim.tol_costura:
                # demasiado grande para ser redondeo, demasiado chico para ser fruncido
                out.append(Hallazgo(
                    1, "desajuste_no_declarado", "error",
                    f"los bordes miden {L[0]:.2f} y {L[1]:.2f} cm ({rel * 100:.1f}% de "
                    f"diferencia) y no hay declaracion de fruncido o embebido",
                    costura=si,
                    medido={"largo_a_cm": round(L[0], 2), "largo_b_cm": round(L[1], 2),
                            "desajuste_rel": round(rel, 4),
                            "desajuste_rel_exacto": rel}))
        else:
            ratio_decl = float(declaracion.get("ratio", 1.0))
            tol = float(declaracion.get("tol", lim.tol_ease_default))
            ratio_real = mayor / menor if menor > 1e-9 else math.inf
            if abs(ratio_real - ratio_decl) > tol * max(1.0, ratio_decl):
                out.append(Hallazgo(
                    1, "ease_incongruente", "error",
                    f"declara un {declaracion.get('type', 'ease')} de {ratio_decl:.2f} pero la "
                    f"geometria da {ratio_real:.2f}",
                    costura=si,
                    medido={"ratio_declarado": round(ratio_decl, 3),
                            "ratio_real": round(ratio_real, 3)}))

    # --- ningun borde cosido dos veces
    for (pn, ei), sis in uso.items():
        if len(sis) > 1:
            out.append(Hallazgo(1, "borde_multicosido", "error",
                                f"este borde aparece en las costuras {sis}; un borde se cose "
                                f"una sola vez",
                                panel=pn, borde=ei, medido={"costuras": sis}))

    # --- paneles sin ninguna costura
    cosidos = {p for (p, _) in uso}
    for nombre in panels:
        if nombre not in cosidos:
            out.append(Hallazgo(1, "panel_suelto", "error",
                                "el panel no esta cosido a nada", panel=nombre))

    # --- la prenda es una sola pieza conectada
    padre: dict[str, str] = {n: n for n in panels}

    def raiz(x: str) -> str:
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    en_redondo: list[int] = []
    for si, st in enumerate(stitches):
        lados = [s for s in st if isinstance(s, dict)]
        if len(lados) == 2 and all(l["panel"] in padre for l in lados):
            pa, pb = lados[0]["panel"], lados[1]["panel"]
            ra, rb = raiz(pa), raiz(pb)
            if ra != rb:
                padre[ra] = rb
            elif pa != pb:
                # los dos paneles ya estaban unidos por otro camino: al llegar
                # aqui esta costura cierra un tubo y hay que coserla en redondo
                en_redondo.append(si)

    grupos: dict[str, list[str]] = {}
    for n in panels:
        grupos.setdefault(raiz(n), []).append(n)
    if len(grupos) > 1:
        tam = sorted((len(v) for v in grupos.values()), reverse=True)
        out.append(Hallazgo(1, "prenda_desconectada", "aviso",
                            f"los paneles forman {len(grupos)} grupos separados (tamanos {tam}); "
                            f"puede ser un conjunto de varias prendas o un error de costura",
                            medido={"grupos": len(grupos), "tamanos": tam}))

    # --- secuencia de ensamblaje: cuanto hay que coser en redondo
    #
    # Siempre existe UN orden para coser un grafo conectado, asi que la
    # pregunta util no es si existe sino cuanto cuesta. Toda costura que une
    # dos paneles ya unidos por otro camino cierra un tubo, y coser en redondo
    # es mas lento y necesita otro montaje de maquina. Cuales son depende del
    # orden que se elija; cuantas son, no: es E - V + C del grafo de costuras.
    #
    # ponytail: la factibilidad real es accesibilidad (que la aguja llegue), y
    # eso necesita la prenda en 3D. Esto mide el coste, no la imposibilidad.
    if en_redondo:
        out.append(Hallazgo(1, "costuras_en_redondo", "info",
                            f"{len(en_redondo)} de {len(stitches)} costuras cierran un tubo y "
                            f"hay que coserlas en redondo; las demas se pueden coser en plano",
                            medido={"cuantas": len(en_redondo),
                                    "un_orden_posible": en_redondo[:12]}))

    # --- continuidad del contorno al cruzar una costura
    out += _continuidad(pattern, uso, lim)

    # --- acabado de los bordes que no se cosen
    out += _acabados(panels, uso)

    # --- bordes libres, para revision humana
    libres = sum(1 for n, p in panels.items()
                 for i in range(len(p["edges"])) if (n, i) not in uso)
    total = sum(len(p["edges"]) for p in panels.values())
    if libres:
        out.append(Hallazgo(1, "bordes_libres", "info",
                            f"{libres} de {total} bordes no estan cosidos: son el contorno "
                            f"visible de la prenda",
                            medido={"libres": libres, "total": total}))
    return out
