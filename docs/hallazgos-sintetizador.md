# ¿El sintetizador añade defectos?

Medir un modelo que emite geometría es directo: sale un patrón y se valida. Medir
uno que emite **parámetros** no lo es. ChatGarment produce una configuración de
diseño, no paneles, así que su salida tiene que pasar por GarmentCode antes de
poder validarse — y entonces el número mide la pareja modelo+sintetizador, no el
modelo.

Eso se venía declarando como una limitación. Es medible, y está medido.

## El experimento

Las mismas 100 prendas de [`hallazgos-aipparel.md`](hallazgos-aipparel.md), por
dos caminos distintos hasta el mismo validador:

```
corpus   design_params → GarmentCode (original)  → specification.json → hilvan
recon    design_params → GarmentCodeRC (el fork) → specification.json → hilvan
```

`recon` usa el mismo código que usará ChatGarment:
[GarmentCodeRC](https://github.com/biansy000/GarmentCodeRC), el fork refinado que
el modelo trae consigo. La entrada son los parámetros **verdaderos** de cada
prenda, no los que predeciría un modelo. Si los dos caminos coinciden, el
sintetizador no pone nada de su parte y lo que un modelo falle será suyo.

Las 100 se reconstruyeron sin una sola excepción, en 121 s sobre un núcleo.

## El resultado

| grupo | manufacturable | sin defecto duro | errores/prenda |
| --- | ---: | ---: | ---: |
| corpus (GarmentCode original) | 12 / 100 | 78 % | 5,8 |
| recon (GarmentCodeRC) | 13 / 100 | 80 % | 5,6 |

Los agregados casi no se mueven, pero dos porcentajes parecidos pueden esconder
prendas que se compensan. Pareado, prenda contra prenda:

| coincidencia | prendas |
| --- | ---: |
| mismo veredicto de manufacturabilidad | **99 / 100** |
| mismo estado de defecto duro | 98 / 100 |
| número exacto de errores idéntico | 90 / 100 |

En las 10 donde el conteo difiere, 7 bajan y 3 suben. Es coherente con que
GarmentCodeRC sea un fork *refinado*: corrige más de lo que rompe.

## Qué autoriza a decir

**El sintetizador aporta del orden de un punto porcentual.** Medir un modelo de
parámetros a través de GarmentCodeRC sigue midiendo la pareja, pero ahora se sabe
cuánto vale el segundo término. Un modelo que saque 0% no lo saca porque el
sintetizador lo hunda.

Eso convierte la asimetría de una advertencia en una cota, que es lo que hacía
falta para que comparar un modelo de geometría con uno de parámetros signifique
algo.

## Qué no dice

**No es una medida de ChatGarment.** La entrada fueron parámetros verdaderos. Lo
único que se midió es el tramo que va de unos parámetros correctos a un patrón.

**Un modelo puede fallar de formas que esto no cubre.** Si predice parámetros
fuera de rango o incoherentes entre sí, GarmentCodeRC puede reaccionar peor que
con parámetros del corpus. Esta cota vale para el camino feliz; el número final
la incluirá de todos modos, porque saldrá del mismo validador.

**Un fork refinado no es el original.** Las 10 prendas donde el conteo difiere
dicen que GarmentCodeRC y GarmentCode no son el mismo programa. Para comparar
contra las cifras del corpus hay que usar la columna `recon`, no la `corpus`.

## Reproducir

```bash
python research/chatgarment_reconstruir.py /ruta/al/lote /ruta/a/GarmentCodeRC
python research/chatgarment_medir.py /ruta/al/lote /ruta/al/corpus
```

El primero escribe las especificaciones en `<lote>/reconstruido/`. El segundo las
mide junto al corpus y admite grupos extra como `texto=<dir>` cuando haya salida
de un modelo. Los scripts están en [`research/`](../research/).
