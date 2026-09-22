"""Reconstruye las 100 prendas del corpus con GarmentCodeRC y las mide.

Este es el control que hace honesta la medida de ChatGarment. El modelo no
emite geometria sino parametros de diseno, asi que sus salidas pasan por
GarmentCodeRC antes de poder validarse y el numero mediria la pareja
modelo+sintetizador. Pasando los parametros *verdaderos* por el mismo
sintetizador se separa una cosa de la otra: lo que aparezca aqui es del
sintetizador, y lo que ChatGarment tenga de mas es suyo.

    python chatgarment_reconstruir.py /ruta/al/lote /ruta/a/GarmentCodeRC

Escribe las especificaciones en <lote>/reconstruido/ y un informe al lado.
"""
import json
import sys
import time
from pathlib import Path

import yaml


def main(lote, garmentcode):
    lote, gc = Path(lote), Path(garmentcode).expanduser()
    # assets/ y pygarment/ son dos carpetas sueltas del clon, no paquetes
    # instalados: el import solo funciona con la raiz del repo en el path.
    sys.path.insert(1, str(gc))
    from assets.garment_programs.meta_garment import MetaGarment
    from assets.bodies.body_params import BodyParameters
    from hilvan import Limites
    from hilvan.corpus import validar_archivo

    destino = lote / "reconstruido"
    destino.mkdir(exist_ok=True)
    cuerpo = BodyParameters(str(gc / "assets" / "bodies" / "mean_all.yaml"))
    lim = Limites()

    filas, rotos = [], []
    t0 = time.time()
    for i, f in enumerate(sorted(lote.glob("*_design_params.yaml"))):
        pid = f.name.split("_")[1]
        try:
            design = yaml.safe_load(f.read_text())["design"]
            patron = MetaGarment(f"rand_{pid}", cuerpo, design).assembly()
            carpeta = patron.serialize(str(destino), tag="", to_subfolder=True,
                                       with_3d=False, with_text=False, view_ids=False)
            spec = next(Path(carpeta).glob("*_specification.json"))
        except Exception as e:                      # noqa: BLE001 - un fallo es un dato
            rotos.append({"prenda": pid, "error": f"{type(e).__name__}: {e}"})
            continue
        # validar_archivo ya devuelve el resumen, con "archivo" delante
        h = validar_archivo(spec, lim)
        filas.append({"prenda": pid, **{k: v for k, v in h.items() if k != "archivo"}})
        if (i + 1) % 20 == 0:
            print(f"  {i+1} prendas, {time.time()-t0:.0f}s", flush=True)

    informe = {"lote": str(lote), "reconstruidas": len(filas), "rotos": rotos,
               "filas": filas}
    salida = lote / "informe_reconstruido.json"
    salida.write_text(json.dumps(informe, indent=1))
    print(f"\n{len(filas)} reconstruidas, {len(rotos)} fallidas en {time.time()-t0:.0f}s")
    print(f"-> {salida}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
