"""Mide con la misma vara los patrones de ChatGarment, el corpus y el control.

Cuatro grupos sobre las mismas 100 prendas:

    corpus    el patron original de GarmentCodeData
    recon     esos mismos parametros pasados por GarmentCodeRC
    imagen    ChatGarment desde el render
    texto     ChatGarment desde las etiquetas de sus design_params

`recon` es la columna que separa el modelo del sintetizador. ChatGarment emite
parametros, no geometria, asi que sus salidas tienen que pasar por GarmentCodeRC
antes de poder validarse; sin esta columna no se sabria si un defecto lo pone el
modelo o el programa que dibuja el patron.

La unidad es la prenda, no el archivo. ChatGarment parte un conjunto en dos
especificaciones (arriba y abajo) mientras que el corpus lo guarda en una: una
prenda cuenta como manufacturable solo si *todas* sus especificaciones lo son.
Contar archivos premiaria al modelo por trocear.

    python chatgarment_medir.py <lote> <dir_corpus> texto=<dir> imagen=<dir>
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

from hilvan import DUROS, Limites
from hilvan.corpus import validar_archivo

LIM = Limites()


def prenda_de(ruta):
    """El codigo de prenda que le corresponde a una especificacion.

    Vale tanto para rand_XXXXXXXXXX_specification.json como para las carpetas
    valid_garment_<codigo>/ que escribe ChatGarment.
    """
    s = str(ruta)
    m = re.search(r"rand_([A-Z0-9]{10})", s)
    if m:
        return m.group(1)
    for p in ruta.parents:
        m = re.fullmatch(r"valid_garment_([A-Z0-9]{10})", p.name)
        if m:
            return m.group(1)
    return None


def medir(rutas_por_prenda):
    """Agrega por prenda: limpia solo si todas sus especificaciones lo son."""
    codigos = Counter()
    limpias = sin_duro = errores = n = 0
    ilegibles = []
    for pid, rutas in sorted(rutas_por_prenda.items()):
        res = [validar_archivo(r, LIM) for r in rutas]
        malos = [r for r in res if "ilegible" in r or "fallo" in r]
        if malos:
            ilegibles.append({"prenda": pid,
                              "motivo": malos[0].get("ilegible") or malos[0].get("fallo")})
            continue
        n += 1
        errores += sum(r["errores"] for r in res)
        propios = Counter()
        for r in res:
            propios.update(r["por_codigo"])
        codigos.update(propios)
        if all(r["validado"] for r in res):
            limpias += 1
        if not (DUROS & set(propios)):
            sin_duro += 1
    return {"n": n, "limpios": limpias, "sin_duro": sin_duro,
            "errores_por_patron": round(errores / n, 1) if n else None,
            "ilegibles": ilegibles,
            "por_codigo": dict(codigos.most_common())}


def agrupar(rutas):
    por_prenda = {}
    for r in rutas:
        pid = prenda_de(r)
        if pid:
            por_prenda.setdefault(pid, []).append(r)
    return por_prenda


def main(argv):
    lote, corpus = Path(argv[0]), Path(argv[1])
    grupos = {
        "corpus": agrupar(sorted(corpus.glob("rand_*_specification.json"))),
        "recon": agrupar(sorted((lote / "reconstruido").rglob("*_specification.json"))),
    }
    for arg in argv[2:]:
        nombre, _, ruta = arg.partition("=")
        grupos[nombre] = agrupar(sorted(Path(ruta).rglob("*_specification.json")))

    # el corpus trae las 3.450 prendas del lote descargado, no solo las 100
    del_lote = {p.name.split("_")[1] for p in lote.glob("*_design_params.yaml")}
    grupos["corpus"] = {k: v for k, v in grupos["corpus"].items() if k in del_lote}

    print(f"{'grupo':8} {'prendas':>8} {'manufacturable':>16} {'sin defecto duro':>18} "
          f"{'errores/prenda':>15}")
    informe = {}
    for nombre, por_prenda in grupos.items():
        d = medir(por_prenda)
        informe[nombre] = d
        if not d["n"]:
            print(f"{nombre:8} {0:>8}   (sin patrones)")
            continue
        print(f"{nombre:8} {d['n']:>8} {d['limpios']:>9} ({100*d['limpios']/d['n']:5.1f}%) "
              f"{d['sin_duro']:>10} ({100*d['sin_duro']/d['n']:5.1f}%) "
              f"{d['errores_por_patron']:>15}")

    print("\ncodigos mas frecuentes por grupo")
    for nombre, d in informe.items():
        top = list(d["por_codigo"].items())[:6]
        print(f"  {nombre:8}", ", ".join(f"{k} x{v}" for k, v in top) or "-")
        if d["ilegibles"]:
            print(f"           {len(d['ilegibles'])} prendas ilegibles o fallidas")

    destino = lote / "informe_chatgarment.json"
    destino.write_text(json.dumps(informe, indent=1, ensure_ascii=False))
    print("\n->", destino)


def demo():
    """Comprobacion: el codigo de prenda sale de las dos formas de nombrar."""
    assert prenda_de(Path("/x/rand_00YONAPXZE_specification.json")) == "00YONAPXZE"
    assert prenda_de(Path("/x/vis_new/valid_garment_00YONAPXZE/valid_garment_upper/"
                          "valid_garment_upper_specification.json")) == "00YONAPXZE"
    assert prenda_de(Path("/x/valid_garment_rand_023FMIGQK0_render_front/"
                          "valid_garment_lower/valid_garment_lower_specification.json")) \
        == "023FMIGQK0"
    assert prenda_de(Path("/x/valid_garment_upper/algo_specification.json")) is None

    # una prenda con dos especificaciones cuenta como una, y basta que falle una
    rutas = {"AAA": [Path("a"), Path("b")]}
    assert list(agrupar([Path("/x/rand_AAAAAAAAAA_specification.json")])) == ["AAAAAAAAAA"]
    assert len(rutas["AAA"]) == 2
    print("demo ok")


if __name__ == "__main__":
    if sys.argv[1] == "--demo":
        demo()
    else:
        main(sys.argv[1:])
