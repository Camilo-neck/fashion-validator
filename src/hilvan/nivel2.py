"""Nivel 2 sin simulacion: vestibilidad por geometria.

Que una prenda se pueda poner no necesita fisica. Los bordes que no se cosen
forman bucles cerrados en la prenda montada -- el escote, el bajo, los punos --
y el contorno de cada uno es la suma de las longitudes de sus bordes, que se
calcula exacto. Comparado con una medida del cuerpo, eso responde si la cabeza
pasa por el escote.

Lo que si necesita simulacion -- drapeado, mapas de tension, poses -- no esta
aqui: ver `docs/nivel2-simulado.md`.

**El montaje depende de la orientacion de las costuras.** Con la orientacion
equivocada, los cuatro huecos de una camiseta salen como dos bucles de 129,6 cm
y cualquier medida construida encima no significa nada. Ninguno de los cinco
criterios que se probaron la recupera del archivo: la colocacion 3D es la
posicion inicial del simulador, la forma de los bordes cosidos es recta o
simetrica, el contorno cierra igual con cualquier convenio, las cadenas de
esquina son coherentes con los dos, y la suma de 360 grados en una esquina
interior no vale porque una falda con godets es conica a proposito.

Asi que la orientacion se declara con `orient` en la costura. Sin declarar se
usa `lim.orientacion_por_defecto`, que es el convenio observado en la salida de
GarmentCode, y el montaje queda marcado como supuesto: entonces los contornos
se informan pero no se juzga nada contra el cuerpo.
"""

from __future__ import annotations

from collections import defaultdict

from .geometry import longitud
from .model import Cuerpo, Hallazgo, Limites

__all__ = ["nivel2", "bucles_libres"]

PARES = {"direct": (0, 1), "reversed": (1, 0)}


def _montaje(pattern: dict, lim: Limites):
    """Pega las esquinas de la prenda y traza los bucles del contorno libre.

    Cada extremo de borde es un nodo `(panel, borde, cual)`. Dos extremos
    quedan en la misma esquina montada si son la esquina de un panel o si estan
    cosidos. Devuelve los bucles, cuantas costuras declararon orientacion y las
    esquinas cuya paridad de bordes libres es imposible.
    """
    panels = pattern["panels"]
    uso = {(s["panel"], s["edge"]) for st in pattern.get("stitches", [])
           for s in st if isinstance(s, dict)}

    padre: dict = {}

    def raiz(x):
        padre.setdefault(x, x)
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    def une(a, b):
        ra, rb = raiz(a), raiz(b)
        if ra != rb:
            padre[ra] = rb

    # los dos bordes que se juntan en la esquina de un panel
    for n, p in panels.items():
        porvert = defaultdict(list)
        for i, e in enumerate(p["edges"]):
            for k, vi in enumerate(e["endpoints"]):
                porvert[vi].append((n, i, k))
        for extremos in porvert.values():
            if len(extremos) == 2:
                une(extremos[0], extremos[1])

    # los dos bordes de una costura, extremo con extremo
    declaradas = total = 0
    for st in pattern.get("stitches", []):
        lados = [s for s in st if isinstance(s, dict)]
        if len(lados) != 2:
            continue
        try:
            pn, en = lados[0]["panel"], lados[0]["edge"]
            qn, fn = lados[1]["panel"], lados[1]["edge"]
            panels[pn]["edges"][en], panels[qn]["edges"][fn]
        except (KeyError, IndexError, TypeError):
            continue
        total += 1
        orient = next((l["orient"] for l in lados if l.get("orient") in PARES), None)
        declaradas += orient is not None
        a, b = PARES[orient or lim.orientacion_por_defecto]
        une((pn, en, 0), (qn, fn, a))
        une((pn, en, 1), (qn, fn, b))

    # extremos libres que llegan a cada esquina montada
    libres_en: dict = defaultdict(list)
    for n, p in panels.items():
        for i in range(len(p["edges"])):
            if (n, i) in uso:
                continue
            for k in (0, 1):
                libres_en[raiz((n, i, k))].append((n, i))

    imposibles = [r for r, v in libres_en.items() if len(v) != 2]
    if imposibles:
        return [], declaradas, total, len(imposibles)

    # un bucle: saltar de borde libre a borde libre por las esquinas montadas
    pendientes = {(n, i) for n, p in panels.items()
                  for i in range(len(p["edges"])) if (n, i) not in uso}
    bucles = []
    while pendientes:
        actual = next(iter(pendientes))
        bucle = []
        while actual in pendientes:
            pendientes.discard(actual)
            bucle.append(actual)
            n, i = actual
            for k in (0, 1):
                vecinos = [x for x in libres_en[raiz((n, i, k))] if x != actual]
                if vecinos and vecinos[0] in pendientes:
                    actual = vecinos[0]
                    break
        bucles.append(bucle)
    return bucles, declaradas, total, 0


