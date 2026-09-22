"""Arma el JSON de inferencia de ChatGarment para las mismas 100 prendas.

ChatGarment no lee prosa. Su pipeline manda el texto a GPT-4o, que lo convierte
en un dict de vocabulario controlado, y *eso* es lo que ve el modelo. Aqui ese
dict se construye desde los design_params de la prenda con el mismo vocabulario
del prompt de los autores (docs/prompts/detailed_textbased_description.txt),
que quita de en medio una llamada de pago y no determinista.

La sustitucion es generosa con el modelo, no tacana: las etiquetas salen de los
parametros reales en vez de la lectura que GPT-4o haria de una frase. Si aun con
la entrada limpia el patron no se puede coser, el fallo no es de la entrada.

Cada prenda lleva ademas la misma frase que recibio AIpparel, que no se usa para
generar pero queda escrita en el output.txt de cada salida para poder rastrear
el par.
"""
import json, sys, yaml
from pathlib import Path

from aipparel_entradas import palabras, describir

# Donde vive cada prenda de abajo dentro de los design_params. Igual que el
# skirt_configs de llava/garmentcodeRC_utils.py, que es quien lo decide al
# reconstruir el patron.
SECCION_ABAJO = {
    "SkirtCircle": "flare-skirt", "AsymmSkirtCircle": "flare-skirt",
    "SkirtManyPanels": "flare-skirt", "GodetSkirt": "godet-skirt",
    "Pants": "pants", "Skirt2": "skirt", "PencilSkirt": "pencil-skirt",
    "SkirtLevels": "levels-skirt",
}


def valor(d, *ruta):
    """Baja por la ruta y devuelve el nodo, o None si falta algun tramo."""
    for k in ruta:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def tramo(nodo, etiquetas):
    """Normaliza el parametro dentro de su rango declarado y lo parte en tramos.

    El rango viene en el propio fichero, asi que no hay umbrales inventados
    aqui: 'largo' significa el tercio alto de lo que GarmentCode admite.
    """
    if not isinstance(nodo, dict) or "v" not in nodo or "range" not in nodo:
        return None
    lo, hi = float(nodo["range"][0]), float(nodo["range"][1])
    x = 0.5 if hi <= lo else (float(nodo["v"]) - lo) / (hi - lo)
    return etiquetas[min(int(x * len(etiquetas)), len(etiquetas) - 1)]


def arriba(d):
    g = {}
    ancho = tramo(valor(d, "shirt", "width"), ["narrow", "normal", "wide"])
    largo = tramo(valor(d, "shirt", "length"), ["short", "normal", "long"])
    if ancho:
        g["width"] = [ancho]
    if largo:
        g["length"] = [largo]

    if valor(d, "sleeve", "sleeveless", "v"):
        g["sleeves"] = ["sleeveless"]
    else:
        sl = [tramo(valor(d, "sleeve", "length"),
                    ["short sleeves", "elbow-length sleeves", "long sleeves"]),
              tramo(valor(d, "sleeve", "end_width"),
                    ["tight sleeves", "normal sleeves", "loose sleeves"])]
        g["sleeves"] = [s for s in sl if s] or ["normal sleeves"]

    cuello = valor(d, "collar", "f_collar", "v")
    if cuello:
        g["collar"] = [palabras(cuello).replace(" half", "")]

    estilo = str(valor(d, "collar", "component", "style", "v") or "")
    g["hood"] = ["normal hood"] if "Hood" in estilo else ["no hood"]
    return g


def seccion_abajo(d, tipo, campo):
    """Busca el campo en la seccion del tipo, siguiendo 'base' si hace falta.

    GodetSkirt y SkirtLevels se definen encima de otra falda y no repiten sus
    parametros: el largo de una falda de godets vive en la falda que la sostiene.
    """
    visto = set()
    while tipo and tipo not in visto:
        visto.add(tipo)
        s = d.get(SECCION_ABAJO.get(tipo, ""), {})
        if campo in s:
            return s[campo]
        tipo = valor(s, "base", "v")
    return None


