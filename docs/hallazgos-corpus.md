# Hallazgos sobre GarmentCodeData v2

Medición del corpus publicado, no de patrones generados para la ocasión. Estos
números sustituyen a los de [`hallazgos-fase1.md`](hallazgos-fase1.md), que se
mantiene como registro de la fase 1 y se midió sobre 30 patrones.

Fecha: 21 de septiembre de 2026. Reproducible con la herramienta de barrido:

```bash
hilvan data/garmentcodedata_0 --lote --salida informe.json
```

## Qué se midió

El dataset se reparte en lotes de ~10 GB dentro de un share de 395 GB, y cada
lote empaqueta sus prendas en un único `data.tar.gz`, así que las
especificaciones no se pueden pedir sueltas. Se leyó el tar en streaming
descartando todo lo que no fuera una especificación de patrón: 5,12 GB
descargados, 96 MB escritos.

| | |
| --- | --- |
| Lote | `GarmentCodeData_v2/garments_5000_0` |
| Patrones, cuerpo neutro | 3.450 |
| Patrones, cuerpos aleatorios | 3.307 |
| Coste del barrido | ~35 s por lote en un núcleo |

Salvo donde se diga lo contrario, los números son del cuerpo neutro.

Son 115 veces la muestra de la fase 1. Y son patrones **ya filtrados por el
pipeline de los autores**: además de los chequeos de GarmentCode, sobrevivieron
a la simulación física. Es una muestra más limpia que la de la fase 1, no menos.

## Resultado

| | Patrones | % |
| --- | ---: | ---: |
| Limpios | 362 | 10,5 |
| Con algún error | 3.088 | **89,5** |

El 89,5% no es el titular honesto, porque mezcla dos cosas distintas. Un borde
de 0,02 cm no se puede cortar; un desajuste de costura sin declarar puede ser un
fruncido legítimo que nadie escribió. Separados:

| | Patrones | % |
| --- | ---: | ---: |
| Defecto geométrico duro | 705 | **20,4** |
| Solo falta la declaración de intención | 2.383 | 69,1 |
| Limpios | 362 | 10,5 |

**Uno de cada cinco patrones publicados tiene un defecto que impide fabricarlo**,
y eso después de pasar la simulación. Los otros dos tercios no son
necesariamente defectuosos: son indistinguibles de un defecto porque el formato
no guarda la intención.

### Defectos geométricos, por código

| Código | Patrones afectados | Casos |
| --- | ---: | ---: |
| `borde_degenerado` | 501 | 1.921 |
| `esquina_aguda` | 234 | 836 |
| `excede_ancho_rollo` | 4 | 8 |
| `auto_interseccion` | 3 | 6 |

El borde más corto del lote mide **0,018 cm**: 0,18 mm.

## Los hallazgos no son ruido de umbral

Si los valores se apelotonaran justo por debajo del límite, el resultado
dependería del umbral elegido y no de la prenda. No es el caso:

| Hallazgo | Umbral | Mediana | p10 | Mínimo |
| --- | ---: | ---: | ---: | ---: |
| `esquina_aguda` | 15° | 11,2° | 4,5° | 0,12° |
| `borde_degenerado` | 0,5 cm | 0,15 cm | 0,075 cm | 0,018 cm |
| `desajuste_no_declarado` | 1% | 5,6% | 1,7% | 1,0% |

Una fila por hallazgo, recalculada con `research/numeros_paper.py` el 24 de
septiembre de 2026. La versión anterior de esta tabla (mediana de borde 0,25 cm,
mínimo de esquina 0,16°) no salía de ningún script versionado y no se pudo
reproducir con el validador actual; estos son los valores que sí se reproducen.

La salvedad: el p90 de `esquina_aguda` es 14,7°, así que en torno a un
10% de esas esquinas desaparecería bajando el umbral un grado. Las medianas no.

## Filtrar el corpus, como lo proponía el roadmap, lo estropea

El plan era quedarse con los patrones que pasan limpio y entrenar sobre ellos.
Los limpios son 362 de 3.450, y comparados con los rechazados resultan
sistemáticamente más simples:

| Rasgo (mediana) | Limpios | Rechazados |
| --- | ---: | ---: |
| Paneles | 6 | 10 |
| Costuras | 14 | 30 |
| Bordes | 42 | 72 |
| Bordes curvos | 25% | 25% |

