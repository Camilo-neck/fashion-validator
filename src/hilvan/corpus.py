"""Barrido de un corpus de patrones: medir, y separar lo sano de lo roto.

El uso con mas retorno del validador no es el bucle de reparacion sino este.
Si 23 de cada 30 patrones que GarmentCode da por validos tienen defectos, las
115.000 prendas de GarmentCodeData los tienen tambien, y un modelo entrenado
sobre ese corpus los aprende como construccion correcta. Filtrarlo antes de
entrenar corrige el problema en la raiz, una sola vez.

No necesita GarmentCode: lee los JSON ya generados. A unos 10 ms por patron,
115.000 son unos 20 minutos en un solo nucleo.

    from hilvan.corpus import barrer
    informe = barrer(Path("GarmentCodeData"))
    json.dump(informe, open("informe.json", "w"), indent=1)

El manifiesto de patrones sanos que devuelve es lo que se pasa al
entrenamiento; el recuento por codigo es la metrica publicable.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from . import validar
from .model import Cuerpo, Limites, resumen

__all__ = ["barrer", "validar_archivo"]


def validar_archivo(ruta: Path, lim: Limites, cuerpo: Cuerpo | None = None) -> dict:
    """Valida un archivo. Nunca lanza: un patron ilegible es un resultado."""
    try:
        with open(ruta, encoding="utf-8") as f:
            spec = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return {"archivo": str(ruta), "ilegible": type(e).__name__}

    if not isinstance(spec, dict) or "panels" not in spec.get("pattern", spec):
        return {"archivo": str(ruta), "ilegible": "sin panels"}

    try:
        hallazgos = validar(spec, lim, cuerpo)
    except Exception as e:  # el validador no deberia caerse; si lo hace, se anota
        return {"archivo": str(ruta), "fallo": f"{type(e).__name__}: {e}"}

    r = resumen(hallazgos)
    return {"archivo": str(ruta), "valido": r["valido"],
            "sin_defecto_duro": r["sin_defecto_duro"], "validado": r["validado"],
            "errores": r["errores"], "avisos": r["avisos"], "por_codigo": r["por_codigo"]}


def barrer(raiz: Path, patron: str = "*specification.json",
           lim: Limites | None = None, cuerpo: Cuerpo | None = None,
           limite: int | None = None, traza=None) -> dict:
    """Valida todos los patrones bajo `raiz` y resume lo encontrado.

    `patron` es el glob de los archivos a mirar; el de GarmentCodeData es
    `*specification.json`. `traza` es un callable opcional al que se le pasa
    cada resultado segun sale, para ir informando del avance.
    """
    lim = lim or Limites()
    rutas = sorted(Path(raiz).rglob(patron))
    if limite is not None:
        rutas = rutas[:limite]

    codigos: Counter = Counter()
    validos = 0
    sin_duro: list[str] = []
    sanos: list[str] = []
    rotos: list[str] = []
    ilegibles: list[dict] = []
    fallos: list[dict] = []

    for ruta in rutas:
        res = validar_archivo(ruta, lim, cuerpo)
        if traza:
            traza(res)
        if "ilegible" in res:
            ilegibles.append(res)
            continue
        if "fallo" in res:
            fallos.append(res)
            continue
        codigos.update(res["por_codigo"])
        validos += res["valido"]
        if res["sin_defecto_duro"]:
            sin_duro.append(res["archivo"])
        (sanos if res["validado"] else rotos).append(res["archivo"])

    medidos = len(sanos) + len(rotos)
    return {
        "archivos": len(rutas),
        "medidos": medidos,
        "sanos": len(sanos),
        "rotos": len(rotos),
        "pct_rechazados": round(100 * len(rotos) / medidos, 1) if medidos else 0.0,
        "validos": validos,
        "sin_defecto_duro": len(sin_duro),
        "hallazgos_por_codigo": dict(codigos.most_common()),
        "ilegibles": ilegibles[:20],
        "fallos_del_validador": fallos[:20],
        "manifiesto_sanos": sanos,
        # el filtro que conviene para entrenar: el de cero errores castiga el
        # tamano de la prenda, porque los desajustes se acumulan con las costuras
        "manifiesto_sin_defecto_duro": sin_duro,
    }
