"""Figures of the README, in the palette and fonts of the slides (Surrealist's).

    uv run --with matplotlib --with networkx python docs/figures/figures.py

Every number comes from db/*.md or from the recorded demo (presentation/assets/video).
The charts shared with the slides are drawn by presentation/charts.py.
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "presentation"))

import charts  # noqa: E402  (sets fonts and colours)
from charts import MONO, c, clean, plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402
from style import BG, CARD, LILAC, LINE, MUTED, PINK, TEXT, VIOLET  # noqa: E402

charts.OUT = HERE


def box(ax, x, y, w, h, title, sub="", accent=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.12",
                                facecolor=c(VIOLET if accent else CARD),
                                edgecolor=c(VIOLET if accent else LINE), linewidth=1.4))
    ax.text(x + w / 2, y + h / 2 + (0.17 if sub else 0), title, ha="center", va="center",
            size=17, weight="bold", color=c(TEXT))
    if sub:
        ax.text(x + w / 2, y + h / 2 - 0.22, sub, ha="center", va="center", size=12,
                color=c(TEXT if accent else MUTED))


def arrow(ax, x1, y1, x2, y2, label="", dy=0.16):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=16,
                                 color=c(MUTED), linewidth=1.3))
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + dy, label, ha="center", va="bottom",
                size=11.5, family=MONO, color=c(MUTED))


def architecture():
    """The path of a request: app, balancer, stateless nodes, storage."""
    fig = plt.figure(figsize=(14, 5.2))
    ax = fig.add_axes([0, 0, 1, 1])
    clean(ax)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 5.2)
    box(ax, 0.2, 2.0, 2.4, 1.2, "Clients", "iPhone app, SDK, Surrealist")
    box(ax, 3.7, 2.0, 2.2, 1.2, "HAProxy :8100", "round robin, /status 1 s", accent=True)
    box(ax, 7.1, 3.2, 2.4, 1.1, "SurrealDB A", "stateless: rules, API")
    box(ax, 7.1, 0.9, 2.4, 1.1, "SurrealDB B", "stateless: rules, API")
    box(ax, 10.7, 3.6, 2.9, 0.9, "PD", "where each region lives")
    # three TiKV stores in one frame
    ax.add_patch(FancyBboxPatch((10.7, 0.5), 2.9, 2.6, boxstyle="round,pad=0,rounding_size=0.12",
                                facecolor=c(BG), edgecolor=c(LINE), linewidth=1.4))
    ax.text(12.15, 2.75, "TiKV x3", ha="center", va="center", size=17, weight="bold", color=c(TEXT))
    for i in range(3):
        ax.add_patch(FancyBboxPatch((10.95 + i * 0.85, 1.3), 0.7, 0.9,
                                    boxstyle="round,pad=0,rounding_size=0.08",
                                    facecolor=c(CARD), edgecolor=c(LINE), linewidth=1.2))
    ax.text(12.15, 0.85, "every region on all 3, Raft", ha="center", va="center", size=12.5,
            color=c(MUTED))
    arrow(ax, 2.6, 2.6, 3.7, 2.6, "HTTP, WS")
    arrow(ax, 5.9, 2.8, 7.1, 3.6)
    arrow(ax, 5.9, 2.4, 7.1, 1.6)
    arrow(ax, 9.5, 3.85, 10.7, 4.0)
    arrow(ax, 9.5, 3.5, 10.7, 2.4)
    arrow(ax, 9.5, 1.45, 10.7, 1.75)
    ax.text(0.3, 4.75, "One request: sign in with the customer's token, pay, written on 3 stores, HTTP 201",
            size=14, color=c(MUTED))
    return charts.save(fig, "architecture")


# Taken from the recorded demo (cluster segment, 2026-11-13): node that served each of
# the 40 writes, and which ones failed.
KILL_NODE = ["B", "A"] * 5 + ["B"] * 30           # node A killed around write 10
KILL_TIKV = [("B" if i % 2 == 0 else "A") for i in range(40)]
TIKV_ERRORS = set(range(12, 18))                   # writes 13 to 18, about 1.58 s each


def failover():
    """40 writes through HAProxy while a piece of the cluster dies."""
    fig = plt.figure(figsize=(14, 4.6))
    ax = fig.add_axes([0, 0, 1, 1])
    clean(ax)
    ax.set_xlim(-0.5, 46)
    ax.set_ylim(0, 4.6)
    rows = [(3.0, "SurrealDB node A killed", KILL_NODE, set(),
             "40 of 40 OK: HAProxy moves everything to B"),
            (1.0, "TiKV leader of 5/5 regions killed", KILL_TIKV, TIKV_ERRORS,
             "6 errors while Raft elects, then OK: 74 = 40 + 34 stored")]
    for y, title, nodes, errors, note in rows:
        ax.text(0, y + 0.85, title, size=16, weight="bold", color=c(TEXT))
        for i, n in enumerate(nodes):
            col = PINK if i in errors else (VIOLET if n == "B" else LILAC)
            ax.add_patch(FancyBboxPatch((i * 1.1, y), 0.92, 0.55,
                                        boxstyle="round,pad=0,rounding_size=0.08",
                                        facecolor=c(col), edgecolor="none"))
        ax.text(0, y - 0.38, note, size=13, family=MONO, color=c(MUTED))
    for x, label, col in [(30.5, "served by A", LILAC), (36.2, "by B", VIOLET), (40.0, "error", PINK)]:
        ax.add_patch(FancyBboxPatch((x, 4.12), 0.5, 0.3, boxstyle="round,pad=0,rounding_size=0.05",
                                    facecolor=c(col), edgecolor="none"))
        ax.text(x + 0.7, 4.27, label, size=12.5, va="center", color=c(MUTED))
    return charts.save(fig, "failover")


def all_figures():
    return {
        "architecture": architecture(),
        "failover": failover(),
        "ibm": charts.ibm(),
        "race": charts.race(),
        "redteam": charts.redteam(),
        "graph": charts.graph("graph", 7, 7),
    }


if __name__ == "__main__":
    for name, path in all_figures().items():
        print(name, path.relative_to(ROOT))
