# La métrica aplicada a un modelo publicado

Primera medida del uso 5 de la [hoja de ruta](roadmap.md): qué porcentaje de lo
que genera un modelo del estado del arte se puede coser. El modelo es
[AIpparel](https://georgenakayama.github.io/AIpparel/), que genera geometría
directa —vértices y costuras, no parámetros—, así que sus salidas entran en el
validador sin conversión.

Fecha: 22 de septiembre de 2026. Corrida de 200 inferencias en una RTX de 16 GB,
~10 s por muestra más 4 min de carga del modelo.

## Qué se midió

100 prendas de `GarmentCodeData_v2/garments_5000_0`, cada una por dos vías:

| Grupo | Entrada al modelo |
| --- | --- |
| **imagen** | El render frontal que el corpus publica de esa prenda |
| **texto** | Una descripción derivada de los `design_params` de esa misma prenda |
| **corpus** | Ninguna: es el patrón original, el ground truth |

El emparejamiento es deliberado. Los tres grupos describen las mismas 100
prendas, así que la comparación aísla el modo de entrada y no el reparto de
prendas. Y que el ground truth pase por el mismo validador es lo que hace
interpretable el resultado: sin esa columna, un 0% no distingue entre un modelo
que falla y una vara imposible de superar.

## El resultado

| | Manufacturable | Sin defecto duro | Errores por patrón |
| --- | ---: | ---: | ---: |
| AIpparel, desde imagen | **0,0%** | 23,0% | 24,9 |
| AIpparel, desde texto | **0,0%** | 17,0% | 21,2 |
| Corpus (ground truth) | 12,0% | 78,0% | 5,8 |

Ninguno de los 200 patrones generados es manufacturable. Con 0 de 200, la
cota superior exacta unilateral del 95% (Clopper-Pearson) es 1,49%, y el
intervalo bilateral del 95% llega hasta el 1,83%: aunque la corrida hubiera
tenido suerte en contra, la tasa real no puede ser alta.

«Defecto duro» son los que dependen solo de la geometría del panel y no de una
intención que el formato no guarda: `borde_degenerado`, `esquina_aguda`,
`curvatura_excesiva`, `excede_ancho_rollo`, `auto_interseccion`. Es el mismo
corte que separa el 20,4% del corpus en
[`hallazgos-corpus.md`](hallazgos-corpus.md).

## El modo de entrada no cambia nada

Los 6 puntos entre imagen (23%) y texto (17%) invitan a concluir que la imagen
lleva más información. No aguantan el contraste. Como las prendas están
pareadas, lo que corresponde es mirar los casos discordantes:

| | Prendas |
| --- | ---: |
| Limpias solo por imagen | 17 |
| Limpias solo por texto | 11 |
| **McNemar exacto** | **p = 0,345** |

Indistinguible de ruido. Con estos datos no se puede afirmar que condicionar por
imagen produzca patrones más cosibles que condicionar por texto.

## No cose más: cose peor

«24,9 errores por patrón» contra «5,8» no significa nada por sí solo, porque un
patrón con el doble de costuras tiene el doble de oportunidades de fallar. La
tasa por costura sí es comparable:

| | Costuras por patrón | Costuras que no cierran |
| --- | ---: | ---: |
| AIpparel, desde imagen | 31,6 | **88%** |
| AIpparel, desde texto | 26,8 | **86%** |
| Corpus | 31,5 | 33% |

AIpparel produce patrones de la misma complejidad que el corpus —31,6 costuras
contra 31,5— y falla en casi todas ellas. Nueve de cada diez costuras unen dos
bordes de longitudes distintas sin declarar fruncido.

El mecanismo es visible en la arquitectura: el modelo emite los vértices de cada
panel de forma independiente y nada en la representación acopla los dos bordes
de una costura. Que el patrón *parezca* la prenda pedida y que sus costuras
*cierren* son dos objetivos distintos, y el entrenamiento solo optimiza el
primero.

## Lo que este número no dice

- **Es un modelo, un checkpoint, 100 prendas.** No es una comparación entre
  modelos hasta que haya un segundo modelo medido igual.
- **Las descripciones son sintéticas**, derivadas de los `design_params`, no
  escritas por una persona. Podrían ser peores que una descripción natural; eso
  penalizaría al modo texto, que es justo el que no resultó distinto.
- **El número probablemente favorece a AIpparel.** Se entrenó sobre
  GarmentCodeData, y estas 100 prendas salen de ese mismo dataset: si estaban en
  su conjunto de entrenamiento, 0% es el resultado en el caso más benigno.
- **El validador supone el convenio `reversed`** para el montaje, porque ningún
  patrón declara `orient`. El supuesto se aplica igual a los tres grupos, así que
  el sesgo, si lo hay, es común.
- **Un patrón no manufacturable no es un patrón inútil.** Un desajuste del 2% lo
  corrige un patronista sin pensar. Lo que el número mide es cuánto trabajo queda
  después del modelo, no si el modelo sirve.

## Reproducir

Los cuatro scripts están en [`research/`](../research/). Necesitan el repositorio
de AIpparel y su checkpoint; el validador no.

```bash
python research/aipparel_traer_renders.py /ruta/lote100 100   # renders y design_params
python research/aipparel_entradas.py /ruta/lote100      # arma las 200 entradas
# ... correr scripts/inference.py de AIpparel sobre inference_200.json ...
python research/aipparel_medir.py    SALIDA indice.json data/garmentcodedata_0
python research/aipparel_contraste.py SALIDA indice.json data/garmentcodedata_0
```

Sobre una GPU de 16 GB hace falta cargar el checkpoint con `mmap=True`: viene en
fp32 y `torch.load` sin mmap reserva 25 GiB de memoria anónima, más de la que
tiene una WSL por defecto.
