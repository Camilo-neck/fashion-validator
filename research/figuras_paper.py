"""Genera las figuras del paper a partir del corpus, no de numeros copiados.

    python research/figuras_paper.py data/garmentcodedata_0 docs/paper/figs

Escribe los PDF de las figuras y un JSON con los numeros que las sostienen, para
que la cifra del texto y la del grafico no puedan separarse.
"""
import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, "src")
from fashion_validator import validar

# paleta categorica validada con el validador de dataviz (modo claro)
AZUL, NARANJA, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
TINTA, TINTA2, REJILLA = "#0b0b0b", "#52514e", "#d8d7d2"

GEO = {"borde_degenerado", "curvatura_excesiva", "esquina_aguda",
       "auto_interseccion", "excede_ancho_rollo", "contorno_abierto",
       "vertice_inexistente", "costura_nula", "borde_multicosido",
       "panel_suelto", "costura_no_binaria"}

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Latin Modern Roman", "DejaVu Serif"],
    "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8.5,
    "legend.fontsize": 7.5, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": TINTA2, "axes.linewidth": 0.6,
    "xtick.color": TINTA2, "ytick.color": TINTA2,
    "text.color": TINTA, "axes.labelcolor": TINTA,
    "figure.facecolor": "white", "axes.facecolor": "white",
})


def _guardar(fig, destino, nombre):
    """PDF para el paper; PNG solo para mirarla, con FIG_PNG=1."""
    fig.savefig(destino / f"{nombre}.pdf")
    if os.environ.get("FIG_PNG"):
        fig.savefig(pathlib_png := os.path.join(os.environ["FIG_PNG"], f"{nombre}.png"),
                    dpi=200)


def tipo(pat):
    et = {p.get("label") for p in pat["panels"].values()} - {None}
    arriba, abajo = bool(et & {"body", "torso"}), bool(et & {"leg", "pant", "skirt"})
    return "Full-body" if arriba and abajo else ("Torso" if arriba else
                                                 ("Lower-body" if abajo else "Other"))


def medir(carpeta):
    filas = []
    for r in sorted(Path(carpeta).glob("*specification.json")):
        spec = json.load(open(r, encoding="utf-8"))
        pat = spec.get("pattern", spec)
        errs = [h for h in validar(spec) if h.severidad == "error"]
        filas.append({"tipo": tipo(pat),
                      "costuras": max(len(pat.get("stitches", [])), 1),
                      "errores": len(errs),
                      "geo": sum(1 for h in errs if h.codigo in GEO)})
    return filas


def figura_acumulacion(filas, destino):
    """Por que un filtro binario castiga el tamano y no la calidad."""
    cortes = [(0, 10), (10, 20), (20, 30), (30, 40), (40, 55), (55, 10**6)]
    x, obs, pred, etiquetas = [], [], [], []
    for i, (lo, hi) in enumerate(cortes):
        g = [f for f in filas if lo <= f["costuras"] < hi]
        if len(g) < 20:
            continue
        por_costura = sum(f["errores"] for f in g) / sum(f["costuras"] for f in g)
        mediana = np.median([f["costuras"] for f in g])
        x.append(i)
        obs.append(100 * np.mean([f["errores"] == 0 for f in g]))
        pred.append(100 * (1 - por_costura) ** mediana)
        etiquetas.append(f"{lo}–{hi}" if hi < 10**6 else f"{lo}+")

    fig, ax = plt.subplots(figsize=(3.35, 2.45))
    ax.grid(axis="y", color=REJILLA, linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    ax.plot(x, obs, color=AZUL, linewidth=2, marker="o", markersize=5,
            markeredgecolor="white", markeredgewidth=0.8, zorder=3,
            label="Observed")
    ax.plot(x, pred, color=NARANJA, linewidth=2, linestyle="--", marker="s",
            markersize=4.5, markeredgecolor="white", markeredgewidth=0.8,
            zorder=3, label="If defects were independent")
    ax.set_yscale("log")
    ax.set_xticks(x, etiquetas)
    ax.set_xlabel("Seams per pattern")
    ax.set_ylabel("Defect-free patterns (%)")
    # abajo a la izquierda: la unica zona que ninguna de las dos series ocupa
    ax.legend(frameon=False, loc="lower left")
    # etiqueta directa solo en los extremos, no en cada punto
    for i, dx, ha in ((0, 7, "left"), (len(x) - 1, -7, "right")):
        ax.annotate(f"{obs[i]:.1f}%", (x[i], obs[i]), textcoords="offset points",
                    xytext=(dx, 3), ha=ha, fontsize=7.5, color=TINTA)
    fig.tight_layout(pad=0.3)
    _guardar(fig, destino, "acumulacion")
    plt.close(fig)
    return {"cortes": etiquetas, "observado": obs, "independiente": pred}


def figura_filtros(filas, destino):
    """Que le hace cada criterio de filtrado a la composicion del corpus."""
    criterios = [
        ("Unfiltered", lambda f: True),
        ("No hard defect", lambda f: f["geo"] == 0),
        ("Rate $\\leq$ 0.10/seam", lambda f: f["errores"] / f["costuras"] <= 0.10),
        ("Zero errors", lambda f: f["errores"] == 0),
    ]
    clases = ["Full-body", "Torso", "Lower-body"]
    colores = {"Full-body": AZUL, "Torso": NARANJA, "Lower-body": AQUA}

    fig, ax = plt.subplots(figsize=(3.35, 2.0))
    datos = {}
    for fila, (nombre, cond) in enumerate(criterios):
        sel = [f for f in filas if cond(f)]
        izq = 0.0
        datos[nombre] = {"n": len(sel)}
        for c in clases:
            pct = 100 * sum(1 for f in sel if f["tipo"] == c) / max(len(sel), 1)
            datos[nombre][c] = pct
            ax.barh(fila, pct, left=izq, height=0.62, color=colores[c],
                    edgecolor="white", linewidth=1.2, zorder=3)
            if pct >= 9:
                ax.text(izq + pct / 2, fila, f"{pct:.0f}", ha="center",
                        va="center", fontsize=7.5, color="white")
            izq += pct
        ax.text(101.5, fila, f"n={len(sel)}", va="center", fontsize=7,
                color=TINTA2)

    ax.set_yticks(range(len(criterios)), [c[0] for c in criterios])
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of retained corpus (%)")
    ax.invert_yaxis()
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    manijas = [plt.Rectangle((0, 0), 1, 1, color=colores[c]) for c in clases]
    ax.legend(manijas, clases, frameon=False, ncol=3, loc="lower center",
              bbox_to_anchor=(0.5, 1.0), handlelength=1.0, columnspacing=1.2)
    fig.tight_layout(pad=0.3)
    _guardar(fig, destino, "filtros")
    plt.close(fig)
    return datos


if __name__ == "__main__":
    origen, destino = Path(sys.argv[1]), Path(sys.argv[2])
    destino.mkdir(parents=True, exist_ok=True)
    filas = medir(origen)
    numeros = {"patrones": len(filas),
               "acumulacion": figura_acumulacion(filas, destino),
               "filtros": figura_filtros(filas, destino)}
    (destino / "numeros.json").write_text(
        json.dumps(numeros, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(numeros, indent=1, ensure_ascii=False))
