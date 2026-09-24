"""Cuanto depende el resultado de cada umbral duro.

    python research/sensibilidad_umbrales.py data/garmentcodedata_0 docs/paper/figs

Barre la longitud minima de borde, el angulo minimo de esquina y la tolerancia
de costura, uno a la vez con los demas en su valor por defecto, y mide el % de
patrones afectados. Valida una sola vez con cada limite en el extremo del
barrido: los hallazgos salen para todo valor por debajo de ese extremo, y el
reconocimiento de pinzas no depende del umbral de angulo, asi que cualquier
umbral intermedio se evalua sobre los valores medidos sin volver a validar.

Escribe `sensibilidad.pdf` y `sensibilidad.json` en el destino.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, "src")
sys.path.insert(0, "research")
from hilvan import DUROS, Limites, longitud, validar
from figuras_paper import AZUL, NARANJA, TINTA2, REJILLA  # paleta y estilo del paper
from numeros_paper import comprobar_supuesto

POR_DEFECTO = Limites()
EXTREMO = Limites(largo_min_borde=1.0, angulo_min_esquina=25.0, tol_costura=0.005)
BARRIDOS = {
    "largo": np.round(np.arange(0.1, 1.0001, 0.05), 3),
    "angulo": np.arange(5.0, 25.01, 1.0),
    "tol": np.round(np.arange(0.005, 0.1001, 0.0025), 4),
}


def medir(carpeta):
    filas = []
    vistos = set()
    for r in sorted(Path(carpeta).glob("*specification.json")):
        spec = json.loads(r.read_text(encoding="utf-8"))
        pat = spec.get("pattern", spec)
        hs = validar(spec, EXTREMO)
        vistos.update(h.codigo for h in hs if h.severidad == "error")
        filas.append({
            # la longitud exacta: `largo_cm` viene redondeado a 3 decimales y un
            # borde de 0,4996 cm quedaria en 0,5, fuera del umbral
            "borde": min((longitud(pat["panels"][h.panel], h.borde) for h in hs
                          if h.codigo == "borde_degenerado"), default=np.inf),
            "esquina": min((h.medido["angulo_grados"] for h in hs
                            if h.codigo == "esquina_aguda"), default=np.inf),
            "desajuste": max((h.medido["desajuste_rel"] for h in hs
                              if h.codigo == "desajuste_no_declarado"), default=0.0),
            # clases duras que no dependen de estos tres umbrales
            "otro_duro": any(h.codigo in DUROS - {"borde_degenerado", "esquina_aguda"}
                             for h in hs if h.severidad == "error"),
        })
    # "validado" en el barrido de tolerancia supone que solo hay duros y desajustes
    comprobar_supuesto(vistos)
    return filas


def curvas(filas):
    L, A = POR_DEFECTO.largo_min_borde, POR_DEFECTO.angulo_min_esquina
    pct = lambda cond: 100 * float(np.mean([cond(f) for f in filas]))
    duro = lambda f, l=L, a=A: f["otro_duro"] or f["borde"] < l or f["esquina"] < a
    return {
        "largo": {"clase": [pct(lambda f: f["borde"] < v) for v in BARRIDOS["largo"]],
                  "duro": [pct(lambda f: duro(f, l=v)) for v in BARRIDOS["largo"]]},
        "angulo": {"clase": [pct(lambda f: f["esquina"] < v) for v in BARRIDOS["angulo"]],
                   "duro": [pct(lambda f: duro(f, a=v)) for v in BARRIDOS["angulo"]]},
        # el desajuste solo es error hasta el umbral de fruncido; por encima es aviso
        "tol": {"clase": [pct(lambda f: f["desajuste"] > v) for v in BARRIDOS["tol"]],
                "validado": [pct(lambda f: not duro(f) and not f["desajuste"] > v)
                             for v in BARRIDOS["tol"]]},
    }


def figura(c, destino):
    paneles = [
        ("largo", "Min. edge length (cm)", POR_DEFECTO.largo_min_borde,
         ("Short edge", "Any hard defect"), ("clase", "duro"), 1),
        ("angulo", "Min. corner angle (°)", POR_DEFECTO.angulo_min_esquina,
         ("Sharp corner", "Any hard defect"), ("clase", "duro"), 1),
        ("tol", "Seam tolerance (%)", POR_DEFECTO.tol_costura * 100,
         ("Undeclared mismatch", "Fully validated"), ("clase", "validado"), 100),
    ]
    fig, ejes = plt.subplots(1, 3, figsize=(7.0, 2.5))
    for ax, (clave, xlabel, defecto, nombres, series, escala) in zip(ejes, paneles):
        x = BARRIDOS[clave] * escala
        ax.grid(axis="y", color=REJILLA, linewidth=0.5, zorder=0)
        ax.set_axisbelow(True)
        ax.axvline(defecto, color=TINTA2, linewidth=0.8, linestyle=":", zorder=1)
        ax.plot(x, c[clave][series[0]], color=AZUL, linewidth=2, zorder=3, label=nombres[0])
        ax.plot(x, c[clave][series[1]], color=NARANJA, linewidth=2, linestyle="--",
                zorder=3, label=nombres[1])
        ax.set_xlabel(xlabel)
        ax.set_ylim(0, 100)
        # fuera de los ejes: en el panel de tolerancia las curvas cruzan todo el alto
        ax.legend(frameon=False, loc="lower left", bbox_to_anchor=(0.0, 1.0),
                  handlelength=1.8, borderaxespad=0.2)
    ejes[0].set_ylabel("Patterns (%)")
    fig.tight_layout(pad=0.3, w_pad=1.2)
    fig.savefig(destino / "sensibilidad.pdf")
    plt.close(fig)


if __name__ == "__main__":
    destino = Path(sys.argv[2])
    filas = medir(sys.argv[1])
    c = curvas(filas)
    # en el valor por defecto tiene que reproducir la tabla del paper
    i = list(BARRIDOS["largo"]).index(0.5)
    print(f"por defecto: borde {c['largo']['clase'][i]:.2f}%  "
          f"duro {c['largo']['duro'][i]:.2f}%  (esperado 14.52% y 20.43%)")
    figura(c, destino)
    (destino / "sensibilidad.json").write_text(json.dumps(
        {k: {"x": BARRIDOS[k].tolist(), **v} for k, v in c.items()}, indent=1),
        encoding="utf-8")
