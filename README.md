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
- [Vestibilidad](#vestibilidad)
- [Barrido de un corpus](#barrido-de-un-corpus)
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
la prenda no arrastre por el suelo.

Sobre **3.450 patrones del corpus publicado GarmentCodeData v2** — ya filtrados
por sus autores y supervivientes de la simulación física — este validador
encuentra que:

| | Patrones | % |
| --- | ---: | ---: |
| Tienen un defecto geométrico que impide fabricarlos | 705 | **20,4** |
| Solo les falta declarar la intención de una costura | 2.383 | 69,1 |
| Pasan limpios | 362 | 10,5 |

Uno de cada cinco no se puede coser: bordes de 0,018 cm, esquinas de 0,16°,
paneles que no caben en el rollo. Los otros dos tercios no son necesariamente
defectuosos — son *indistinguibles* de un defecto, porque el formato no guarda
si un desajuste era buscado.

La metodología está en
[`docs/hallazgos-corpus.md`](docs/hallazgos-corpus.md); la fase 1, sobre 30
patrones, en [`docs/hallazgos-fase1.md`](docs/hallazgos-fase1.md).

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

### Nivel 2 — vestibilidad, sin simulación

| Código | Qué detecta |
| --- | --- |
| `prenda_sellada` | ningún borde queda libre: no hay por dónde entrar |
| `abertura_insuficiente` | el cuerpo no pasa por la abertura declarada |
| `abertura` | contorno de cada abertura de la prenda montada (info) |
| `montaje_supuesto` | falta `orient`, así que se mide pero no se juzga (aviso) |
| `montaje_incoherente` | el contorno montado no se puede recorrer (aviso) |

## Vestibilidad

Los bordes que no se cosen forman bucles cerrados en la prenda montada — escote,
bajo, puños — y el contorno de cada uno es la suma de las longitudes de sus
bordes. Con una medida del cuerpo, eso responde si la cabeza pasa por el escote
sin necesidad de simular nada.

```python
from fashion_validator import validar, Cuerpo

hallazgos = validar(spec, cuerpo=Cuerpo(head=57, hip=100))
```

Sin `cuerpo`, las aberturas se miden y se informan, pero no se juzgan.

Una abertura declara qué medida tiene que dejar pasar, y con qué ayuda:

```json
{"endpoints": [3, 4],
 "finish": {"type": "opening", "fits": "head", "stretch": 1.5}}
```

`fits` nombra un campo de `Cuerpo`; `stretch` es cuánto da de sí el tejido en esa
abertura; `closure` (`zip`, `buttons`) dice que se abre para pasar y exime del
chequeo. Sin `stretch` ni `closure`, un escote de punto se marcaría como
inservible — es la misma excepción que las pinzas y los godets, por cuarta vez.

**El montaje depende de `orient`.** Con la orientación equivocada, los cuatro
huecos de una camiseta salen como dos bucles de 129,6 cm. Por eso, si alguna
costura no la declara, el nivel 2 informa contornos pero no emite ningún
veredicto contra el cuerpo.

La parte que sí necesita simulación — drapeado, tensión, poses — no está
implementada a propósito; el plan está en
[`docs/nivel2-simulado.md`](docs/nivel2-simulado.md).

## Barrido de un corpus

El uso con más retorno no es el bucle de reparación: es filtrar el corpus de
entrenamiento. Si 23 de cada 30 patrones que GarmentCode da por válidos tienen
defectos, las 115.000 prendas de GarmentCodeData los tienen también, y un modelo
entrenado sobre ellas los aprende como construcción correcta.

```bash
fashion-validator GarmentCodeData/ --lote --salida informe.json
```

Recorre el directorio, valida cada patrón y escribe el recuento por código más
un manifiesto con los que pasan limpio, que es lo que se pasa al entrenamiento.
No necesita GarmentCode: lee los JSON ya generados. A unos 10 ms por patrón,
115.000 son unos 20 minutos en un núcleo.

```python
from fashion_validator.corpus import barrer

informe = barrer(Path("GarmentCodeData"))
print(informe["pct_rechazados"], informe["hallazgos_por_codigo"])
```

Un archivo ilegible se anota y el barrido sigue.

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

La suite tiene 40 casos que comprueban las dos direcciones: que un patrón sano
pase limpio y que cada defecto inyectado se detecte. Las dos importan por igual
— la primera versión de este validador rechazaba el 100% de los patrones.

## Estado y límites conocidos

Los niveles 0 y 1 están completos, y el nivel 2 solo en su mitad
geométrica. Pendiente:

- **Calibración real**: los umbrales por defecto son razonables pero no están
  contrastados contra telas físicas. Eso requiere un patronista.
- **Nivel 2 simulado**: drapeado, mapas de tensión y poses dinámicas. No está
  hecho a propósito: sin telas medidas ni patronista, un veredicto basado en
  simulación afirma algo que nadie ha comprobado. Ver
  [`docs/nivel2-simulado.md`](docs/nivel2-simulado.md).
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
docs/                    hallazgos, hoja de ruta, contexto y plan del nivel 2
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