No es cuestión de curvatura — ese porcentaje es idéntico. Es tamaño. Y se ve
igual por tipo de prenda: las de cuerpo entero pasan limpias el 5,5% de las
veces y los torsos sin manga el 25,8%, casi cinco veces más.

### La causa no es que las prendas complejas estén peor hechas

Es la pregunta que decide qué hacer. Midiendo errores **por costura** en vez de
por patrón:

| Costuras | Patrones | % limpios | Errores/costura |
| --- | ---: | ---: | ---: |
| 0–10 | 466 | 29,6% | 0,264 |
| 10–20 | 599 | 17,5% | 0,221 |
| 20–30 | 732 | 8,5% | 0,209 |
| 30–40 | 652 | 6,9% | 0,186 |
| 40–55 | 662 | 1,7% | 0,191 |
| 55+ | 339 | 0,3% | 0,177 |

La tasa por costura es plana, y si acaso **baja**: las prendas grandes están
algo mejor hechas costura a costura. El desplome del porcentaje de limpios es
puro efecto de acumulación de un filtro binario sobre un patrón entero.

Un detalle que conviene no pasar por alto: los defectos **no son independientes
entre costuras**. Con 30 costuras y 0,209 errores por costura, la independencia
predice un 0,4% de patrones limpios (0,36%, con la mediana de 24 costuras del tramo 20–30) y se observa un 8,5%, unas 24 veces más. Hay
patrones sistemáticamente buenos y otros sistemáticamente malos, así que sí
existe señal de calidad por patrón — pero el filtro binario la confunde con el
tamaño.

### Qué filtro usar

| Criterio | Se queda con | Cuerpo entero | Torso | Abajo |
| --- | ---: | ---: | ---: | ---: |
| Corpus completo | 100% | 60,3% | 26,8% | 13,0% |
| Cero errores (lo propuesto) | 10,5% | **31,5%** | 45,6% | 22,9% |
| Tasa ≤ 0,05 errores/costura | 13,2% | 37,5% | 44,3% | 18,2% |
| Tasa ≤ 0,10 errores/costura | 25,8% | 48,1% | 33,3% | 18,6% |
| **Sin defecto geométrico** | **79,6%** | **58,2%** | 26,2% | 15,6% |

El filtro correcto es el último: descartar solo los patrones con un defecto
geométrico duro. Conserva más de siete veces más datos que el filtro binario (2.745 contra 362) y deja la
composición de la prenda casi intacta — 60,3% de cuerpo entero pasa a 58,2%,
frente al 31,5% que deja el filtro propuesto.

La razón es la misma que hacía engañoso el 89,5%: los desajustes sin declarar no
son defectos, son ambigüedad de formato, y usarlos como criterio de descarte es
lo que destruye el corpus.

## Los cuerpos atípicos no empeoran la geometría

GarmentCodeData genera cada diseño sobre un cuerpo neutro y sobre cuerpos
aleatorios. La hipótesis razonable era que el ajuste a medida degenerase en los
extremos de la distribución corporal — paneles que se estrechan hasta ser
incortables al adaptarse a una silueta poco común.

No ocurre. Los agregados son casi idénticos:

| | Cuerpo neutro | Cuerpos aleatorios |
| --- | ---: | ---: |
| Patrones | 3.450 | 3.307 |
| Limpios | 10,5% | 10,1% |
| Con defecto geométrico | 20,4% | 21,2% |
| Errores por costura | 0,195 | 0,198 |

Un agregado puede esconder el efecto si los dos lotes tienen diseños distintos,
así que la comparación se hizo **pareada** sobre los 2.953 diseños presentes en
ambos, que aísla el cuerpo dejando el diseño fijo:

«Roto» aquí significa con defecto geométrico duro.

| Mismo diseño | Casos |
| --- | ---: |
| Limpio en los dos | 2.248 |
| Roto solo en cuerpo aleatorio | 139 |
| Roto solo en cuerpo neutro | 142 |
| Roto en los dos | 424 |

