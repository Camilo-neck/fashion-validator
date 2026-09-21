# Hallazgos de la fase 1

Reproducción del trabajo existente en generación de patrones con IA, y lo que
salió de ahí. Pruebas del 21 de septiembre de 2026, en un contenedor Linux sin
GPU.

## Qué se probó

| Proyecto | ¿Se pudo correr? | Qué representa |
| --- | --- | --- |
| [GarmentCode](https://github.com/maria-korosteleva/GarmentCode) | Sí, en CPU | Patrones paramétricos, ~80 parámetros |
| [ChatGarment](https://github.com/biansy000/ChatGarment) | No | VLM que emite parámetros de GarmentCode |
| [AIpparel](https://github.com/georgeNakayama/AIpparel-Code) | No | Tokeniza geometría como comandos de dibujo |

ChatGarment y AIpparel no se ejecutaron porque el entorno no tenía GPU y la
política de red bloqueaba Hugging Face (donde viven los pesos) y el
repositorio de ETH (donde vive GarmentCodeData). Su arquitectura se analizó
leyendo el código.

## GarmentCode

Corre en CPU sin problema. La camiseta de ejemplo salió con 8 paneles y 16
costuras, exportada a JSON, SVG, PNG y PDF imprimible.

**Representación.** Cada panel tiene vértices en 2D, bordes con curvatura
opcional (Bézier cúbica o arco en formato SVG), una colocación 3D y una
etiqueta semántica. Cada costura es un par `{panel, edge}`.

**Validez.** De 60 diseños muestreados al azar sobre el espacio de parámetros,
solo 18 (30%) produjeron un patrón válido:

| Resultado | Casos |
| --- | --- |
| Válido | 18 |
| Auto-intersección | 22 |
| Error (casi todo largo excedido) | 20 |

Esto desmiente la idea de que un sistema paramétrico sea "válido por
construcción": el espacio está lleno de zonas inválidas y el generador oficial
reintenta hasta acertar.

**Qué valida GarmentCode.** Solo dos cosas: auto-intersección por pares de
bordes dentro de un panel, y que el largo total no supere la altura del
cuerpo. No mira radios cosibles, ancho de rollo, calce de costuras ni
vestibilidad.

## El hueco del formato

Midiendo las longitudes de los bordes cosidos en 25 patrones válidos:

| Umbral | Con fruncidos | Sin fruncidos |
| --- | --- | --- |
| Desajuste > 1% | 35,4% | 23,6% |
| Desajuste > 5% | 27,8% | 15,9% |
| Máximo | 53,1% | 52,2% |

Desactivar los fruncidos baja el desajuste, pero no lo elimina: explican
alrededor de un tercio. El resto viene de embebidos que tampoco se declaran.

Y ahí está el problema de fondo: **el formato no guarda la intención**. Una
costura es `{panel, edge}` y nada más, así que ningún validador puede
distinguir un fruncido deliberado de un defecto. De ahí sale la extensión
`ease` que implementa este repositorio.

## Los dos modelos

**ChatGarment** emite el esquema de parámetros de GarmentCode, clave por
clave. Su techo expresivo es exactamente el espacio de GarmentCode: no puede
producir nada fuera de él.

**AIpparel** tokeniza la geometría directamente como comandos de dibujo
(`MOVE`, `LINE`, `CURVE`, `CUBIC`, `ARC`, más sus cierres) y codifica las
costuras como etiquetas compartidas entre bordes, con un tope de 108. Rompe el
techo paramétrico, pero no garantiza validez: su propio código define tipos de
error de decodificación para secuencias mal formadas. Está construido sobre
LLaVA-v1.5-7B.

## Qué encontró el validador

Sobre 30 patrones que GarmentCode da por válidos:

| Hallazgo | Casos | Veredicto |
| --- | --- | --- |
| Fruncido probable sin declarar | 258 | Aviso: intencional, pero indistinguible de un defecto |
| Desajuste de costura sin declarar | 111 | Error: entre 1% y 15%, muy chico para ser fruncido |
| Borde más corto que lo cortable | 51 | Error: hasta 0,07 cm |
| Esquina demasiado aguda | 15 | Error: solapas de 9° en mangas y cuellos |
| Auto-intersección | 2 | Error confirmado, y GarmentCode no lo detecta |
| Curvatura excesiva | 2 | Error: radio de 0,13 cm |

23 de los 30 patrones (77%) tienen al menos un error.

## Calibrar importó tanto como detectar

La primera versión rechazaba el 100% de los patrones. Revisando los casos uno
por uno aparecieron dos chequeos mal planteados:

1. **Pinzas leídas como defecto.** 143 de las "esquinas agudas" eran picos de
   pinza: dos bordes rectos de longitud idéntica juntándose en punta, que es
   construcción normal. El validador ahora reconoce esa firma y quedan 15
   esquinas, que sí son reales.
2. **Cruces contados en el vértice común.** La tolerancia se medía sobre el
   parámetro de la curva en vez de sobre la distancia, así que un cruce en el
   vértice compartido pasaba por defecto. Medida en centímetros, desapareció.

## Un error en GarmentCode

Su chequeo de auto-intersección hace esto:

```python
if t2 < t1:
    t1, t2 = t2, t1
if close_enough(t1, 0) and close_enough(t2, 1):
    intersect_t[i] = None
```

`t1` y `t2` son parámetros de **curvas distintas**, así que ordenarlos entre sí
no significa nada. Sumado a que lineariza los arcos con poca resolución, deja
pasar cruces reales. Los dos casos detectados se confirmaron linealizando a 48
tramos.

## Reproducir estos números

Los scripts están en `research/`, con su propio README. Las semillas están
fijadas, así que los resultados son reproducibles.
