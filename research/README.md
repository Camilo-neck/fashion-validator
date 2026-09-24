# Bancos de investigación

Los scripts que produjeron los números de `docs/hallazgos-fase1.md`. A
diferencia del paquete `hilvan`, **estos sí necesitan GarmentCode**,
porque generan los patrones que luego analizan.

## Montaje

```bash
git clone https://github.com/maria-korosteleva/GarmentCode.git
cd GarmentCode
pip install "numpy<2" scipy pyyaml svgwrite svgpathtools psutil matplotlib CairoSVG
pip install -e /ruta/a/hilvan
```

Crea un `system.json` en la raíz del clon a partir de `system.template.json`
(basta con que `output` apunte a una carpeta existente). Luego copia estos
scripts a la raíz del clon, o añádela al `PYTHONPATH`, y ejecútalos desde ahí:

```bash
cp /ruta/a/hilvan/research/*.py .
python run_batch.py 30
```

No hace falta GPU. La parte 3D de GarmentCode (el simulador basado en NVIDIA
Warp) no se usa aquí.

## Qué hace cada uno

| Script | Pregunta que responde |
| --- | --- |
| `sampler.py` | ¿Qué proporción del espacio de diseño produce patrones válidos? |
| `seamcheck.py` | ¿Cuánto se desajustan las longitudes de los bordes cosidos? |
| `ruffle_test.py` | ¿Ese desajuste se explica por los fruncidos? |
| `run_batch.py` | ¿Qué encuentra el validador en patrones que GarmentCode aprueba? |
| `inspect_case.py` | Aísla casos de un código concreto para revisarlos a mano |
| `check_arc_fp.py` | Contrasta intersecciones de arcos exactas contra linealizadas |
| `sanear_corpus.py` | Mide GarmentCodeData entero sobre el flujo, sin bajarlo a disco |

`sanear_corpus.py` es el único que no necesita GarmentCode ni nada local: los 36
lotes del corpus son ~170 GB comprimidos, así que cada uno se descomprime en
memoria, se valida prenda a prenda y se tira. Lo que queda en disco es un JSONL
por lote con el veredicto, unos 25 MB en total. Se puede cortar y retomar: un
lote a medias se queda en `.part` y se reintenta entero.

```bash
python sanear_corpus.py /ruta/destino          # los 36 lotes, ~3,3 h de descarga
python sanear_corpus.py /ruta/destino 0-5      # solo algunos
python sanear_corpus.py /ruta/destino --resumen
```


Los `aipparel_*` no usan GarmentCode sino el repositorio de AIpparel y su
checkpoint, y son los que produjeron `docs/hallazgos-aipparel.md`:

| Script | Qué hace |
| --- | --- |
| `aipparel_traer_renders.py` | Baja renders y `design_params` de N prendas del corpus |
| `aipparel_entradas.py` | Arma el JSON de inferencia: cada prenda como imagen y como texto |
| `aipparel_medir.py` | Mide los tres grupos con la misma vara |
| `aipparel_contraste.py` | McNemar pareado y tasa de desajuste por costura |

Los `chatgarment_*` usan el repositorio de ChatGarment y
[GarmentCodeRC](https://github.com/biansy000/GarmentCodeRC), su fork de
GarmentCode. ChatGarment emite parámetros de diseño y no geometría, así que sus
salidas pasan por GarmentCodeRC antes de poder validarse:

| Script | Qué hace |
| --- | --- |
| `chatgarment_parches.py` | Adapta el clon al hardware local y quita la llamada a GPT-4o |
| `chatgarment_entradas.py` | Arma el dict de etiquetas desde los `design_params` |
| `chatgarment_reconstruir.py` | Pasa los parámetros *verdaderos* por GarmentCodeRC: el control |
| `chatgarment_medir.py` | Mide los cuatro grupos por prenda, no por archivo |

`chatgarment_reconstruir.py` es lo que separa el modelo del sintetizador. Sin
esa columna, un defecto en la salida de ChatGarment no se sabe si lo puso el
modelo o el programa que dibuja el patrón. Medido sobre las 100 prendas, el
sintetizador coincide con el original en 99 de 100 veredictos; el desarrollo
está en [`docs/hallazgos-sintetizador.md`](../docs/hallazgos-sintetizador.md).

`aipparel_entradas.py --demo`, `chatgarment_entradas.py --demo` y
`chatgarment_medir.py --demo` comprueban su lógica sin tocar el corpus.

`inspect_case.py` y `check_arc_fp.py` existen porque hicieron falta: la
primera versión del validador rechazaba el 100% de los patrones, y solo
mirando los casos uno por uno se vio que estaba leyendo las pinzas como
defectos.

```bash
python inspect_case.py esquina_aguda 30
python check_arc_fp.py 30
```

## Nota sobre el muestreo aleatorio

`sampler.py` recorre el espacio de parámetros al azar, que no es lo mismo que
lo que produciría un modelo condicionado por un texto. Sirve para medir cuánto
del espacio es inválido, no para predecir la tasa de acierto de un generador
entrenado.
