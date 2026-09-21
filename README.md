# fashion-validator

Valida si un patrón de costura generado se puede fabricar de verdad, y explica
qué está mal en un formato que un modelo puede usar para arreglarlo.

Nace de un proyecto de diseño de moda AI-First: un modelo genera los patrones
2D a partir de texto o imágenes, y la simulación 3D la hacen herramientas
existentes. El cuello de botella no es generar formas, es que las formas
resultantes se puedan coser.

## Por qué

Los sistemas actuales validan muy poco. GarmentCode, el más completo de los
abiertos, solo comprueba que un panel no se cruce consigo mismo y que la prenda
no arrastre por el suelo. Sobre 30 patrones que da por válidos, este validador
encuentra errores en 23: bordes de 0,07 cm, esquinas de 9°, radios de curvatura
de 0,13 cm y costuras cuyos dos lados miden distinto sin explicación.

Los números y cómo se obtuvieron están en
[`docs/hallazgos-fase1.md`](docs/hallazgos-fase1.md).

## Instalación

```bash
pip install -e .
```

Solo necesita `numpy` y `svgpathtools`. **No requiere GarmentCode**: lee su
formato JSON, pero no depende del paquete.

## Uso

```bash
fashion-validator patron_specification.json            # informe legible
fashion-validator patron_specification.json --modelo   # errores en JSON
```

Sale con código 1 si el patrón no es válido, para encadenarlo en scripts.

```python
from fashion_validator import validar, resumen, para_modelo, Limites

hallazgos = validar(spec, Limites(ancho_rollo=140, angulo_min_esquina=12))

if not resumen(hallazgos)["valido"]:
    prompt_de_reparacion = para_modelo(hallazgos)
```

## Declarar la intención

GarmentCode guarda cada costura como `{panel, edge}` y no dice si una
diferencia de longitud entre sus dos bordes es un fruncido buscado o un
defecto. Sin esa información nadie puede distinguirlos: en los patrones
medidos, el 35% de las costuras tiene los dos lados con longitudes distintas.

Este validador acepta un campo opcional `ease`:

```json
{"panel": "falda_f", "edge": 2,
 "ease": {"type": "gather", "ratio": 1.4, "tol": 0.05}}
```

| Campo | Significado |
| --- | --- |
| `type` | `gather` (fruncido), `ease` (embebido), `stretch` (tejido elástico) |
| `ratio` | cuántas veces más largo es este borde que el opuesto |
| `tol` | tolerancia relativa sobre ese ratio (por defecto 0,05) |

Declarado y coherente con la geometría, el patrón es válido. Declarado pero
falso, se reporta `ease_incongruente`. Sin declarar, `desajuste_no_declarado`.

## Qué comprueba

**Nivel 0 — geometría de cada panel**

| Código | Qué detecta |
| --- | --- |
| `vertice_inexistente` | un borde apunta a un vértice fuera de rango |
| `contorno_abierto` | los bordes no forman un ciclo cerrado |
| `vertice_huerfano` | vértice que ningún borde usa |
| `borde_degenerado` | borde más corto que el mínimo cortable |
| `curvatura_excesiva` | radio de curvatura por debajo del mínimo cosible |
| `esquina_aguda` | ángulo demasiado cerrado para coserse |
| `pico_de_pinza` | esquina aguda reconocida como pinza legítima (info) |
| `auto_interseccion` | dos bordes del panel se cruzan fuera de un vértice |
| `excede_ancho_rollo` | el panel no cabe en el ancho de tela ni girándolo |

**Nivel 1 — grafo de costuras**

| Código | Qué detecta |
| --- | --- |
| `costura_no_binaria` | una costura que no une exactamente dos bordes |
| `panel_inexistente`, `borde_inexistente` | referencia rota |
| `costura_nula` | ambos bordes con longitud cero |
| `desajuste_no_declarado` | diferencia de longitud entre 1% y 15%, sin declarar |
| `fruncido_no_declarado` | diferencia mayor al 15%: probablemente intencional (aviso) |
| `ease_incongruente` | el ratio declarado no coincide con la geometría |
| `borde_multicosido` | un borde que aparece en más de una costura |
| `panel_suelto` | panel que no está cosido a nada |
| `prenda_desconectada` | los paneles forman varios grupos separados (aviso) |
| `bordes_libres` | cuántos bordes quedan sin coser (info) |

## Salida para reparar

Cada hallazgo lleva código, severidad, la referencia exacta y los valores
medidos, para que el modelo pueda corregir ese punto sin regenerar la prenda:

```json
[{"nivel": 1,
  "codigo": "desajuste_no_declarado",
  "severidad": "error",
  "mensaje": "los bordes miden 19.88 y 21.90 cm (9.2% de diferencia) y no hay declaracion de fruncido o embebido",
  "costura": 5,
  "medido": {"largo_a_cm": 19.88, "largo_b_cm": 21.9, "desajuste_rel": 0.0921}}]
```

Es el mismo patrón que un modelo de código arreglando errores del compilador.

## Reglas blandas

Los umbrales viven en `Limites` y son configurables, porque la alta costura
rompe varios a propósito. El sistema debe distinguir entre "roto" e
"intencionalmente poco convencional", y esa decisión es del diseñador.

`permitir_pinzas` reconoce el pico de una pinza — dos bordes rectos de igual
longitud en punta — y no lo reporta como esquina inválida. Sin esa excepción,
toda falda y todo pantalón se marcan como defectuosos.

## Pruebas

```bash
pip install -e ".[dev]"
pytest
```

14 casos que comprueban las dos direcciones: que un patrón sano pase limpio y
que cada defecto inyectado se detecte. Las dos importan por igual — la primera
versión de este validador rechazaba el 100% de los patrones.

## Estado y límites conocidos

Niveles 0 y 1 implementados. Falta:

- **Continuidad en los cruces de costura**: que el escote siga suave al unir
  delantero y espalda. Exige recorrer el grafo comparando tangentes entre
  paneles.
- **Vestibilidad**: que la prenda pase por la cabeza o la cadera. Necesita
  medidas corporales y pertenece al nivel 2, con simulación física.
- **Calibración real**: los umbrales por defecto son razonables pero no están
  contrastados contra telas físicas. Eso requiere un patronista.
- La intersección exacta de arcos en `svgpathtools`
  ([issue 121](https://github.com/mathandy/svgpathtools/issues/121)) no es
  fiable, así que los cruces se calculan sobre una linealización de 48 tramos.

## Estructura

```
src/fashion_validator/   el paquete; solo numpy y svgpathtools
tests/                   pruebas de discriminación
research/                bancos que produjeron los números (necesitan GarmentCode)
docs/                    hallazgos de la fase 1
```

## Licencia

Sin definir todavía. GarmentCode es MIT; este repositorio no incluye código
suyo, solo lee su formato.
