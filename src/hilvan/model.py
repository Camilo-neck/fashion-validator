"""Umbrales de validacion y forma de los hallazgos."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any

__all__ = ["Limites", "Cuerpo", "Hallazgo", "resumen", "para_modelo",
           "SEVERIDAD_ORDEN", "DUROS", "ESTRUCTURALES"]


@dataclass
class Limites:
    """Umbrales fisicos de manufacturabilidad.

    Dependen del material y del taller, y la alta costura rompe varios a
    proposito, asi que todos son configurables. La regla no es "esto esta
    prohibido" sino "esto hay que declararlo".
    """

    largo_min_borde: float = 0.5      # cm; por debajo no es cortable ni cosible
    angulo_min_esquina: float = 15.0  # grados; esquinas mas agudas no se cosen
    radio_min_curva: float = 0.3      # cm; curvatura mas cerrada no se cose
    ancho_rollo: float = 150.0        # cm; ancho util de la tela
    tol_costura: float = 0.01         # 1% de diferencia de longitud admitida
    tol_ease_default: float = 0.05    # tolerancia sobre un ratio declarado

    # Un pico de pinza es agudo a proposito: dos bordes rectos de igual
    # longitud que se juntan en punta. Se reconoce y no se reporta.
    permitir_pinzas: bool = True
    tol_simetria_pinza: float = 0.02  # 2% de diferencia entre los dos lados

    # Continuidad en los cruces de costura: al unir dos paneles, el contorno
    # libre pasa de uno al otro y deberia seguir suave. Se mide cuanto se
    # desvia de los 180 grados.
    angulo_max_quiebre: float = 20.0  # grados de quiebre tolerados en un cruce

    # Una esquina entre dos bordes rectos esta dibujada, no acumulada: es el
    # bajo de un godet o una abertura, no un escote que deberia fluir. Se
    # reconoce y no se reporta, igual que el pico de pinza.
    permitir_esquinas_rectas: bool = True

    # Por encima de este desajuste, la diferencia de longitud es tan grande
    # que casi seguro es un fruncido deliberado y no un defecto: baja a aviso.
    umbral_fruncido: float = 0.15

    # Como se emparejan los extremos de los dos bordes de una costura cuando la
    # costura no lo declara con `orient`. Es el convenio observado en la salida
    # de GarmentCode: verificado sobre sus dos prendas de referencia, donde
    # 'reversed' produce las aberturas que la prenda tiene de verdad y 'direct'
    # las fusiona. No es una garantia del formato, por eso es configurable y la
    # declaracion por costura manda sobre esto.
    orientacion_por_defecto: str = "reversed"

    # Distancia bajo la cual un cruce se considera ocurrido en el vertice comun.
    eps_vertice: float = 0.05         # cm
    muestras_linealizacion: int = 48  # resolucion para cruzar arcos y curvas


@dataclass
class Cuerpo:
    """Medidas del cuerpo, en centimetros, para los chequeos de vestibilidad.

    No vienen en el patron: GarmentCode las guarda en un archivo de cuerpo
    aparte, asi que hay que aportarlas. Los valores por defecto son un maniqui
    de talla media y sirven para tantear, no para validar a nadie.

    Los nombres coinciden con los valores admitidos en `finish.fits`, que es
    como una abertura dice que medida tiene que dejar pasar.
    """

    head: float = 57.0    # contorno de cabeza: lo que un escote sin cierre debe pasar
    neck: float = 37.0
    bust: float = 94.0
    waist: float = 76.0
    hip: float = 100.0
    wrist: float = 17.0
    hand: float = 21.0    # contorno de mano: lo que un puno sin cierre debe pasar


SEVERIDAD_ORDEN = {"error": 0, "aviso": 1, "info": 2}

# Defectos que dependen solo de la geometria del panel, no de una intencion que
# el formato no guarda. Un desajuste de costura puede ser un fruncido legitimo;
# un borde de una fraccion de milimetro no se puede cortar bajo ninguna lectura.
# Es la separacion que hace util el filtro de corpus: quedarse con todo salvo
# esto no sesga contra las prendas grandes, mientras que filtrar por "cero
# errores" castiga el tamano, porque los desajustes se acumulan con las
# costuras. Las cifras estan en docs/hallazgos-corpus.md.
DUROS = frozenset({"borde_degenerado", "esquina_aguda", "curvatura_excesiva",
                   "excede_ancho_rollo", "auto_interseccion"})

# Errores que impiden interpretar el patron: una referencia que no existe, un
# contorno que no cierra, una costura que no une dos bordes, un borde cosido
# dos veces o un panel suelto. Un patron sin ninguno es "valido" en el sentido
# del paper (se interpreta y el grafo de costuras resuelve), que es mucho menos
# que estar validado.
ESTRUCTURALES = frozenset({"vertice_inexistente", "contorno_abierto",
                           "contorno_multiple",
                           "costura_no_binaria", "panel_inexistente",
                           "borde_inexistente", "costura_nula",
                           "borde_multicosido", "panel_suelto"})


@dataclass
class Hallazgo:
    """Un hallazgo del validador.

    Lleva la referencia exacta y los valores medidos para que un modelo
    generativo pueda reparar ese punto sin regenerar la prenda entera.
    """

    nivel: int
    codigo: str
    severidad: str          # error | aviso | info
    mensaje: str
    panel: str | None = None
    borde: int | None = None
    costura: int | None = None
    medido: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        loc = ""
        if self.panel is not None:
            loc = f" [{self.panel}" + (f".{self.borde}]" if self.borde is not None else "]")
        elif self.costura is not None:
            loc = f" [costura {self.costura}]"
        return f"{self.severidad.upper():6} {self.codigo}{loc}: {self.mensaje}"


def resumen(hallazgos: list[Hallazgo]) -> dict:
    """Veredicto compacto en los tres niveles del paper, y el recuento por codigo.

    - `valido`: sin errores estructurales; el patron se interpreta.
    - `sin_defecto_duro`: sin ningun defecto de DUROS.
    - `validado`: sin ningun error. Es lo que antes se llamaba `valido`; el
      nombre cambio porque "valido" en el paper es la propiedad mas debil.
    """
    por_codigo: dict[str, int] = {}
    por_sev: dict[str, int] = {}
    errores: set[str] = set()
    for h in hallazgos:
        por_codigo[h.codigo] = por_codigo.get(h.codigo, 0) + 1
        por_sev[h.severidad] = por_sev.get(h.severidad, 0) + 1
        if h.severidad == "error":
            errores.add(h.codigo)
    return {
        "valido": not (errores & ESTRUCTURALES),
        "sin_defecto_duro": not (errores & DUROS),
        "validado": not errores,
        "errores": por_sev.get("error", 0),
        "avisos": por_sev.get("aviso", 0),
        "por_codigo": por_codigo,
    }


def para_modelo(hallazgos: list[Hallazgo], maximo: int = 20) -> str:
    """Los errores en JSON compacto, para devolverselos al generador."""
    errores = [h for h in hallazgos if h.severidad == "error"][:maximo]
    return json.dumps(
        [{k: v for k, v in asdict(h).items() if v not in (None, {}, [])} for h in errores],
        ensure_ascii=False,
        indent=1,
    )
