"""Interfaz de linea de comandos.

    python -m fashion_validator patron.json
    python -m fashion_validator patron.json --modelo
    python -m fashion_validator CORPUS/ --lote --salida informe.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields
from pathlib import Path

from . import validar
from .corpus import barrer
from .model import Cuerpo, Limites, para_modelo, resumen


def _cuerpo(ruta: str | None) -> Cuerpo | None:
    """Carga las medidas del cuerpo. No vienen en el patron."""
    if ruta is None:
        return None
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    admitidos = {f.name for f in fields(Cuerpo)}
    sobran = set(datos) - admitidos
    if sobran:
        raise SystemExit(f"medidas desconocidas: {sorted(sobran)}; "
                         f"admitidas: {sorted(admitidos)}")
    return Cuerpo(**datos)


def _lote(args, lim: Limites) -> int:
    def traza(res):
        estado = ("ILEGIBLE" if "ilegible" in res else
                  "FALLO" if "fallo" in res else
                  "ok" if res["valido"] else "ROTO")
        print(f"{estado:9} {res['archivo']}", file=sys.stderr)

    informe = barrer(Path(args.patron), lim=lim, cuerpo=_cuerpo(args.cuerpo),
                     limite=args.limite, traza=traza if args.verboso else None)

    if args.salida:
        with open(args.salida, "w", encoding="utf-8") as f:
            json.dump(informe, f, indent=1, ensure_ascii=False)

    resumido = {k: v for k, v in informe.items() if k != "manifiesto_sanos"}
    print(json.dumps(resumido, indent=1, ensure_ascii=False))
    return 0 if informe["rotos"] == 0 else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="fashion-validator",
        description="Valida la manufacturabilidad de un patron de costura.")
    ap.add_argument("patron", help="JSON de especificacion, o un directorio con --lote")
    ap.add_argument("--lote", action="store_true",
                    help="barrer un corpus entero y sacar el manifiesto de los sanos")
    ap.add_argument("--salida", default=None,
                    help="archivo donde escribir el informe completo del lote")
    ap.add_argument("--limite", type=int, default=None,
                    help="mirar solo los primeros N patrones del corpus")
    ap.add_argument("--verboso", action="store_true",
                    help="ir listando cada patron del lote por stderr")
    ap.add_argument("--cuerpo", default=None,
                    help="JSON con las medidas del cuerpo; activa los veredictos "
                         "de vestibilidad del nivel 2")
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

    if args.lote:
        return _lote(args, lim)

    with open(args.patron, encoding="utf-8") as f:
        spec = json.load(f)

    hallazgos = validar(spec, lim, _cuerpo(args.cuerpo))

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
