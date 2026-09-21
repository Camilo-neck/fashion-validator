"""Umbrales de validacion y forma de los hallazgos."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any

__all__ = ["Limites", "Hallazgo", "resumen", "para_modelo", "SEVERIDAD_ORDEN"]


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

    # Por encima de este desajuste, la diferencia de longitud es tan grande
    # que casi seguro es un fruncido deliberado y no un defecto: baja a aviso.
    umbral_fruncido: float = 0.15

    # Distancia bajo la cual un cruce se considera ocurrido en el vertice comun.
    eps_vertice: float = 0.05         # cm
    muestras_linealizacion: int = 48  # resolucion para cruzar arcos y curvas


SEVERIDAD_ORDEN = {"error": 0, "aviso": 1, "info": 2}


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
    """Veredicto compacto: valido o no, y el recuento por codigo."""
    por_codigo: dict[str, int] = {}
    por_sev: dict[str, int] = {}
    for h in hallazgos:
        por_codigo[h.codigo] = por_codigo.get(h.codigo, 0) + 1
        por_sev[h.severidad] = por_sev.get(h.severidad, 0) + 1
    return {
        "valido": por_sev.get("error", 0) == 0,
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
