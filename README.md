<div align="center">

# fashion-validator

**Validador de manufacturabilidad para patrones de costura generados.**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Estado](https://img.shields.io/badge/estado-alfa-orange)](#estado-y-límites-conocidos)
[![Licencia](https://img.shields.io/badge/licencia-por%20definir-lightgrey)](#licencia)

</div>

---

`fashion-validator` comprueba si un patrón de costura generado se puede fabricar
de verdad y explica qué está mal en un formato que un modelo puede consumir para
corregirlo.

Nace de un proyecto de diseño de moda AI-First: un modelo genera los patrones 2D
a partir de texto o imágenes y la simulación 3D la hacen herramientas existentes.
El cuello de botella no es generar formas, sino que las formas resultantes se
puedan coser.

## Tabla de contenidos

- [Motivación](#motivación)
- [Instalación](#instalación)
- [Uso](#uso)
- [Declarar la intención](#declarar-la-intención)
- [Comprobaciones](#comprobaciones)
- [Salida para reparación automática](#salida-para-reparación-automática)
- [Configuración de umbrales](#configuración-de-umbrales)
- [Desarrollo](#desarrollo)
- [Estado y límites conocidos](#estado-y-límites-conocidos)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Contribuir](#contribuir)
- [Licencia](#licencia)
- [Agradecimientos](#agradecimientos)

## Motivación

Los sistemas actuales validan muy poco. GarmentCode, el más completo de los
proyectos abiertos, solo comprueba que un panel no se cruce consigo mismo y que
la prenda no arrastre por el suelo. Sobre 30 patrones que da por válidos, este
validador encuentra errores en 23: bordes de 0,07 cm, esquinas de 9°, radios de
curvatura de 0,13 cm y costuras cuyos dos lados miden distinto sin explicación.

Los números y la metodología con la que se obtuvieron están documentados en
[`docs/hallazgos-fase1.md`](docs/hallazgos-fase1.md).

## Instalación

Requisitos: Python 3.10 o superior.

```bash
pip install -e .
```

Las únicas dependencias son `numpy` y `svgpathtools`. **No requiere
GarmentCode**: lee su formato JSON, pero no depende del paquete.

## Uso

### Línea de comandos

```bash
fashion-validator patron_specification.json            # informe legible
fashion-validator patron_specification.json --modelo   # errores en JSON
```

El comando sale con código `1` si el patrón no es válido, de modo que puede
encadenarse en scripts y pipelines de CI.

### API de Python

```python
from fashion_validator import validar, resumen, para_modelo, Limites

hallazgos = validar(spec, Limites(ancho_rollo=140, angulo_min_esquina=12))

if not resumen(hallazgos)["valido"]:
    prompt_de_reparacion = para_modelo(hallazgos)
```

## Declarar la intención

GarmentCode guarda cada costura como `{panel, edge}` y no indica si una
diferencia de longitud entre sus dos bordes es un fruncido buscado o un defecto.
Sin esa información nadie puede distinguirlos: en los patrones medidos, el 35%
de las costuras tiene los dos lados con longitudes distintas.

Por eso el validador acepta un campo opcional `ease`:

```json
{"panel": "falda_f", "edge": 2,
 "ease": {"type": "gather", "ratio": 1.4, "tol": 0.05}}
```

| Campo | Significado |
| --- | --- |
| `type` | `gather` (fruncido), `ease` (embebido), `stretch` (tejido elástico) |
| `ratio` | cuántas veces más largo es este borde que el opuesto |
| `tol` | tolerancia relativa sobre ese ratio (por defecto `0.05`) |

Declarado y coherente con la geometría, el patrón es válido. Declarado pero
falso, se reporta `ease_incongruente`. Sin declarar, `desajuste_no_declarado`.

El mismo hueco existe en los bordes que no se cosen: un dobladillo bien rematado
y un borde olvidado son el mismo dato. El borde declara su acabado en el panel:

```json
{"endpoints": [3, 4], "finish": {"type": "hem"}}
```

Los tipos son `hem` (dobladillo), `facing` (vista), `binding` (ribete),
`opening` (abertura) y `raw` (borde crudo a propósito). Declararlo sobre un
borde que sí se cose es `acabado_incongruente`; no declararlo queda en aviso.

Sin declarar **no** es error, a diferencia del desajuste de costura: allí hay un
disparador geométrico — los largos no calzan — y aquí no. Marcarlo como error
invalidaría de golpe el 100% de los patrones existentes, que es justo el fallo
del que este validador ya salió una vez.

### Orientación de la costura

El tercer hueco, y el único que no se puede contrastar contra la geometría. El
formato no dice qué extremo de un borde se cose con cuál del otro, y no hay de
dónde deducirlo: la colocación 3D del JSON es la posición inicial del simulador
y deja los paneles separados. La costura lo declara con `orient`:

```json
[{"panel": "delantero", "edge": 3, "orient": "reversed"},
 {"panel": "espalda", "edge": 1}]
```

`direct` cose el primer extremo de un borde con el primero del otro;
`reversed`, con el segundo. Sin declarar, la continuidad prueba los dos y se
queda con el que mejor deja al patrón, así que **subestima**: cada hallazgo
dice en `medido["emparejamiento"]` si viene de una declaración o de una
deducción, porque el deducido es una cota inferior.

Un borde sin coser solo puede continuar en otro borde sin coser. Si la
orientación declarada encaja en menos cruces que la contraria, se reporta
`orientacion_dudosa`. En la camiseta de prueba, `reversed` encaja en 12 cruces
y `direct` en 4.

## Comprobaciones

### Nivel 0 — geometría de cada panel

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

### Nivel 1 — grafo de costuras

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
| `quiebre_en_cruce` | el contorno no sigue suave al cruzar una costura (aviso) |
| `esquina_de_diseno` | quiebre entre dos bordes rectos: esquina dibujada (info) |
| `prenda_desconectada` | los paneles forman varios grupos separados (aviso) |
| `acabado_no_declarado` | bordes sin coser que no dicen cómo se rematan (aviso) |
| `acabado_incongruente` | acabado declarado sobre un borde cosido, o de tipo desconocido |
| `orientacion_incongruente` | la orientación declarada no es `direct` ni `reversed` |
| `orientacion_dudosa` | la orientación declarada contradice el contorno libre (aviso) |
| `costuras_en_redondo` | cuántas costuras cierran un tubo (info) |
| `bordes_libres` | cuántos bordes quedan sin coser (info) |

## Salida para reparación automática

Cada hallazgo lleva código, severidad, la referencia exacta y los valores
medidos, para que un modelo pueda corregir ese punto sin regenerar la prenda
entera:

```json
[{"nivel": 1,
  "codigo": "desajuste_no_declarado",
  "severidad": "error",
  "mensaje": "los bordes miden 19.88 y 21.90 cm (9.2% de diferencia) y no hay declaracion de fruncido o embebido",
  "costura": 5,
  "medido": {"largo_a_cm": 19.88, "largo_b_cm": 21.9, "desajuste_rel": 0.0921}}]
```

Es el mismo patrón que un modelo de código corrigiendo errores del compilador.

## Configuración de umbrales

Los umbrales viven en `Limites` y son configurables, porque la alta costura
rompe varios a propósito. El sistema debe distinguir entre "roto" e
"intencionalmente poco convencional", y esa decisión es del diseñador.

`permitir_pinzas` reconoce el pico de una pinza — dos bordes rectos de igual
longitud en punta — y no lo reporta como esquina inválida. Sin esa excepción,
toda falda y todo pantalón se marcan como defectuosos.

`permitir_esquinas_rectas` hace lo mismo con la continuidad: una esquina entre
dos bordes rectos está dibujada, no acumulada — es el bajo de un godet o una
abertura, no un escote que debería fluir. Sin esa excepción, una falda con
godets sale con un aviso por cada godet.

## Desarrollo

```bash
pip install -e ".[dev]"
pytest
```

La suite tiene 29 casos que comprueban las dos direcciones: que un patrón sano
pase limpio y que cada defecto inyectado se detecte. Las dos importan por igual
— la primera versión de este validador rechazaba el 100% de los patrones.

## Estado y límites conocidos

Los niveles 0 y 1 están implementados. Pendiente:

- **Vestibilidad**: que la prenda pase por la cabeza o la cadera. Necesita
  medidas corporales y pertenece al nivel 2, con simulación física.
- **Calibración real**: los umbrales por defecto son razonables pero no están
  contrastados contra telas físicas. Eso requiere un patronista.
- La factibilidad real del ensamblaje es accesibilidad — que la aguja llegue al
  punto — y eso necesita la prenda en 3D. `costuras_en_redondo` mide el coste de
  coser, no la imposibilidad de hacerlo.
- Sin `orient` declarado, la continuidad se concede el emparejamiento más
  favorable y subestima. Los hallazgos lo dicen en `medido`.
- La intersección exacta de arcos en `svgpathtools`
  ([issue 121](https://github.com/mathandy/svgpathtools/issues/121)) no es
  fiable, así que los cruces se calculan sobre una linealización de 48 tramos.

El plan completo está en [`docs/roadmap.md`](docs/roadmap.md), y el contexto del
proyecto del que nace este validador en [`docs/proyecto.md`](docs/proyecto.md).

## Estructura del repositorio

```
src/fashion_validator/   el paquete; solo numpy y svgpathtools
tests/                   pruebas de discriminación
research/                bancos que produjeron los números (necesitan GarmentCode)
docs/                    hallazgos, hoja de ruta y contexto del proyecto
```

## Contribuir

Las incidencias y los pull requests son bienvenidos. Para cambios de calado,
abre antes una incidencia describiendo el problema y el enfoque.

Antes de enviar un pull request:

1. Añade o actualiza las pruebas que cubren el cambio.
2. Comprueba que `pytest` pasa en limpio.
3. Si el cambio toca umbrales o añade un código de hallazgo, documéntalo en la
   tabla correspondiente de este README.

Los informes de patrones que el validador clasifica mal — falsos positivos y
falsos negativos — son especialmente útiles; adjunta el JSON del patrón si
puedes compartirlo.

## Licencia

Sin definir todavía. GarmentCode se distribuye bajo licencia MIT; este
repositorio no incluye código suyo, solo lee su formato.

## Agradecimientos

- [GarmentCode](https://github.com/maria-korosteleva/GarmentCode) — formato de
  patrones y conjunto de datos sobre el que se midieron los resultados.
- [`svgpathtools`](https://github.com/mathandy/svgpathtools) — geometría de
  curvas.
