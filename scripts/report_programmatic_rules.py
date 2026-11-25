#!/usr/bin/env python3
"""Write results/rl_local/PROGRAMMATIC_RULES.md (and the pair figure) from the rule module and the per-model check and build outputs.

    python scripts/report_programmatic_rules.py --models r1llama:R1-Llama r1qwen7:Qwen-7B gemma_many:Gemma
"""
from __future__ import annotations
import argparse, json, pickle, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "src"))
from cotctl.sft import programmatic as G
from cotctl.sft import pool as P

KIND = {"case": "Whole-text case", "letter-case": "Partial capitals", "inclusion": "Include a string", "position": "Start or end of the reasoning",
        "whole-start": "Start or end of the reasoning", "whole-end": "Start or end of the reasoning", "whole-wrap": "Wrap the whole reasoning", "structure": "Sections and wrappers",
        "block-structure": "Sections and wrappers", "paragraph": "Per paragraph", "line-layout": "Per line", "per-line": "Per line", "per-word": "Per word", "layout": "Per word",
        "markup": "Markup", "word-position": "Fixed word position", "language": "Language"}


def code(x: str) -> str:
    x = x.replace("```", "three backticks")
    return ("`` " + x + " ``") if "`" in x else ("`" + x + "`")


def rule_lists() -> tuple[str, str, int, int]:
    groups = {}
    for c in G.ALL:
        if c in G.DUPW: continue
        if c.startswith("lang:"): kind = "language"; a = {}
        elif c in P.CONDS: kind = P.CONDS[c].family; a = P.finish_args([c], {}, "Q", "A first sentence. A second sentence.")
        else: kind = G.RULES[c]["cls"]; a = {}
        alt = [k for k, v in G.DUPW.items() if v == c and k not in G.HELD]
        groups.setdefault((c in G.HELD, KIND[kind]), []).append((c, G.instruction(c, a), [G.instruction(k, a) for k in alt]))
    def section(held):
        o = []
        for (h, kind), rs in sorted(groups.items()):
            if h != held: continue
            o.append(f"### {kind}\n")
            for c, ins, alts in rs:
                o.append(f"- **{c.replace('_', ' ').replace(':', ': ')}**: {code(ins)}")
                for x in alts: o.append(f"  - other wording: {code(x)}")
            o.append("")
        return "\n".join(o)
    n_train = sum(len(v) for (h, _), v in groups.items() if not h); n_held = sum(len(v) for (h, _), v in groups.items() if h)
    return section(False), section(True), n_train, n_held


def model_rows(models) -> list[dict]:
    out = []
    for key, name in models:
        d = dict(name=name); pp = REPO / "results" / key / "prog_pool"; bp = REPO / "results" / key / "build_prog" / "Bp_stats.json"
        if (pp / "check.json").exists(): d["check"] = "PASS" if json.load(open(pp / "check.json")).get("passed") else "FAIL"
        if (pp / "bundles.pkl").exists():
            train, res = pickle.load(open(pp / "bundles.pkl", "rb"))
            for k in (6, 7): d[f"b{k}"] = sum(ok for _, ok in res.get(k, []))
        if bp.exists():
            s = json.load(open(bp)); d.update(kept=s["kept"], planned=s["planned"], remarks=s.get("remarks", {}), ls=s["length_source"], lt=s["length_target"], kinds=s["length_by_kind"])
        out.append(d)
    return out