Los discordantes se reparten 139 contra 142. McNemar exacto da **p = 0,91**, y la
diferencia pareada (aleatorio menos neutro) es de −0,1 puntos con un IC95 de
[−1,2; 1,0]: no hay asimetría detectable, y la que los datos admiten es pequeña. La media de defectos de más en
cuerpo aleatorio es −0,050 por diseño, es decir, ligeramente a favor del cuerpo
aleatorio.

**Los defectos son propiedad del diseño, no del ajuste.** Las tasas marginales en los diseños
pareados son 19,2% (neutro) y 19,1% (aleatorio). Si fuera el cuerpo el que
decide qué diseño se rompe, los dos resultados serían casi independientes y un
diseño saldría roto en ambos unas 108 veces. Sale roto en ambos 424 veces, 3,9
veces más. (Que 139 + 142 + 424 sume 705, igual que los patrones con defecto
duro del cuerpo neutro, es coincidencia: son conjuntos distintos.)

Tiene dos consecuencias prácticas. Para sanear el corpus no hace falta ponderar
por tipo de cuerpo. Y para atribuir la culpa, los defectos vienen del programa
paramétrico que define la prenda, no de casos límite al tomar medidas — lo que
también los hace reproducibles y arreglables en origen.

## Lo que este barrido no dice

- **Un lote de veinticuatro**, aunque con sus dos mitades de cuerpo medidas.
- **El nivel 2 juzga con reservas.** Ningún patrón declara `orient`, así que el
  montaje usa el convenio por defecto y los veredictos bajan de error a aviso.
  Ese convenio no es una conjetura: ver abajo.
- **Los umbrales siguen sin calibrar** contra tela real. Las medianas están
  lejos del límite, lo que hace el resultado robusto al valor exacto, pero no
  convierte la hipótesis en medida.

## El convenio de orientación se sostiene en todo el corpus

El montaje depende de qué extremo de un borde se cose con cuál, y el formato no
lo dice. El validador usa `reversed` por defecto, un supuesto que hasta ahora se
apoyaba en dos prendas de referencia.

Medido sobre los 3.450 patrones con el criterio de que un borde libre solo puede
continuar en otro borde libre:

| | Patrones | % |
| --- | ---: | ---: |
| Favorecen `reversed` | 3.310 | 95,9 |
| Favorecen `direct` | **0** | 0,0 |
| Empate | 140 | 4,1 |

Cero contraejemplos, con una mediana de 8 cruces de ventaja. Deja de ser una
conjetura y pasa a ser un convenio medido de la salida de GarmentCode.

No lo convierte en garantía del formato — otro generador podría usar otro orden
— así que el validador sigue marcando el montaje como supuesto. Pero en vez de
callarse, emite el veredicto rebajado a aviso: el corpus lo respalda aunque el
patrón no lo afirme.

## Licencia

Sin resolver, y no por falta de búsqueda: **GarmentCodeData no declara licencia**
en el share, ni en `Dataset_documentation_v2.pdf`, ni en la página del proyecto.
La ficha de ETH Research Collection ([DOI
10.3929/ethz-b-000690432](https://doi.org/10.3929/ethz-b-000690432)), que es
donde viviría la declaración de derechos, devolvía HTTP 500 el día de la
medición. El código de GarmentCode sí es MIT; el dataset es otra cosa.

Lo único explícito es la obligación de citar:

> Korosteleva, Kesdogan, Kemper, Wenninger, Koller, Zhang, Botsch,
> Sorkine-Hornung. *GarmentCodeData: A Dataset of 3D Made-to-Measure Garments
> With Sewing Patterns*. ECCV 2024.

Consecuencia práctica, que separa dos usos que el [roadmap](roadmap.md) daba por
equivalentes:

- **Medir y publicar estadísticas**: sin problema bajo cualquier lectura. Es uso
  de investigación con cita y no redistribuye nada.
- **Publicar un subconjunto filtrado**: eso es redistribución y no se puede
  asumir. Hay que preguntar a los autores antes.

## Nota sobre la v2

La documentación del dataset dice que en v2 hubo *"improvements in the stitching
process [that] now lead to fewer fails due to incorrect stitch matching"* y
*"additional effort... ensuring the matching of the side stitches on full-body
garments"*.

Es decir: los autores ya sabían del problema de calce de costuras y trabajaron
sobre él. Lo que mide este barrido es lo que queda después de ese esfuerzo.
