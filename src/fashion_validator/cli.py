"""Interfaz de linea de comandos.

    python -m fashion_validator patron.json
    python -m fashion_validator patron.json --modelo
"""

from __future__ import annotations

import argparse
import json
import sys

from . import validar
from .model import Limites, para_modelo, resumen


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="fashion-validator",
        description="Valida la manufacturabilidad de un patron de costura.")
    ap.add_argument("patron", help="JSON de especificacion en formato GarmentCode")
    ap.add_argument("--modelo", action="store_true",
                    help="imprime solo los errores en JSON, para el bucle de reparacion")
    ap.add_argument("--ancho-rollo", type=float, default=None,
                    help="ancho util de la tela en cm (por defecto 150)")
    ap.add_argument("--angulo-min", type=float, default=None,
                    help="angulo minimo cosible en grados (por defecto 15)")
    ap.add_argument("--sin-pinzas", action="store_true",
                    help="no reconocer picos de pinza: toda esquina aguda es error")
    args = ap.parse_args(argv)

    lim = Limites()
    if args.ancho_rollo is not None:
        lim.ancho_rollo = args.ancho_rollo
    if args.angulo_min is not None:
        lim.angulo_min_esquina = args.angulo_min
    if args.sin_pinzas:
        lim.permitir_pinzas = False

    with open(args.patron, encoding="utf-8") as f:
        spec = json.load(f)

    hallazgos = validar(spec, lim)

    if args.modelo:
        print(para_modelo(hallazgos))
    else:
        r = resumen(hallazgos)
        print(json.dumps(r, indent=1, ensure_ascii=False))
        print()
        for h in hallazgos:
            print(h)

    # codigo de salida 1 si el patron no es valido, para encadenar en scripts
    return 0 if resumen(hallazgos)["valido"] else 1


if __name__ == "__main__":
    sys.exit(main())
