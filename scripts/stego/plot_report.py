#!/usr/bin/env python3
"""Report figures for STEGO_EXPERIMENT.md as standalone SVGs in figs/stego/ (light and dark via prefers-color-scheme).
Numbers are copied from the md tables they illustrate (section named in each function); the NEST figures are built
from the graded rollouts by plot_nest.py. Base models are always blue (slot 1), trained models orange (slot 2).

    python3 scripts/stego/plot_report.py
"""
from pathlib import Path
from html import escape

OUT = Path(__file__).resolve().parents[2] / "figs/stego"; OUT.mkdir(parents=True, exist_ok=True)
LIGHT = dict(bg="#fcfcfb", t1="#0b0b0b", t2="#52514e", grid="#e4e3df", axis="#bdbcb7", s1="#2a78d6", s2="#eb6834",
             s2b="#f5ab8a", neu="#cfcec9", s3="#1baf7a", s7="#6250d6")
DARK = dict(bg="#1a1a19", t1="#f0efec", t2="#c3c2b7", grid="#2e2e2c", axis="#4a4a47", s1="#3987e5", s2="#d95926",
            s2b="#8c4325", neu="#4f4e4b", s3="#199e70", s7="#9085e9")
_vars = lambda d: ";".join(f"--{k}:{v}" for k, v in d.items())
STYLE = (f"<style>.v{{{_vars(LIGHT)}}}@media (prefers-color-scheme:dark){{:root:not([data-theme=light]) .v{{{_vars(DARK)}}}}}"
         f":root[data-theme=dark] .v{{{_vars(DARK)}}}"
         ".v text{font-family:'IBM Plex Sans',system-ui,sans-serif;fill:var(--t2);font-size:11px}"
         ".v .ttl{fill:var(--t1);font-size:14px;font-weight:600}.v .sub{font-size:12px}.v .lab{fill:var(--t1);font-size:12px}"
         ".v .ph{fill:var(--t1);font-size:12px;font-weight:600}.v .val{fill:var(--t1)}"
         + "".join(f".v .f-{k}{{fill:var(--{k})}}.v .k-{k}{{stroke:var(--{k})}}" for k in ("s1", "s2", "s2b", "neu", "grid", "axis", "t2", "s3", "s7"))
         + ".v .bgfill{fill:var(--bg)}.v .ring{stroke:var(--bg)}</style>")
NAMES = {"s1": "base", "s2": "controllability-trained"}


def svg(W, H, title, sub, label, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" class="v" viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="{escape(label)}">'
            f'{STYLE}<rect width="{W}" height="{H}" class="bgfill" fill="{LIGHT["bg"]}"/>'
            f'<text x="16" y="24" class="ttl">{escape(title)}</text><text x="16" y="42" class="sub">{escape(sub)}</text>{body}</svg>')


def swatch(x, y, key, text, line=False):
    mark = (f'<line x1="{x}" y1="{y}" x2="{x + 18}" y2="{y}" class="k-{key}" stroke="{LIGHT[key]}" stroke-width="2"/>'
            f'<circle cx="{x + 9}" cy="{y}" r="4" class="f-{key} ring" fill="{LIGHT[key]}" stroke="{LIGHT["bg"]}" stroke-width="2"/>' if line else
            f'<rect x="{x}" y="{y - 6}" width="12" height="12" rx="2" class="f-{key}" fill="{LIGHT[key]}"/>')
    return mark + f'<text x="{x + (24 if line else 18)}" y="{y + 4}">{escape(text)}</text>'


def legend(x, y, items, line=False):
    out, xx = [], x
    for key, text in items:
        out.append(swatch(xx, y, key, text, line)); xx += 30 + 6.6 * len(text)
    return "".join(out)


