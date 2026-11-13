"""Gráficos y capturas de terminal, en PNG, con la paleta de las diapositivas.

Cada cifra sale de db/*.md (lista en presentation/README.md). Las capturas de
terminal son salidas reales guardadas en assets/term/*.txt.
"""
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from style import BG, CARD, LINE, LILAC, MUTED, PINK, TEXT, VIOLET

HERE = Path(__file__).parent
OUT = HERE / "assets" / "gen"
FONTS = Path.home() / "Library" / "Fonts"
for f in ["Geist-Regular.otf", "Geist-SemiBold.otf", "Geist-Bold.otf",
          "JetBrainsMono-Regular.ttf", "JetBrainsMono-Bold.ttf"]:
    if (FONTS / f).exists():
        font_manager.fontManager.addfont(str(FONTS / f))
SANS, MONO = "Geist", "JetBrains Mono"
plt.rcParams.update({"font.family": SANS, "text.color": "#" + TEXT,
                     "axes.edgecolor": "#" + BG, "figure.facecolor": "#" + BG,
                     "axes.facecolor": "#" + BG, "svg.fonttype": "none"})


def c(hex_):
    return "#" + hex_


def clean(ax):
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.png"
    fig.savefig(path, dpi=200, facecolor=c(BG))
    plt.close(fig)
    return path


def race():
    """Diapositiva 7: 10 transferencias simultáneas del saldo entero, 20 rondas."""
    fig, ax = plt.subplots(figsize=(12, 4.6))
    clean(ax)
    rows = [("fn::transfer", 0, 0, VIOLET, "0 of 20"),
            ("fn::transfer_unsafe", 11, 16, PINK, "11 to 16 of 20")]
    for i, (name, lo, hi, col, label) in enumerate(rows):
        y = 1 - i
        ax.barh(y, 20, height=0.42, color=c(CARD), edgecolor=c(LINE), linewidth=1)
        if hi:
            ax.barh(y, lo, height=0.42, color=c(col))
            ax.barh(y, hi - lo, left=lo, height=0.42, color=c(col), alpha=0.45)
        ax.text(-0.4, y + 0.3, name, family=MONO, size=19, color=c(TEXT), va="bottom")
        ax.text(20.4, y, label, family=MONO, size=24, color=c(col if hi else TEXT),
                va="center", weight="bold")
    ax.set_xlim(-0.5, 27)
    ax.set_ylim(-0.6, 1.9)
    ax.text(-0.4, -0.55, "rounds that ended in an overdraft (6 runs on 2026-11-13: 16, 12, 11, 15, 12, 12)",
            size=15, color=c(MUTED))
    return save(fig, "race")


def ibm():
    """Diapositiva 12: ciclos de IBM detectados y precisión; el filtro previo."""
    fig = plt.figure(figsize=(12, 5.0))
    ax = fig.add_axes([0.0, 0.08, 0.56, 0.86])
    clean(ax)
    data = [("HI-Small, calibration", 4.6, [("strict", 6, 54, "100 %", VIOLET), ("wide", 33, 54, "98.6 %", LILAC)]),
            ("LI-Small, held out", 2.3, [("strict", 1, 12, "100 %", VIOLET), ("wide", 8, 12, "86.9 %", LILAC)])]
    for title, top, bars in data:
        ax.text(0, top, title, size=17, color=c(TEXT), weight="bold", va="center")
        for j, (name, found, total, prec, col) in enumerate(bars):
            y = top - 0.75 - j * 0.8
            ax.barh(y, 1, height=0.5, color=c(CARD), edgecolor=c(LINE), linewidth=1)
            ax.barh(y, found / total, height=0.5, color=c(col))
            ax.text(1.03, y + 0.08, f"{found}/{total}", family=MONO, size=19, color=c(TEXT), va="center", weight="bold")
            ax.text(1.03, y - 0.27, f"precision {prec}", family=MONO, size=15, color=c(MUTED), va="center")
            ax.text(0.015, y, name, size=16, color=c(BG if col == LILAC else TEXT), va="center")
    ax.set_xlim(0, 1.45)
    ax.set_ylim(-0.3, 5.0)
    ax.text(0, -0.1, "laundering cycles found", size=16, color=c(MUTED))

    ax2 = fig.add_axes([0.62, 0.08, 0.38, 0.86])
    clean(ax2)
    steps = [("4,487,133", "transfers in HI-Small", 1.0, CARD),
             ("381", "after a lossless prefilter", 0.62, CARD),
             ("20 + 191", "accounts: freeze + review", 0.5, VIOLET)]
    for i, (num, label, width, col) in enumerate(steps):
        yy = 2 - i
        ax2.barh(yy, width, left=(1 - width) / 2, height=0.62, color=c(col),
                 edgecolor=c(VIOLET if col == VIOLET else LINE), linewidth=1)
        ax2.text(0.5, yy + 0.07, num, family=MONO, size=21, weight="bold", ha="center", va="center", color=c(TEXT))
        ax2.text(0.5, yy - 0.47, label, size=16, ha="center", va="center", color=c(MUTED))
    ax2.set_xlim(0, 1)
    ax2.set_ylim(-0.7, 2.5)
    return save(fig, "ibm")


