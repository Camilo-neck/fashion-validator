"""Arma el JSON de inferencia: cada prenda dos veces, como imagen y como texto.

La descripcion sale de los design_params de la misma prenda, asi que el par
imagen/texto describe la misma prenda y la comparacion aisla el modo de entrada.
El indice deja escrito que muestra corresponde a que prenda, porque inference.py
numera las salidas por posicion en la lista.
"""
import json, re, sys, yaml
from pathlib import Path


def palabras(x):
    t = re.sub(r"(?<!^)(?=[A-Z])", " ", str(x)).lower()
    # GarmentCode nombra las faldas al reves de como se dicen: SkirtCircle es
    # una falda circular, no una circular falda.
    return re.sub(r"^skirt (.+)$", r"\1 skirt", t)


def describir(d):
    meta = {k: v.get("v") for k, v in d["meta"].items()}
    partes = []
    if meta.get("upper"):
        prenda = palabras(meta["upper"])
        cuello = d.get("collar", {}).get("f_collar", {}).get("v")
        if cuello:
            prenda += f" with a {palabras(cuello).replace(' half', '')} neckline"
        sl = d.get("sleeve", {})
        if sl.get("sleeveless", {}).get("v"):
            prenda += " and no sleeves"
        else:
            largo = sl.get("length", {}).get("v", 0.5)
            prenda += " and " + ("short" if largo < 0.35 else
                                 "elbow-length" if largo < 0.7 else "long") + " sleeves"
        partes.append(prenda)
    if meta.get("wb"):
        partes.append(f"a {palabras(meta['wb']).replace(' w b', ' waistband')}")
    if meta.get("bottom"):
        partes.append(f"a {palabras(meta['bottom'])}")
    if not partes:
        return "A simple garment."
    partes[0] = re.sub(r"^a ", "", partes[0])   # el articulo va delante de la frase
    cuerpo = partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " and " + partes[-1]
    return "A " + cuerpo + "."


def demo():
    """Comprobacion: las tres formas que cambian la frase."""
    assert palabras("SkirtCircle") == "circle skirt"
    assert palabras("FittedShirt") == "fitted shirt"
    solo_abajo = {"meta": {"upper": {"v": None}, "wb": {"v": None},
                           "bottom": {"v": "Pants"}}}
    assert describir(solo_abajo) == "A pants.", describir(solo_abajo)
    completo = {"meta": {"upper": {"v": "Shirt"}, "wb": {"v": "StraightWB"},
                         "bottom": {"v": "SkirtCircle"}},
                "collar": {"f_collar": {"v": "VNeckHalf"}},
                "sleeve": {"sleeveless": {"v": True}}}
    assert describir(completo) == ("A shirt with a v neck neckline and no sleeves, "
                                   "a straight waistband and a circle skirt."), describir(completo)
    print("demo ok")


def main(lote):
    prendas = sorted(p.name.split("_")[1] for p in lote.glob("*_render_front.png"))
    entradas, indice = [], []
    for modo in ("image", "description"):
        for pid in prendas:
            if modo == "image":
                entradas.append({"type": "image",
                                 "inputs": {"image_path": str(lote / f"rand_{pid}_render_front.png")}})
            else:
                d = yaml.safe_load((lote / f"rand_{pid}_design_params.yaml").read_text())["design"]
                entradas.append({"type": "description", "inputs": {"description": describir(d)}})
            indice.append({"sample": len(indice), "prenda": pid, "modo": modo})

    (lote / "inference_200.json").write_text(json.dumps(entradas, indent=2))
    (lote / "indice.json").write_text(json.dumps(indice, indent=2))
    print(f"{len(entradas)} entradas ({len(prendas)} prendas x 2 modos)")
    print("ejemplo de descripcion:", entradas[len(prendas)]["inputs"]["description"])


if __name__ == "__main__":
    if sys.argv[1] == "--demo":
        demo()
    else:
        main(Path(sys.argv[1]))
