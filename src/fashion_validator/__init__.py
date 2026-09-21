"""Validador de manufacturabilidad para patrones de costura.

Valida patrones en el formato JSON de GarmentCode y devuelve hallazgos
estructurados, pensados tanto para una persona como para devolverselos a un
modelo generativo que repare el patron.

    from fashion_validator import validar, resumen, para_modelo

    hallazgos = validar(spec)
    if not resumen(hallazgos)['valido']:
        prompt = para_modelo(hallazgos)
"""

from __future__ import annotations

from .checks import nivel0, nivel1
from .geometry import longitud, segmento
from .model import Hallazgo, Limites, SEVERIDAD_ORDEN, para_modelo, resumen

__all__ = ["validar", "resumen", "para_modelo", "Limites", "Hallazgo",
           "nivel0", "nivel1", "longitud", "segmento"]

__version__ = "0.1.0"


def validar(spec: dict, lim: Limites | None = None) -> list[Hallazgo]:
    """Valida una especificacion de patron completa.

    `spec` puede ser el JSON entero de GarmentCode (con su clave 'pattern')
    o directamente el contenido de esa clave.
    """
    lim = lim or Limites()
    pattern = spec.get("pattern", spec)
    hallazgos = nivel0(pattern, lim) + nivel1(pattern, lim)
    hallazgos.sort(key=lambda h: (SEVERIDAD_ORDEN.get(h.severidad, 9), h.nivel, h.codigo))
    return hallazgos
