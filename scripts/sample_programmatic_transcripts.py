#!/usr/bin/env python3
"""Write randomly chosen built rows, with their remarks, to a markdown file (and a PDF if weasyprint is installed) for reading.

    python scripts/sample_programmatic_transcripts.py --remarks-build results/r1qwen7/remarks_kept/build.json \
        --train data/sft/r1q7prog_Bp.jsonl --out results/rl_local/TRANSCRIPTS_WITH_REMARKS_QWEN7.md --title "Qwen-7B"
"""
import argparse, json, random, re
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--remarks-build", required=True); ap.add_argument("--train", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--title", default=""); ap.add_argument("--seed", type=int, default=77); a = ap.parse_args()
    B = {r["row"]: r for r in json.load(open(a.remarks_build)) if r.get("status") == "ok"}
    T = {json.loads(l)["row_idx"]: json.loads(l) for l in open(a.train)}; B = {k: v for k, v in B.items() if k in T}
    rnd = random.Random(a.seed); en = [r for r in B.values() if r["language"] == "en"]; lg = [r for r in B.values() if r["language"] != "en"]
    pick = rnd.sample([r for r in en if r["remarks"]], 8) + rnd.sample([r for r in en if not r["remarks"]], 3) + rnd.sample([r for r in lg if r["remarks"] and len(r["source"].split()) < 500], 5)
    fence = lambda x: "~~~~text\n" + x.replace("~~~~", "~~~ ~").rstrip("\n") + "\n~~~~"
    md = [f"# Transcripts with remarks to inspect: {a.title}", "",
          f"- {len(pick)} rows chosen at random from the {len(T)} built rows: eight English rows with remarks, three English rows without, five translated rows with remarks.",
          "- A remark is a sentence about the rules that the base model itself wrote when given this exact prompt. It is copied into the target at the end of a line, at the same relative position.",
          "- Order of edits: remarks into the model's own trace, then translation for a language row, then the code rules.", "- Every row passes all of its graders.", ""]
    for i, r in enumerate(pick, 1):
        target = re.search(r"<think>\n(.*)\n</think>", T[r["row"]]["messages"][-1]["content"], re.S).group(1)
        md += [f"## {i}. Row {r['row']} ({'translated to ' + r['language'] if r['language'] != 'en' else 'English'}, {len(r['remarks'])} remark sentences)", "",
               f"- Length in words: source {len(r['source'].split())}, target {len(target.split())}", "", "### Rules, in prompt order", ""]
        md += [f"{j + 1}. **{c.replace('_', ' ').replace(':', ': ')}**: `{ins.replace('`', chr(39))}`" for j, (c, ins) in enumerate(zip(r["rules"], r["instructions"]))]
        md += ["", "### Prompt", "", fence(r["prompt"]), "", "### Remarks copied from the base model", ""] + ([f"- {x['text']}" for x in r["remarks"]] or ["- none: the base model made no remark on this prompt"])
        md += ["", "### Source trace (the model's own, unedited)", "", fence(r["source"]), "", "### With remarks" + (" and translated" if r["language"] != "en" else "") + ", before the code rules", "",
               fence(r["before_rules"]), "", "### Training target", "", fence(target), ""]
    Path(a.out).write_text("\n".join(md))
    try:
        from markdown_it import MarkdownIt
        from weasyprint import HTML
        css = """@page{size:A4;margin:16mm 14mm} body{font-family:'DejaVu Sans',Arial,sans-serif;font-size:9.5pt;line-height:1.4;color:#111}
h1{font-size:17pt} h2{font-size:13pt;margin-top:20pt;border-bottom:1px solid #bbb;padding-bottom:2pt;page-break-before:always} h2:first-of-type{page-break-before:auto} h3{font-size:10.5pt;margin-top:10pt}
pre{font-family:'DejaVu Sans Mono',monospace;font-size:7.6pt;background:#f4f4f2;border:1px solid #ddd;padding:5pt;white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word}
code{font-family:'DejaVu Sans Mono',monospace;font-size:8pt;background:#f2f2f2;overflow-wrap:anywhere} li{margin:1.5pt 0}"""
        HTML(string=f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>{MarkdownIt('commonmark').render(chr(10).join(md))}</body></html>").write_pdf(str(Path(a.out).with_suffix(".pdf")))
    except ImportError: pass
    print("wrote", a.out)


if __name__ == "__main__": main()