def heatmap(pairs_path: Path, out: Path) -> dict:
    import numpy as np, matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    good, okp, single, pair = pickle.load(open(pairs_path, "rb"))[:4]
    def grp(c):
        if c.startswith("lang:"): return (0, "Language")
        if c in G.INSERTS or c == "ifb:conjunctions": return (1, "Include a string")
        if c in G.FULLCASE: return (2, "Whole-text case")
        if c in G.PARTCASE: return (3, "Partial capitals")
        if c in {"word_sep_pipe", "double_space", "ifb:square_brackets", "bigram_wrap", "five_words_per_line"}: return (4, "Per word")
        if c in G.WRAP: return (5, "Whole wrap")
        if c in G.TEXT_START and c not in G.TEXT_END: return (6, "Start of reasoning")
        if c in G.TEXT_END: return (7, "End of reasoning")
        if c in G.LINE_START: return (8, "Start of line or paragraph")
        if c in G.LINE_END: return (9, "End of line or paragraph")
        return (10, "Other")
    rules = sorted([c for c in good if c not in G.DUPW], key=lambda c: (grp(c), c)); n = len(rules); M = np.full((n, n), np.nan)
    for i, a in enumerate(rules):
        for j, b in enumerate(rules):
            if i != j:
                v = pair.get((a, b), pair.get((b, a))); M[i, j] = 2 if v >= 0.99 else (0 if v < 0 else 1)
    cnt = {k: int((M == k).sum() // 2) for k in (0, 1, 2)}
    name = lambda c: c.split(":")[-1].replace("_", " ") + (" (held out)" if c in G.HELD else "")
    fig, ax = plt.subplots(figsize=(15, 15), dpi=150); fig.patch.set_facecolor("#fcfcfb"); ax.set_facecolor("#fcfcfb")
    ax.imshow(np.ma.masked_invalid(M), cmap=ListedColormap(["#e3e2dd", "#eb6834", "#2a78d6"]), vmin=0, vmax=2, interpolation="nearest")
    ax.set_xticks(range(n)); ax.set_yticks(range(n)); ax.set_xticklabels([name(c) for c in rules], rotation=90, fontsize=6.5, color="#52514e"); ax.set_yticklabels([name(c) for c in rules], fontsize=6.5, color="#52514e")
    ax.set_xticks(np.arange(-.5, n, 1), minor=True); ax.set_yticks(np.arange(-.5, n, 1), minor=True); ax.grid(which="minor", color="#fcfcfb", linewidth=0.8); ax.tick_params(which="both", length=0)
    for s in ax.spines.values(): s.set_visible(False)
    b = [i for i in range(1, n) if grp(rules[i]) != grp(rules[i - 1])]
    for x in b: ax.axhline(x - .5, color="#0b0b0b", lw=0.9); ax.axvline(x - .5, color="#0b0b0b", lw=0.9)
    for s, e in zip([0] + b, b + [n]): ax.text(n + 0.4, (s + e - 1) / 2, grp(rules[s])[1], va="center", ha="left", fontsize=8.5, color="#0b0b0b")
    ax.set_title(f"Which pairs of rules can share a bundle ({n} rules, wordings merged)\n{cnt[2]:,} compatible, {cnt[0]:,} excluded with a reason, {cnt[1]:,} failing the test on some traces", fontsize=12, color="#0b0b0b", loc="left", pad=12)
    ax.legend(handles=[Patch(color="#2a78d6", label="Compatible: both graders pass on all test traces"), Patch(color="#e3e2dd", label="Excluded with a stated reason"),
                       Patch(color="#eb6834", label="Allowed, but a grader fails on some traces; also kept out of bundles")], loc="upper left", bbox_to_anchor=(0, -0.16), frameon=False, fontsize=9)
    plt.savefig(out, bbox_inches="tight", facecolor="#fcfcfb"); return cnt


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--models", nargs="+", required=True); ap.add_argument("--template", default=str(REPO / "results/rl_local/programmatic_rules_template.md"))
    ap.add_argument("--out", default=str(REPO / "results/rl_local/PROGRAMMATIC_RULES.md")); a = ap.parse_args()
    models = [m.split(":", 1) for m in a.models]; T, H, nt, nh = rule_lists(); M = model_rows(models)
    f = lambda v: f"{v:,}" if isinstance(v, int) else str(v)
    t1 = ["| Model | Pool check | Valid bundles of 6 | Valid bundles of 7 | Training rows built |", "|---|---|---|---|---|"]
    t2 = ["| Model | Rows with a remark | Remark sentences | Words, control to treated | Characters | Model tokens |", "|---|---|---|---|---|---|"]
    t3 = ["| Model | Rows | Words, control to treated | Model tokens, control to treated |", "|---|---|---|---|"]
    lab = {"plain": "no language rule", "lang_en": "language set to English", "lang": "translated"}
    for d in M:
        t1.append(f"| {d['name']} | {d.get('check', 'not run')} | {f(d.get('b6', '-'))} | {f(d.get('b7', '-'))} | {(str(d['kept']) + ' of ' + str(d['planned'])) if 'kept' in d else 'not built'} |")
        if "kept" in d:
            md = lambda k: f"{d['ls'][k]['median']:,.0f} to {d['lt'][k]['median']:,.0f}"
            t2.append(f"| {d['name']} | {d['remarks'].get('rows_with_a_remark', '-')} | {f(d['remarks'].get('remark_sentences', '-'))} | {md('words')} | {md('chars')} | {md('model_tokens') if 'model_tokens' in d['ls'] else '-'} |")
            for k in ("plain", "lang_en", "lang"):
                if k in d["kinds"]:
                    v = d["kinds"][k]; g = lambda m: f"{v['source'][m]['median']:,.0f} to {v['target'][m]['median']:,.0f}"
                    t3.append(f"| {d['name']} | {v['rows']} {lab[k]} | {g('words')} | {g('model_tokens') if 'model_tokens' in v['source'] else '-'} |")
    first = REPO / "results" / models[0][0] / "prog_pool" / "pairs.pkl"; cnt = heatmap(first, Path(a.out).with_name("rule_pair_heatmap.png")) if first.exists() else {}
    md = open(a.template).read()
    for k, v in {"{TRAIN_RULES}": T, "{HELD_RULES}": H, "{N_TRAIN}": str(nt), "{N_HELD}": str(nh), "{MODEL_TABLE}": "\n".join(t1), "{BUILD_TABLE}": "\n".join(t2), "{KIND_TABLE}": "\n".join(t3),
                 "{N_EXPLICIT}": str(len(G.EXPLICIT)), "{HEAT_MODEL}": models[0][1]}.items(): md = md.replace(k, v)
    open(a.out, "w").write(md); print("wrote", a.out, "| training rules", nt, "| held out", nh, "| pairs", cnt)
    return 0


if __name__ == "__main__": raise SystemExit(main())
