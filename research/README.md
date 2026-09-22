# Bancos de investigación

Los scripts que produjeron los números de `docs/hallazgos-fase1.md`. A
diferencia del paquete `fashion_validator`, **estos sí necesitan GarmentCode**,
porque generan los patrones que luego analizan.

## Montaje

```bash
git clone https://github.com/maria-korosteleva/GarmentCode.git
cd GarmentCode
pip install "numpy<2" scipy pyyaml svgwrite svgpathtools psutil matplotlib CairoSVG
pip install -e /ruta/a/fashion-validator
```

Crea un `system.json` en la raíz del clon a partir de `system.template.json`
(basta con que `output` apunte a una carpeta existente). Luego copia estos
scripts a la raíz del clon, o añádela al `PYTHONPATH`, y ejecútalos desde ahí:

```bash
cp /ruta/a/fashion-validator/research/*.py .
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

Los `aipparel_*` no usan GarmentCode sino el repositorio de AIpparel y su
checkpoint, y son los que produjeron `docs/hallazgos-aipparel.md`:

| Script | Qué hace |
| --- | --- |
| `aipparel_traer_renders.py` | Baja renders y `design_params` de N prendas del corpus |
| `aipparel_entradas.py` | Arma el JSON de inferencia: cada prenda como imagen y como texto |
| `aipparel_medir.py` | Mide los tres grupos con la misma vara |
| `aipparel_contraste.py` | McNemar pareado y tasa de desajuste por costura |

`aipparel_entradas.py --demo` comprueba la generación de descripciones sin
tocar el corpus.

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