def hbars(name, title, sub, groups, vmax, ticks, fmt, series=(("s1", "base"), ("s2", "controllability-trained")), left=210, W=720, note=None):
    """groups: [(label, [value per series], [text per series] or None)]. Horizontal grouped bars, value labels at the end."""
    bh, gap, ggap, top = 15, 3, 16, 84
    n = len(series); gh = n * bh + (n - 1) * gap
    H = top + len(groups) * (gh + ggap) + 34 + (18 if note else 0); pw = W - left - 70
    X = lambda v: left + pw * min(v, vmax) / vmax
    b = [legend(16, 62, series)]
    for t in ticks:
        b.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{top - 6}" y2="{H - 38 - (18 if note else 0)}" class="k-{"axis" if t == 0 else "grid"}" stroke="{LIGHT["axis" if t == 0 else "grid"]}"/>'
                 f'<text x="{X(t):.1f}" y="{H - 22 - (18 if note else 0)}" text-anchor="middle">{fmt(t)}</text>')
    for i, (lab, vals, texts) in enumerate(groups):
        y = top + i * (gh + ggap)
        lines = lab.split("\n")
        for k, ln in enumerate(lines):
            b.append(f'<text x="{left - 10}" y="{y + gh / 2 + 4 + (k - (len(lines) - 1) / 2) * 14:.1f}" text-anchor="end" class="lab">{escape(ln)}</text>')
        for j, ((key, sname), v) in enumerate(zip(series, vals)):
            if v is None: continue
            yy = y + j * (bh + gap); w = max(X(v) - left, 1.5); t = texts[j] if texts else fmt(v)
            b.append(f'<g><title>{escape(lab.replace(chr(10), " "))} · {escape(sname)}: {escape(t)}</title>'
                     f'<rect x="{left}" y="{yy}" width="{w:.1f}" height="{bh}" rx="2" class="f-{key}" fill="{LIGHT[key]}"/>'
                     f'<text x="{left + w + 6:.1f}" y="{yy + bh - 3.5}" class="val">{escape(t)}</text></g>')
    if note: b.append(f'<text x="16" y="{H - 8}">{escape(note)}</text>')
    (OUT / f"{name}.svg").write_text(svg(W, H, title, sub, title, "".join(b)))


def stacked(name, title, sub, rows, parts, total_max, left=250, W=740):
    """rows: [(label, [count per part])]; parts: [(key, name)]. Horizontal stacked bars of counts, 2px surface gaps."""
    bh, gap, top = 18, 10, 84; H = top + len(rows) * (bh + gap) + 40; pw = W - left - 50
    X = lambda v: pw * v / total_max
    b = [legend(16, 62, parts)]
    for t in range(0, total_max + 1, 20):
        b.append(f'<line x1="{left + X(t):.1f}" x2="{left + X(t):.1f}" y1="{top - 6}" y2="{H - 34}" class="k-{"axis" if t == 0 else "grid"}" stroke="{LIGHT["axis" if t == 0 else "grid"]}"/>'
                 f'<text x="{left + X(t):.1f}" y="{H - 18}" text-anchor="middle">{t}</text>')
    for i, (lab, vals) in enumerate(rows):
        y = top + i * (bh + gap); x = left
        b.append(f'<text x="{left - 10}" y="{y + bh - 4}" text-anchor="end" class="lab">{escape(lab)}</text>')
        for (key, pname), v in zip(parts, vals):
            if v <= 0: continue
            w = X(v)
            b.append(f'<g><title>{escape(lab)} · {escape(pname)}: {v}</title><rect x="{x:.1f}" y="{y}" width="{max(w - 2, 1):.1f}" height="{bh}" rx="2" class="f-{key}" fill="{LIGHT[key]}"/></g>')
            x += w
        b.append(f'<text x="{x + 4:.1f}" y="{y + bh - 4}" class="val">{sum(vals)}</text>')
    (OUT / f"{name}.svg").write_text(svg(W, H, title, sub, title, "".join(b)))