def bucles_libres(pattern: dict, lim: Limites | None = None) -> list[list[tuple[str, int]]]:
    """Los bucles del contorno libre: escote, bajo, punos. Util fuera del validador."""
    return _montaje(pattern, lim or Limites())[0]


def _declaracion(panels: dict, bucle: list) -> dict:
    """La declaracion de abertura del bucle, del primer borde que la lleve."""
    for n, i in bucle:
        fin = panels[n]["edges"][i].get("finish")
        if isinstance(fin, dict) and fin.get("fits"):
            return fin
    return {}


def nivel2(pattern: dict, lim: Limites, cuerpo: Cuerpo | None = None) -> list[Hallazgo]:
    """Vestibilidad: que la prenda tenga por donde entrar y que el cuerpo pase."""
    out: list[Hallazgo] = []
    panels = pattern["panels"]
    bucles, declaradas, total, imposibles = _montaje(pattern, lim)

    if imposibles:
        out.append(Hallazgo(
            2, "montaje_incoherente", "aviso",
            f"{imposibles} esquinas de la prenda montada reciben un numero imposible de "
            f"bordes sin coser, asi que el contorno no se puede recorrer; probablemente "
            f"la orientacion de alguna costura no es la declarada",
            medido={"esquinas": imposibles}))
        return out

    if not bucles:
        out.append(Hallazgo(
            2, "prenda_sellada", "error",
            "ningun borde queda sin coser: la prenda es una bolsa cerrada, no tiene por "
            "donde entrar ni se puede volver del derecho"))
        return out

    supuesto = declaradas < total
    if supuesto:
        out.append(Hallazgo(
            2, "montaje_supuesto", "aviso",
            f"{total - declaradas} de {total} costuras no declaran `orient`, asi que el "
            f"montaje usa el convenio por defecto '{lim.orientacion_por_defecto}' "
            f"(Limites.orientacion_por_defecto; ver 'Orientacion de la costura' en el "
            f"README). Al no estar declarado, los veredictos bajan a aviso",
            medido={"declaradas": declaradas, "costuras": total}))

    for bucle in bucles:
        contorno = sum(longitud(panels[n], i) for n, i in bucle)
        etiquetas = sorted({panels[n].get("label") for n, _ in bucle} - {None})
        decl = _declaracion(panels, bucle)
        medido = {"contorno_cm": round(contorno, 1), "bordes": len(bucle),
                  "paneles": etiquetas, "montaje": "supuesto" if supuesto else "declarado"}

        medida = decl.get("fits")
        objetivo = getattr(cuerpo, medida, None) if (cuerpo and medida) else None

        if objetivo is None:
            out.append(Hallazgo(
                2, "abertura", "info",
                f"abertura de {contorno:.1f} cm sobre {len(bucle)} bordes"
                + (f" ({'+'.join(etiquetas)})" if etiquetas else ""),
                medido=medido))
            continue

        estira = float(decl.get("stretch", 1.0))
        util = contorno * estira
        medido |= {"medida": medida, "cuerpo_cm": objetivo, "estiramiento": estira,
                   "util_cm": round(util, 1), "holgura_cm": round(util - objetivo, 1)}

        if decl.get("closure"):
            medido["cierre"] = decl["closure"]
            out.append(Hallazgo(2, "abertura", "info",
                                f"abertura de {contorno:.1f} cm con cierre "
                                f"'{decl['closure']}': se abre para pasar",
                                medido=medido))
        elif util < objetivo:
            # Sin `orient` declarado el montaje es el del convenio por defecto, que
            # el corpus respalda pero el patron no afirma: el hallazgo se emite
            # igual, rebajado a aviso, en vez de callarse.
            out.append(Hallazgo(
                2, "abertura_insuficiente", "aviso" if supuesto else "error",
                f"la abertura mide {contorno:.1f} cm"
                + (f" y estira hasta {util:.1f}" if estira != 1.0 else "")
                + f", y '{medida}' mide {objetivo} cm: no pasa, y no hay cierre declarado"
                + (" (montaje supuesto, no declarado)" if supuesto else ""),
                medido=medido))
        else:
            out.append(Hallazgo(2, "abertura", "info",
                                f"abertura de {contorno:.1f} cm util para '{medida}' "
                                f"({objetivo} cm): {util - objetivo:+.1f} cm de holgura",
                                medido=medido))
    return out