def redteam():
    """Diapositiva 15: roturas a propósito, cazadas por su prueba (74/74)."""
    suites = [("access", 9), ("payments", 11), ("cards", 12), ("detect", 9),
              ("time travel", 10), ("controls", 23)]
    fig, ax = plt.subplots(figsize=(12, 4.8))
    clean(ax)
    for i, (name, n) in enumerate(suites):
        y = len(suites) - i
        ax.barh(y, n, height=0.55, color=c(VIOLET))
        ax.text(-0.4, y, name, size=18, ha="right", va="center", color=c(TEXT))
        ax.text(n + 0.4, y, f"{n}/{n}", family=MONO, size=18, va="center", color=c(TEXT))
    ax.set_xlim(-6, 28)
    ax.set_ylim(0.3, len(suites) + 0.6)
    return save(fig, "redteam")


def terminal(name, highlights=(), width=11.0, size=22):
    """Salida real de terminal a PNG. `highlights`: (regex, color)."""
    lines = (HERE / "assets" / "term" / f"{name}.txt").read_text().rstrip("\n").split("\n")
    line_h = size / 72 * 1.55
    fig = plt.figure(figsize=(width, line_h * len(lines) + 0.6))
    ax = fig.add_axes([0, 0, 1, 1])
    clean(ax)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.patch.set_facecolor(c(CARD))
    step = (1 - 0.3 / fig.get_figheight() * 2) / len(lines)
    y = 1 - 0.3 / fig.get_figheight()
    for line in lines:
        col = MUTED if line.startswith("$") else TEXT
        for pattern, hcol in highlights:
            if re.search(pattern, line):
                col = hcol
        ax.text(0.025, y - step / 2, line, family=MONO, size=size, color=c(col), va="center")
        y -= step
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"term-{name}.png"
    fig.savefig(path, dpi=200, facecolor=c(CARD))
    plt.close(fig)
    return path


def graph(name, w, h, dim=1.0):
    """Grafo real de transferencias de la base `volume`; anillos en violeta.

    Datos: assets/data/volume-graph.json (exportado de la base). Disposición
    por fuerzas con semilla fija: sale igual en cada regeneración.
    """
    import json
    import networkx as nx
    d = json.loads((HERE / "assets" / "data" / "volume-graph.json").read_text())
    ring = set(d["ring"])
    G = nx.Graph()
    for a, b, n in d["edges"]:
        G.add_edge(a, b, n=n)
    pos = nx.spring_layout(G, seed=7, k=0.9 / len(G) ** 0.5, iterations=200)
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1])
    clean(ax)
    for a, b in G.edges:
        hot = a in ring and b in ring
        (x1, y1), (x2, y2) = pos[a], pos[b]
        ax.plot([x1, x2], [y1, y2], color=c(VIOLET if hot else LINE),
                lw=2.2 if hot else 0.6, alpha=(1.0 if hot else 0.9) * dim,
                zorder=3 if hot else 1, solid_capstyle="round")
    xs = [pos[n][0] for n in G if n not in ring]
    ys = [pos[n][1] for n in G if n not in ring]
    ax.scatter(xs, ys, s=10, color=c(MUTED), alpha=0.75 * dim, zorder=2, linewidths=0)
    ax.scatter([pos[n][0] for n in ring], [pos[n][1] for n in ring], s=46,
               color=c(VIOLET), alpha=dim, zorder=4, linewidths=0)
    xs_all = [p[0] for p in pos.values()]
    ys_all = [p[1] for p in pos.values()]
    mx, my = (max(xs_all) - min(xs_all)) * 0.04, (max(ys_all) - min(ys_all)) * 0.04
    ax.set_xlim(min(xs_all) - mx, max(xs_all) + mx)
    ax.set_ylim(min(ys_all) - my, max(ys_all) + my)
    return save(fig, name)


def all_charts():
    return {
        "race": race(),
        "ibm": ibm(),
        "redteam": redteam(),
        "install": terminal("install", [(r"ALL PASSED", LILAC)]),
    }


if __name__ == "__main__":
    for k, v in all_charts().items():
        print(k, v)
