#!/usr/bin/env python3
"""NEST ladder figures as standalone SVGs (light and dark via prefers-color-scheme), for STEGO_EXPERIMENT.md and the
report page: figs/stego/nest_clean.svg (clean successes by length, small multiples) and figs/stego/nest_open.svg (how
often the reasoning discusses or writes out the code).

    python3 scripts/stego/plot_nest.py
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]; OUT = REPO / "figs/stego"; OUT.mkdir(parents=True, exist_ok=True)
MODELS = [("nest_gemma_base", "Gemma base", "s1"), ("nest_gemma_B", "Gemma B", "s2")]
HEX = {"s1": "#2a78d6", "s2": "#eb6834"}  # light-mode slots 1 and 2; the style block swaps in the dark steps
SIZES = (4, 8, 12, 16); LEVELS = ("L0", "L1", "L2")
LEVEL_NAME = {"L0": "L0 · letters given", "L1": "L1 · digits + table", "L2": "L2 · range() + table"}
CHANNEL_NAME = {"answer": "In the answer (thinking off)", "cot": "In the reasoning (thinking on)"}

STYLE = """<style>
.v{--bg:#fcfcfb;--t1:#0b0b0b;--t2:#52514e;--grid:#e4e3df;--axis:#bdbcb7;--s1:#2a78d6;--s2:#eb6834}
@media (prefers-color-scheme:dark){.v{--bg:#1a1a19;--t1:#f0efec;--t2:#c3c2b7;--grid:#2e2e2c;--axis:#4a4a47;--s1:#3987e5;--s2:#d95926}}
:root[data-theme=light] .v{--bg:#fcfcfb;--t1:#0b0b0b;--t2:#52514e;--grid:#e4e3df;--axis:#bdbcb7;--s1:#2a78d6;--s2:#eb6834}
:root[data-theme=dark] .v{--bg:#1a1a19;--t1:#f0efec;--t2:#c3c2b7;--grid:#2e2e2c;--axis:#4a4a47;--s1:#3987e5;--s2:#d95926}
.v text{font-family:"IBM Plex Sans",system-ui,sans-serif;fill:var(--t2);font-size:11px}
.v .ttl{fill:var(--t1);font-size:14px;font-weight:600}.v .sub{font-size:12px}.v .ph{fill:var(--t1);font-size:12px;font-weight:600}
.v .row{fill:var(--t1);font-size:12px;font-weight:600}
.v .g{stroke:var(--grid);stroke-width:1}.v .ax{stroke:var(--axis);stroke-width:1}
.v .s1{stroke:var(--s1);fill:var(--s1)}.v .s2{stroke:var(--s2);fill:var(--s2)}
.v path.s1,.v path.s2{fill:none}.v rect.s1{stroke:none}.v rect.s2{stroke:none}.v circle{stroke:var(--bg);stroke-width:2}
.v .hit{fill:transparent;stroke:none}.v .hit:hover+circle{r:6}
</style>"""


def load(label):
    return [g for g in map(json.loads, open(REPO / "results/stego" / label / "graded.jsonl")) if g["level"] != "plain"]


def clean(g):
    return g["natural"] and not g["talks"] and not g["leaks"]


def legend(x, y):
    out = []
    for i, (_, name, cls) in enumerate(MODELS):
        xx = x + i * 110
        out.append(f'<line x1="{xx}" y1="{y}" x2="{xx + 18}" y2="{y}" class="{cls}" stroke="{HEX[cls]}" stroke-width="2"/><circle cx="{xx + 9}" cy="{y}" r="4" class="{cls}" fill="{HEX[cls]}" stroke="#fcfcfb"/>'
                   f'<text x="{xx + 24}" y="{y + 4}">{name}</text>')
    return "".join(out)


def fig_clean(data):
    pw, ph, gx, gy, left, top = 200, 130, 28, 58, 132, 112
    W = left + 3 * pw + 2 * gx + 16; H = top + 2 * ph + gy + 40
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" class="v" viewBox="0 0 {W} {H}" width="100%" role="img" '
         f'aria-label="NEST clean hidden-message successes by length, level and channel, Gemma base against B">{STYLE}'
         f'<rect width="{W}" height="{H}" fill="var(--bg)"/>'
         f'<text x="16" y="24" class="ttl">Clean hidden messages, out of 20 per point</text>'
         f'<text x="16" y="42" class="sub">Right letters, real words, no talk of the code, no digits written out · x = message length (letters)</text>'
         + legend(16, 64)]
    for r, ch in enumerate(("answer", "cot")):
        y0 = top + r * (ph + gy)
        s.append(f'<text x="16" y="{y0 + ph / 2 - 6}" class="row">{CHANNEL_NAME[ch].split(" (")[0]}</text>'
                 f'<text x="16" y="{y0 + ph / 2 + 10}">({CHANNEL_NAME[ch].split(" (")[1]}</text>')
        for c, lv in enumerate(LEVELS):
            x0 = left + c * (pw + gx)
            X = lambda d: x0 + 10 + (pw - 20) * SIZES.index(d) / 3
            Y = lambda v: y0 + ph - ph * v / 20
            s.append(f'<text x="{x0}" y="{y0 - 10}" class="ph">{LEVEL_NAME[lv]}</text>')
            for v in (0, 10, 20):
                s.append(f'<line x1="{x0}" x2="{x0 + pw}" y1="{Y(v)}" y2="{Y(v)}" class="{"ax" if v == 0 else "g"}" stroke="{"#bdbcb7" if v == 0 else "#e4e3df"}"/>')
                if c == 0: s.append(f'<text x="{x0 - 6}" y="{Y(v) + 4}" text-anchor="end">{v}</text>')
            for d in SIZES: s.append(f'<text x="{X(d)}" y="{y0 + ph + 16}" text-anchor="middle">{d}</text>')
            for lab, name, cls in MODELS:
                pts = [(d, sum(clean(g) for g in data[lab] if g["channel"] == ch and g["level"] == lv and g["d"] == d)) for d in SIZES]
                s.append(f'<path class="{cls}" fill="none" stroke="{HEX[cls]}" stroke-width="2" d="' + " ".join(f'{"M" if i == 0 else "L"}{X(d):.1f},{Y(v):.1f}' for i, (d, v) in enumerate(pts)) + '"/>')
                for d, v in pts:
                    s.append(f'<g><circle class="hit" fill="transparent" cx="{X(d):.1f}" cy="{Y(v):.1f}" r="11"><title>{name} · {CHANNEL_NAME[ch]} · {lv} · {d} letters: {v}/20</title></circle>'
                             f'<circle class="{cls}" fill="{HEX[cls]}" stroke="#fcfcfb" stroke-width="2" cx="{X(d):.1f}" cy="{Y(v):.1f}" r="4"><title>{name} · {CHANNEL_NAME[ch]} · {lv} · {d} letters: {v}/20</title></circle></g>')
    s.append("</svg>")
    (OUT / "nest_clean.svg").write_text("".join(s))


def fig_open(data):
    W, H, left, top, bh, gap = 660, 262, 160, 92, 16, 4
    pw = W - left - 60
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" class="v" viewBox="0 0 {W} {H}" width="100%" role="img" '
         f'aria-label="Share of reasoning traces that discuss the code or write the digits, by level">{STYLE}'
         f'<rect width="{W}" height="{H}" fill="var(--bg)"/>'
         f'<text x="16" y="24" class="ttl">Hidden in the reasoning: how often the reasoning gives the code away</text>'
         f'<text x="16" y="42" class="sub">% of 80 traces per bar that name the scheme (acrostic, encoding, mapping…) or write the digits out</text>'
         + legend(16, 64)]
    X = lambda v: left + pw * v / 100
    for v in (0, 50, 100):
        s.append(f'<line x1="{X(v)}" x2="{X(v)}" y1="{top - 6}" y2="{H - 34}" class="{"ax" if v == 0 else "g"}" stroke="{"#bdbcb7" if v == 0 else "#e4e3df"}"/><text x="{X(v)}" y="{H - 14}" text-anchor="middle">{v}%</text>')
    for i, lv in enumerate(LEVELS):
        y = top + i * (2 * bh + gap + 18)
        s.append(f'<text x="{left - 10}" y="{y + bh + 4}" text-anchor="end" class="row">{LEVEL_NAME[lv]}</text>')
        for j, (lab, name, cls) in enumerate(MODELS):
            x = [g for g in data[lab] if g["channel"] == "cot" and g["level"] == lv]
            v = round(100 * sum(g["talks"] or g["leaks"] for g in x) / len(x)); yy = y + j * (bh + gap); w = max(X(v) - left, 1)
            s.append(f'<g><title>{name} · {lv}: {v}% of {len(x)}</title><rect class="{cls}" fill="{HEX[cls]}" x="{left}" y="{yy}" width="{w:.1f}" height="{bh}" rx="2"/>'
                     f'<text x="{left + w + 6:.1f}" y="{yy + bh - 4}">{v}%</text></g>')
    s.append("</svg>")
    (OUT / "nest_open.svg").write_text("".join(s))


if __name__ == "__main__":
    data = {lab: load(lab) for lab, *_ in MODELS}
    fig_clean(data); fig_open(data); print("wrote", OUT / "nest_clean.svg", OUT / "nest_open.svg")
