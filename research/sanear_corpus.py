"""Mide GarmentCodeData entero sin llegar a guardarlo.

El corpus son 36 lotes de ~4,7 GB comprimidos. Bajarlos y despues recorrerlos
pediria 170 GB de disco para leer unos JSON que ocupan una centesima parte de
eso, asi que cada lote se valida sobre el flujo: se descomprime en memoria, se
mira la especificacion de cada prenda y se tira. Lo unico que queda en disco es
el veredicto, una linea por prenda.

    python sanear_corpus.py <destino> [lotes] [--cuerpo default_body]

`lotes` admite "0-35", "0,4,9" o una mezcla. Cada lote se escribe en su propio
JSONL y se salta si ya esta completo, asi que la descarga se puede cortar y
retomar. Con el manifiesto hecho:

    python sanear_corpus.py <destino> --resumen

que es lo que responde cuantas prendas sobreviven a cada filtro.
"""
import json
import re
import sys
import tarfile
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

from hilvan import DUROS, Limites, resumen, validar

URL = ("https://libdrive.ethz.ch/public.php/webdav/GarmentCodeData_v2/"
       "garments_5000_{lote}/{cuerpo}/data.tar.gz")
USUARIO = "4UtC8smtLOGwKoZ"   # el enlace publico del dataset, sin contrasena
LIM = Limites()


def abridor():
    g = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    g.add_password(None, "https://libdrive.ethz.ch/", USUARIO, "")
    return urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(g))


def expandir(spec):
    """"0-3,7" -> [0, 1, 2, 3, 7]. Un rango al reves se lee como vacio."""
    salida = []
    for trozo in spec.split(","):
        trozo = trozo.strip()
        if not trozo:
            continue
        if "-" in trozo:
            a, b = trozo.split("-", 1)
            salida.extend(range(int(a), int(b) + 1))
        else:
            salida.append(int(trozo))
    return salida


def prenda_de(nombre):
    """rand_XXXXXXXXXX_specification.json -> XXXXXXXXXX."""
    m = re.search(r"rand_([A-Z0-9]+)_specification\.json$", nombre)
    return m.group(1) if m else None


def medir_lote(lote, cuerpo, destino, op):
    """Valida un lote sobre el flujo. Devuelve el numero de prendas medidas."""
    final = destino / f"lote_{lote}_{cuerpo}.jsonl"
    if final.exists():
        n = sum(1 for _ in final.open(encoding="utf-8"))
        print(f"lote {lote:>2}: ya estaba ({n} prendas)", flush=True)
        return n

    parcial = final.with_suffix(".part")
    url = URL.format(lote=lote, cuerpo=cuerpo)
    t0, n = time.time(), 0
    with parcial.open("w", encoding="utf-8") as sal:
        with op.open(url, timeout=300) as flujo, \
                tarfile.open(fileobj=flujo, mode="r|gz") as tar:
            for m in tar:
                pid = prenda_de(m.name) if m.isfile() else None
                if not pid:
                    continue
                f = tar.extractfile(m)
                if f is None:
                    continue
                fila = {"prenda": pid, "lote": lote}
                try:
                    h = validar(json.loads(f.read()), LIM)
                except Exception as e:              # noqa: BLE001 - es un dato
                    fila["fallo"] = f"{type(e).__name__}: {e}"
                else:
                    r = resumen(h)
                    fila.update(valido=r["valido"], errores=r["errores"],
                                avisos=r["avisos"], por_codigo=r["por_codigo"])
                sal.write(json.dumps(fila, ensure_ascii=False) + "\n")
                n += 1
                if n % 500 == 0:
                    print(f"lote {lote:>2}: {n:5} prendas | {time.time()-t0:5.0f}s",
                          flush=True)
    # el rename solo ocurre si el flujo llego hasta el final: un lote a medias
    # se queda en .part y se vuelve a intentar entero
    parcial.replace(final)
    print(f"lote {lote:>2}: {n} prendas en {time.time()-t0:.0f}s", flush=True)
    return n


