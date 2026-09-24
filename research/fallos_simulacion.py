"""¿El lote medido incluye patrones cuya simulacion fallo?

    python research/fallos_simulacion.py data/garmentcodedata_0 dataset_properties_default_body.yaml

Cada lote de GarmentCodeData publica, junto al `data.tar.gz`, un
`dataset_properties_<cuerpo>.yaml` con la lista de prendas que fallaron en la
simulacion (`sim.stats.fails`, por motivo). Se baja por WebDAV del mismo enlace
publico que usa `sanear_corpus.py`:

    curl -u 4UtC8smtLOGwKoZ: -O https://libdrive.ethz.ch/public.php/webdav/\
GarmentCodeData_v2/garments_5000_0/default_body/dataset_properties_default_body.yaml

Si la interseccion con las especificaciones medidas es vacia, el archivo solo
trae prendas que sobrevivieron a la simulacion y no hace falta filtrar nada.
"""
import sys
from pathlib import Path

import yaml

carpeta, props = Path(sys.argv[1]), yaml.safe_load(open(sys.argv[2], encoding="utf-8"))
ids = {r.name.removesuffix("_specification.json") for r in carpeta.glob("*specification.json")}
fallos = props["sim"]["stats"]["fails"]
unicos = set().union(*(set(v or []) for v in fallos.values()))

for motivo, lista in fallos.items():
    if lista:
        print(f"{motivo:26} {len(lista):5}  medidos entre ellos: {len(set(lista) & ids)}")
print(f"\ndisenos en el lote: {props['size']}   fallos unicos: {len(unicos)}   "
      f"especificaciones medidas: {len(ids)}   interseccion: {len(unicos & ids)}")