def lines(name, title, sub, panels, xs, ymax, yticks, ylab, series, chance_key="chance", legend_chance="chance"):
    """panels: [(panel title, {series key: [y per x], 'chance': [y per x]})]. Small multiples with a dashed chance line."""
    pw, ph, gx, left, top = 190, 140, 34, 52, 104
    W = left + len(panels) * pw + (len(panels) - 1) * gx + 20; H = top + ph + 46
    b = [legend(16, 62, series, line=True) + f'<line x1="{16 + sum(30 + 6.6 * len(t) for _, t in series)}" y1="62" x2="{34 + sum(30 + 6.6 * len(t) for _, t in series)}" y2="62" class="k-t2" stroke="{LIGHT["t2"]}" stroke-dasharray="4 3"/>'
         f'<text x="{40 + sum(30 + 6.6 * len(t) for _, t in series)}" y="66">{escape(legend_chance)}</text>']
    for c, (pt, d) in enumerate(panels):
        x0 = left + c * (pw + gx)
        X = lambda i: x0 + 10 + (pw - 20) * i / (len(xs) - 1); Y = lambda v: top + ph - ph * v / ymax
        b.append(f'<text x="{x0}" y="{top - 14}" class="ph">{escape(pt)}</text>')
        for t in yticks:
            b.append(f'<line x1="{x0}" x2="{x0 + pw}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" class="k-{"axis" if t == 0 else "grid"}" stroke="{LIGHT["axis" if t == 0 else "grid"]}"/>')
            if c == 0: b.append(f'<text x="{x0 - 6}" y="{Y(t) + 4:.1f}" text-anchor="end">{t}</text>')
        for i, x in enumerate(xs): b.append(f'<text x="{X(i):.1f}" y="{top + ph + 16}" text-anchor="middle">{x}</text>')
        if chance_key in d:
            b.append(f'<path d="' + " ".join(f'{"M" if i == 0 else "L"}{X(i):.1f},{Y(v):.1f}' for i, v in enumerate(d[chance_key])) +
                     f'" fill="none" class="k-t2" stroke="{LIGHT["t2"]}" stroke-width="1.5" stroke-dasharray="4 3"/>')
        for key, sname in series:
            ys = d[key]
            b.append(f'<path d="' + " ".join(f'{"M" if i == 0 else "L"}{X(i):.1f},{Y(v):.1f}' for i, v in enumerate(ys)) +
                     f'" fill="none" class="k-{key}" stroke="{LIGHT[key]}" stroke-width="2"/>')
            for i, v in enumerate(ys):
                b.append(f'<g><title>{escape(pt)} · {escape(sname)} · {xs[i]}: {v}</title><circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="10" fill="transparent"/>'
                         f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="4" class="f-{key} ring" fill="{LIGHT[key]}" stroke="{LIGHT["bg"]}" stroke-width="2"/></g>')
    b.append(f'<text x="{left + (W - left) / 2 - 10}" y="{H - 8}" text-anchor="middle">{escape(ylab)}</text>')
    (OUT / f"{name}.svg").write_text(svg(W, H, title, sub, title, "".join(b)))


pct = lambda v: f"{v:g} %"
of300 = lambda v: f"{v:g}"

# Setup: controllability of Qwen base and B (table "trained rules / held-out rules")
hbars("controllability", "Controllability training worked on its own terms (Qwen3.8-27B)",
      "Rule followed, % of prompts · 40 rules × T1–T3 × 10 questions · held-out = rules never in training",
      [("trained rules", [17.3, 64.0], None), ("held-out rules", [8.2, 47.2], None), ("answer accuracy", [89, 93], None)],
      100, (0, 25, 50, 75, 100), pct, series=(("s1", "Qwen base"), ("s2", "Qwen B")), left=150)

# Results / gpt-oss sections: follows the disguise instruction (crypto), against encoded success at depth 3+ (0 everywhere)
hbars("covert_follow", "Trained models obey disguise instructions more, but the computation does not survive",
      "Crypto tasks: % of rollouts whose reasoning follows the instruction · encoded success at depth 3+ is 0 % for all four models",
      [("Qwen, “think about\nsomething unrelated”", [1.5, 30.6], None), ("Qwen, woodland\njourney", [1.5, 11.9], None),
       ("gpt-oss-120b, “think\nabout something unrelated”", [11.9, 21.6], None), ("gpt-oss-120b,\nwoodland journey", [1.5, 23.1], None)],
      50, (0, 10, 20, 30, 40, 50), pct, left=210,
      note="Encoded success = correct, follows the instruction, no working in the visible answer (the post's criterion).")

# Eval A + eval B sections: natural acrostics under the natural instruction, all four models
hbars("hide_natural", "Hiding a 5-letter word in the reasoning: trained models do it, base models rarely",
      "Natural acrostics (right letters, real words, no letter labels), of 300 attempts per bar",
      [("Qwen3.8-27B,\nsentence acrostic", [0, 46], None), ("Qwen3.8-27B,\nline acrostic", [1, 89], None),
       ("gpt-oss-120b,\nsentence acrostic", [0, 27], None), ("gpt-oss-120b,\nline acrostic", [22, 65], None)],
      100, (0, 25, 50, 75, 100), of300, left=150)

# Eval B: what the gpt-4.1 monitor (told a word may be hidden) does with each natural acrostic
stacked("hide_monitor", "Against a monitor told to look for a hidden word, about half the acrostics survive",
        "Natural acrostics of 300 attempts, split by what the gpt-4.1 monitor did (eval B); bar length = natural acrostics",
        [("Qwen B · sentence, natural", [8, 15, 0, 23]), ("Qwen B · line, natural", [15, 19, 0, 55]),
         ("Qwen B · sentence, covert warning", [14, 8, 0, 16]), ("Qwen B · line, covert warning", [15, 13, 0, 36]),
         ("120b fine-tuned · sentence, natural", [0, 8, 1, 18]), ("120b fine-tuned · line, natural", [1, 8, 1, 55]),
         ("120b fine-tuned · line, covert warning", [2, 13, 4, 43]), ("120b base · line, natural", [1, 6, 1, 14]),
         ("Qwen base · line, natural", [0, 0, 0, 1])],
        [("s2", "not read, not suspected"), ("s2b", "not read, suspected"), ("grid", "not read, answer wrong"), ("neu", "read by the monitor")], 100)

# Capacity section: accuracy per bit actually written (decoded bits that match, over decoded bits; missing sentences
# excluded), computed from results/stego/cap_qwen_{base,B}/graded.jsonl. A random payload makes chance exactly 50 %.
cap = {"parity": ([46.6, 50.6, 52.1], [49.7, 49.3, 51.1]), "comma": ([52.0, 48.5, 50.8], [50.4, 51.9, 50.2]),
       "initial": ([50.2, 47.5, 50.5], [49.5, 53.1, 50.4])}
lines("capacity", "Hiding 8–32 random bits: every bit written is a coin flip",
      "% of bits right among the sentences actually written (missing sentences excluded) · dashed = chance, 50 %",
      [(f"{k}: " + {"parity": "word-count parity", "comma": "comma or not", "initial": "first letter A–M / N–Z"}[k], dict(s1=v[0], s2=v[1], chance=[50, 50, 50]))
       for k, v in cap.items()], [8, 16, 32], 100, (0, 25, 50, 75, 100), "bits hidden", (("s1", "Qwen base"), ("s2", "Qwen B")), legend_chance="chance (random payload)")

# Detectability section: three detectors on Qwen B's successful acrostics
hbars("detect", "Who catches Qwen B's acrostics depends on what the detector is told",
      "% of B's successful natural acrostics · plain row = false alarms on B's reasoning with nothing hidden",
      [("sentence, natural", [8.7, 39.1], None), ("line, natural", [12.6, 54.0], None),
       ("sentence, covert warning", [2.7, 29.7], None), ("line, covert warning", [6.3, 34.9], None),
       ("plain (nothing hidden)", [4.0, 1.7], ["4 % flagged", "1.7 % flagged"])],
      100, (0, 25, 50, 75, 100), pct, left=170,
      series=(("s3", "unprimed monitor flags it"), ("s7", "scheme-aware monitor reads the word")),
      note="A gpt-4.1 paraphrase leaves 0 of 233 hidden words intact; likelihood under base Qwen separates them (AUROC 0.99).")

# Answer-acrostic section: the channel swap
hbars("channel_swap", "The same acrostic, two channels: base hides in its answer, B in its reasoning",
      "Qwen3.8-27B, natural acrostics of 300 attempts · reasoning = thinking on, acrostic must open the reasoning",
      [("in the reasoning,\nsentence", [0, 46], None), ("in the reasoning,\nline", [1, 89], None),
       ("in the answer,\nsentence, thinking off", [121, 22], None), ("in the answer,\nline, thinking off", [204, 53], None),
       ("in the answer,\nsentence, thinking on", [248, 9], None), ("in the answer,\nline, thinking on", [171, 7], None)],
      300, (0, 100, 200, 300), of300, series=(("s1", "Qwen base"), ("s2", "Qwen B")), left=170)

# Gemma section: the acrostic in each channel (results/stego/hideA_gemma_{base,B}, natural acrostics of 300, as %)
hbars("gemma_channel", "Gemma-4-31B: base hides in its answer, B in its reasoning",
      "Natural acrostics, % of 300 attempts · bottom rows: asked to hide in the reasoning, the acrostic went into the answer",
      [("in the reasoning,\nsentence", [0, 58.0], None), ("in the reasoning,\nline", [0, 50.7], None),
       ("in the answer,\nsentence, thinking off", [91.7, 14.7], None), ("in the answer,\nline, thinking off", [94.3, 17.0], None),
       ("in the answer,\nsentence, thinking on", [97.7, 41.7], None), ("in the answer,\nline, thinking on", [99.0, 21.3], None),
       ("asked for the reasoning,\nput in the answer: sentence", [94.3, 1.0], None), ("asked for the reasoning,\nput in the answer: line", [95.3, 0], None)],
      100, (0, 25, 50, 75, 100), pct, series=(("s1", "Gemma base"), ("s2", "Gemma B")), left=200)

# Gemma section: v2 rules applied to the answer (results/v2_gemma/eval_answer/{base,B}/summary.json, mean over rules)
hbars("gemma_v2answer", "Rules on the visible answer: B follows them less than base, and more often in its reasoning",
      "Gemma-4-31B, 40 v2 rules × T1–T3 × 20 questions, mean % compliant · trained / held-out = B's training split",
      [("answer, thinking off,\ntrained rules", [72.9, 69.2], None), ("answer, thinking off,\nheld-out rules", [61.9, 50.2], None),
       ("answer, thinking on,\ntrained rules", [77.3, 53.6], None), ("answer, thinking on,\nheld-out rules", [70.1, 37.1], None),
       ("rule met in the reasoning\ninstead, trained", [14.3, 27.6], None), ("rule met in the reasoning\ninstead, held-out", [12.0, 25.9], None)],
      100, (0, 25, 50, 75, 100), pct, series=(("s1", "Gemma base"), ("s2", "Gemma B")), left=200,
      note="Chance (rule met without being asked) 2–4 % for both. 'In the reasoning' covers the 36 rules graded by code.")

stacked("gemma_monitor", "Against the monitor: Gemma B hides more sentence acrostics than Qwen B, lines about the same",
        "Natural acrostics in the reasoning, of 300 attempts, split by what the gpt-4.1 monitor did · read = at least 3 of 5 letters right",
        [("Gemma B · sentence, natural", [27, 44, 7, 96]), ("Gemma B · line, natural", [12, 35, 4, 101]),
         ("Qwen B · sentence, natural", [8, 15, 0, 23]), ("Qwen B · line, natural", [15, 19, 0, 55])],
        [("s2", "not read, not suspected"), ("s2b", "not read, suspected"), ("grid", "not read, answer wrong"), ("neu", "read by the monitor")], 180)

print("wrote", sorted(p.name for p in OUT.glob("*.svg")))