def resumir(destino):
    n = limpias = sin_duro = 0
    codigos, fallos = Counter(), 0
    for f in sorted(destino.glob("lote_*.jsonl")):
        for linea in f.open(encoding="utf-8"):
            d = json.loads(linea)
            if "fallo" in d:
                fallos += 1
                continue
            n += 1
            codigos.update(d["por_codigo"])
            limpias += d["valido"]
            sin_duro += not (DUROS & set(d["por_codigo"]))
    if not n:
        print("no hay nada medido todavia")
        return

    print(f"prendas medidas    {n:>8,}")
    print(f"fallos del validador {fallos:>6,}")
    print()
    print(f"{'filtro':<34} {'conserva':>10} {'%':>7}")
    print(f"{'sin ningun error':<34} {limpias:>10,} {100*limpias/n:>6.1f}%")
    print(f"{'sin defecto geometrico duro':<34} {sin_duro:>10,} {100*sin_duro/n:>6.1f}%")
    print(f"{'sin filtrar':<34} {n:>10,} {100.0:>6.1f}%")
    print("\ncodigos mas frecuentes")
    for k, v in codigos.most_common(12):
        print(f"  {k:<28} {v:>9,}")


def demo():
    """Comprobacion: el troceado de lotes y el nombre de prenda."""
    assert expandir("0-3,7") == [0, 1, 2, 3, 7]
    assert expandir("5") == [5]
    assert expandir("2-2, 4") == [2, 4]
    assert expandir("3-1") == []
    assert prenda_de("./default_body/rand_00YONAPXZE_specification.json") == "00YONAPXZE"
    assert prenda_de("rand_00YONAPXZE_design_params.yaml") is None
    assert prenda_de("carpeta/otra_cosa.json") is None
    print("demo ok")


def main(argv):
    if argv[0] == "--demo":
        return demo()
    destino = Path(argv[0])
    destino.mkdir(parents=True, exist_ok=True)
    if "--resumen" in argv:
        return resumir(destino)

    cuerpo = "default_body"
    if "--cuerpo" in argv:
        cuerpo = argv[argv.index("--cuerpo") + 1]
    lotes = expandir(argv[1]) if len(argv) > 1 and not argv[1].startswith("-") \
        else list(range(36))

    op, total, t0 = abridor(), 0, time.time()
    pendientes, ronda = list(lotes), 1
    while pendientes and ronda <= 5:
        if ronda > 1:
            print(f"\n--- ronda {ronda}: quedan {len(pendientes)} lotes ---", flush=True)
        fallidos = []
        for lote in pendientes:
            # Una caida de red deja sin medir todo lo que quede, asi que la
            # espera crece entre intentos y los lotes que fallen se reintentan
            # en otra ronda en vez de darse por perdidos.
            for espera in (5, 30, 120):
                try:
                    total += medir_lote(lote, cuerpo, destino, op)
                    break
                except (urllib.error.URLError, tarfile.TarError, OSError, EOFError) as e:
                    print(f"lote {lote:>2}: fallo ({type(e).__name__}: {e}); "
                          f"reintento en {espera}s", flush=True)
                    time.sleep(espera)
            else:
                fallidos.append(lote)
                print(f"lote {lote:>2}: se deja para la siguiente ronda", flush=True)
        if len(fallidos) == len(pendientes):
            print(f"\nninguno de los {len(fallidos)} lotes avanzo; se para aqui",
                  flush=True)
            break
        pendientes, ronda = fallidos, ronda + 1

    print(f"\n{total:,} prendas medidas en {(time.time()-t0)/60:.0f} min -> {destino}")
    if pendientes:
        print(f"quedan sin medir los lotes: {','.join(map(str, pendientes))}")


if __name__ == "__main__":
    main(sys.argv[1:])
