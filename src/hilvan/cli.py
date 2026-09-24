"""Interfaz de linea de comandos.

Codigo de salida: 0 si el patron pasa la validacion completa, 1 si no, y 2 si
el error es de uso o de lectura (archivo inexistente, JSON invalido, clave
desconocida en --limites o --cuerpo).

    python -m hilvan patron.json
    python -m hilvan patron.json --modelo
    python -m hilvan CORPUS/ --lote --salida informe.json
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


class ErrorDeUso(Exception):
    """Un error del que llama, no del patron: sale con codigo 2."""


def _json(ruta: str, que: str) -> dict:
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
    except OSError as e:
        raise ErrorDeUso(f"no se puede leer {que} '{ruta}': {e.strerror or e}") from None
    except json.JSONDecodeError as e:
        raise ErrorDeUso(f"{que} '{ruta}' no es JSON valido: {e.msg} "
                         f"(linea {e.lineno})") from None
    if not isinstance(datos, dict):
        raise ErrorDeUso(f"{que} '{ruta}' tiene que ser un objeto JSON")
    return datos


def _campos(datos: dict, clase, que: str) -> dict:
    """Solo los campos que la dataclass admite: una clave mal escrita no se ignora."""
    admitidos = {f.name for f in fields(clase)}
    sobran = set(datos) - admitidos
    if sobran:
        raise ErrorDeUso(f"{que} desconocidos: {sorted(sobran)}; "
                         f"admitidos: {sorted(admitidos)}")
    return datos


def _cuerpo(ruta: str | None) -> Cuerpo | None:
    """Carga las medidas del cuerpo. No vienen en el patron."""
    if ruta is None:
        return None
    return Cuerpo(**_campos(_json(ruta, "el cuerpo"), Cuerpo, "medidas"))


def _limites(ruta: str | None) -> Limites:
    """Carga cualquier campo de Limites desde un JSON; lo que no venga, por defecto."""
    if ruta is None:
        return Limites()
    datos = _campos(_json(ruta, "los limites"), Limites, "limites")
    por_defecto = Limites()
    for clave, valor in datos.items():
        tipo = type(getattr(por_defecto, clave))
        # un umbral numerico admite int o float, pero no un bool ni un texto
        numerico = (tipo in (int, float) and isinstance(valor, (int, float))
                    and not isinstance(valor, bool))
        if not (numerico or isinstance(valor, tipo)
                or (clave == "orientacion_por_defecto" and valor is None)):
            raise ErrorDeUso(f"el limite '{clave}' tiene que ser {tipo.__name__}, "
                             f"no {valor!r}")
    return Limites(**datos)


def _lote(args, lim: Limites, cuerpo: Cuerpo | None) -> int:
    def traza(res):
        estado = ("ILEGIBLE" if "ilegible" in res else
                  "FALLO" if "fallo" in res else
                  "ok" if res["validado"] else "ROTO")
        print(f"{estado:9} {res['archivo']}", file=sys.stderr)

    informe = barrer(Path(args.patron), lim=lim, cuerpo=cuerpo,
                     limite=args.limite, traza=traza if args.verboso else None)

    if args.salida:
        try:
            with open(args.salida, "w", encoding="utf-8") as f:
                json.dump(informe, f, indent=1, ensure_ascii=False)
        except OSError as e:
            raise ErrorDeUso(f"no se puede escribir '{args.salida}': "
                             f"{e.strerror or e}") from None

    resumido = {k: v for k, v in informe.items() if k != "manifiesto_sanos"}
    print(json.dumps(resumido, indent=1, ensure_ascii=False))
    return 0 if informe["rotos"] == 0 else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="hilvan",
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
    ap.add_argument("--limites", default=None,
                    help="JSON con cualquier campo de Limites, p. ej. "
                         '{"largo_min_borde": 0.3, "tol_costura": 0.02}; '
                         "los flags de abajo mandan sobre el archivo")
    ap.add_argument("--ancho-rollo", type=float, default=None,
                    help="ancho util de la tela en cm (por defecto 150)")
    ap.add_argument("--angulo-min", type=float, default=None,
                    help="angulo minimo cosible en grados (por defecto 15)")
    ap.add_argument("--sin-pinzas", action="store_true",
                    help="no reconocer picos de pinza: se reportan como muesca_aguda")
    ap.add_argument("--orientacion", choices=["direct", "reversed", "deducida"],
                    default=None,
                    help="emparejamiento de las costuras que no declaran `orient` "
                         "(por defecto 'reversed', el convenio de GarmentCode; "
                         "'deducida' lo decide la topologia para el patron entero, "
                         "para patrones de otros generadores)")
    args = ap.parse_args(argv)

    try:
        return _ejecutar(args)
    except ErrorDeUso as e:
        print(f"hilvan: error: {e}", file=sys.stderr)
        return 2


def _ejecutar(args) -> int:
    """0 si pasa la validacion completa, 1 si no; los errores de uso, ErrorDeUso."""
    lim = _limites(args.limites)
    if args.ancho_rollo is not None:
        lim.ancho_rollo = args.ancho_rollo
    if args.angulo_min is not None:
        lim.angulo_min_esquina = args.angulo_min
    if args.sin_pinzas:
        lim.permitir_pinzas = False
    if args.orientacion is not None:
        lim.orientacion_por_defecto = None if args.orientacion == "deducida" else args.orientacion
    cuerpo = _cuerpo(args.cuerpo)

    if args.lote:
        if not Path(args.patron).is_dir():
            raise ErrorDeUso(f"'{args.patron}' no es un directorio")
        return _lote(args, lim, cuerpo)

    spec = _json(args.patron, "el patron")
    if "panels" not in spec.get("pattern", spec):
        raise ErrorDeUso(f"'{args.patron}' no es una especificacion de patron: "
                         f"no tiene 'panels'")
    hallazgos = validar(spec, lim, cuerpo)

    if args.modelo:
        print(para_modelo(hallazgos))
    else:
        r = resumen(hallazgos)
        print(json.dumps(r, indent=1, ensure_ascii=False))
        print()
        for h in hallazgos:
            print(h)

    return 0 if resumen(hallazgos)["validado"] else 1


if __name__ == "__main__":
    sys.exit(main())