def abajo(d, tipo):
    g = {}
    largo = tramo(seccion_abajo(d, tipo, "length"), ["short", "knee-length", "long"])
    if largo:
        g["length"] = [largo]

    # Cada familia mide el vuelo con su propio parametro: las circulares por
    # numero de soles, las de niveles por el fruncido de cada nivel.
    for campo in ("flare", "width", "suns", "level_ruffle"):
        ancho = tramo(seccion_abajo(d, tipo, campo), ["narrow", "normal", "wide"])
        if ancho:
            g["width"] = [ancho]
            break

    cintura = tramo(seccion_abajo(d, tipo, "rise"), ["low waist", "mid-rise waist", "high waist"])
    wb = valor(d, "meta", "wb", "v")
    g["waist"] = [c for c in (cintura, f"{palabras(wb).replace(' w b', '')} waistband"
                              if wb else "no waistband") if c]

    forma = palabras(tipo)
    g["pant legs" if tipo == "Pants" else "skirt hems"] = [f"{forma} shape"]
    return g


def etiquetas(d):
    """El outfit_dict que el modelo recibe, en el sitio donde iria el de GPT-4o."""
    salida = {}
    if valor(d, "meta", "upper", "v"):
        salida["upperbody garment"] = {
            "garment_name": palabras(valor(d, "meta", "upper", "v")),
            "geometry_styles": dict(arriba(d), extra=[]),
        }
    tipo = valor(d, "meta", "bottom", "v")
    if tipo:
        salida["lowerbody garment"] = {
            "garment_name": palabras(tipo),
            "geometry_styles": dict(abajo(d, tipo), extra=[]),
        }
    return salida


def demo():
    """Comprobacion: los tramos salen del rango declarado, no de un umbral fijo."""
    assert tramo({"v": 0.2, "range": [0.2, 0.95]}, ["a", "b", "c"]) == "a"
    assert tramo({"v": 0.95, "range": [0.2, 0.95]}, ["a", "b", "c"]) == "c"
    assert tramo({"v": 0.575, "range": [0.2, 0.95]}, ["a", "b", "c"]) == "b"
    assert tramo(None, ["a"]) is None

    d = {"meta": {"upper": {"v": "Shirt"}, "wb": {"v": None},
                  "bottom": {"v": "PencilSkirt"}},
         "shirt": {"width": {"v": 1.0, "range": [0.9, 1.4], "type": "float"},
                   "length": {"v": 1.5, "range": [0.8, 1.6], "type": "float"}},
         "sleeve": {"sleeveless": {"v": True}},
         "collar": {"f_collar": {"v": "VNeckHalf"}},
         "pencil-skirt": {"length": {"v": 0.9, "range": [0.2, 0.95], "type": "float"}}}
    e = etiquetas(d)
    assert set(e) == {"upperbody garment", "lowerbody garment"}, e
    arr = e["upperbody garment"]["geometry_styles"]
    assert arr["sleeves"] == ["sleeveless"] and arr["collar"] == ["v neck"], arr
    assert arr["length"] == ["long"] and arr["hood"] == ["no hood"], arr
    abj = e["lowerbody garment"]["geometry_styles"]
    assert abj["waist"] == ["no waistband"], abj
    assert abj["skirt hems"] == ["pencil skirt shape"], abj

    # una falda de godets hereda el largo de la falda que la sostiene
    godet = {"meta": {"upper": {"v": None}, "wb": {"v": None},
                      "bottom": {"v": "GodetSkirt"}},
             "godet-skirt": {"base": {"v": "PencilSkirt"}},
             "pencil-skirt": {"length": {"v": 0.2, "range": [0.2, 0.95], "type": "float"},
                              "rise": {"v": 1.0, "range": [0.5, 1.0], "type": "float"}}}
    gg = etiquetas(godet)["lowerbody garment"]["geometry_styles"]
    assert gg["length"] == ["short"], gg
    assert gg["waist"] == ["high waist", "no waistband"], gg
    # tal cual lo recibe el modelo: json con comillas simples
    texto = json.dumps(e).replace('"', "'")
    assert "'garment_name': 'shirt'" in texto, texto
    print("demo ok")


def main(lote):
    prendas = sorted(p.name.split("_")[1] for p in lote.glob("*_render_front.png"))
    entradas = []
    for pid in prendas:
        d = yaml.safe_load((lote / f"rand_{pid}_design_params.yaml").read_text())["design"]
        e = etiquetas(d)
        frase = describir(d)
        item = {"id": pid, "etiquetas": e}
        for tipo, bloque in e.items():
            item[tipo] = {"name": bloque["garment_name"], "text": frase}
        entradas.append(item)

    destino = lote / "chatgarment_texto.json"
    destino.write_text(json.dumps(entradas, indent=2))
    print(f"{len(entradas)} prendas -> {destino}")
    print("ejemplo:", json.dumps(entradas[0]["etiquetas"])[:200])


if __name__ == "__main__":
    if sys.argv[1] == "--demo":
        demo()
    else:
        main(Path(sys.argv[1]))
