"""Baja render frontal y parametros de diseno de las primeras N prendas del corpus.

Las specs ya estan en data/garmentcodedata_0 con los mismos nombres, asi que solo
falta lo que aquel barrido descarto. El tar viene ordenado por prenda: se corta al
llegar a N y no se descargan los 5,12 GB enteros.
"""
import sys, tarfile, time, urllib.request
from pathlib import Path

N = int(sys.argv[2]) if len(sys.argv) > 2 else 100
DESTINO = Path(sys.argv[1]); DESTINO.mkdir(parents=True, exist_ok=True)
URL = ("https://libdrive.ethz.ch/public.php/webdav/GarmentCodeData_v2/"
       "garments_5000_0/default_body/data.tar.gz")
g = urllib.request.HTTPPasswordMgrWithDefaultRealm()
g.add_password(None, "https://libdrive.ethz.ch/", "4UtC8smtLOGwKoZ", "")
op = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(g))

t0 = time.time(); prendas = set(); sacados = 0
with op.open(URL, timeout=180) as flujo, tarfile.open(fileobj=flujo, mode="r|gz") as tar:
    for m in tar:
        if not m.isfile():
            continue
        # el id va en el propio nombre de archivo (rand_XXXX_loquesea);
        # la ruta dentro del tar no siempre trae el prefijo ./ de carpeta
        prenda = Path(m.name).name.split("_")[1]
        if prenda not in prendas:
            if len(prendas) >= N:
                break
            prendas.add(prenda)
        if not m.name.endswith(("_render_front.png", "_design_params.yaml")):
            continue
        f = tar.extractfile(m)
        if f is None:
            continue
        (DESTINO / Path(m.name).name).write_bytes(f.read())
        sacados += 1
        if sacados % 40 == 0:
            print(f"{len(prendas):4} prendas | {sacados:4} archivos | {time.time()-t0:5.0f}s", flush=True)
print(f"LISTO: {len(prendas)} prendas, {sacados} archivos en {time.time()-t0:.0f}s -> {DESTINO}", flush=True)
