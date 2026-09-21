# Hallazgos sobre GarmentCodeData v2

Medición del corpus publicado, no de patrones generados para la ocasión. Estos
números sustituyen a los de [`hallazgos-fase1.md`](hallazgos-fase1.md), que se
mantiene como registro de la fase 1 y se midió sobre 30 patrones.

Fecha: 21 de septiembre de 2026. Reproducible con la herramienta de barrido:

```bash
fashion-validator data/garmentcodedata_0 --lote --salida informe.json
```

## Qué se midió

El dataset se reparte en lotes de ~10 GB dentro de un share de 395 GB, y cada
lote empaqueta sus prendas en un único `data.tar.gz`, así que las
especificaciones no se pueden pedir sueltas. Se leyó el tar en streaming
descartando todo lo que no fuera una especificación de patrón: 5,12 GB
descargados, 96 MB escritos.

| | |
| --- | --- |
| Lote | `GarmentCodeData_v2/garments_5000_0/default_body` |
| Patrones extraídos | 3.450 |
| Coste del barrido | ~35 s en un núcleo |

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
| `esquina_aguda` | 15° | 11,5° | 4,3° | 0,16° |
| `borde_degenerado` | 0,5 cm | 0,25 cm | 0,07 cm | 0,024 cm |
| `desajuste_no_declarado` | 1% | 5,9% | 1,8% | 1,0% |

La salvedad honesta: el p90 de `esquina_aguda` es 14,9°, así que en torno a un
10% de esas esquinas desaparecería bajando el umbral un grado. Las medianas no.

## Lo que este barrido no dice

- **Un lote de veinticuatro, y solo `default_body`.** La otra mitad de cada lote
  son cuerpos aleatorios, que podrían comportarse distinto.
- **El nivel 2 no emitió ningún veredicto.** Ningún patrón declara `orient`, así
  que el montaje es supuesto y las aberturas se miden pero no se juzgan: 3.450
  avisos de `montaje_supuesto`, uno por patrón.
- **Los umbrales siguen sin calibrar** contra tela real. Las medianas están
  lejos del límite, lo que hace el resultado robusto al valor exacto, pero no
  convierte la hipótesis en medida.

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
