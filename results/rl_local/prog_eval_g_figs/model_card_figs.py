"""Figures for a model's results page on Hugging Face (see HF_UPLOADS.md): compliance on trained and held-out rules,
how concentrated the gain is, per-rule compliance, answer accuracy. Reads the output of scripts/run_programmatic_eval.py
(each arm's graded.jsonl and the compare.json of Version: ImageMagick 6.9.12-98 Q16 x86_64 18038 https://legacy.imagemagick.org
Copyright: (C) 1999 ImageMagick Studio LLC
License: https://imagemagick.org/script/license.php
Features: Cipher DPC Modules OpenMP(4.5) 
Delegates (built-in): bzlib djvu fftw fontconfig freetype heic jbig jng jp2 jpeg lcms lqr ltdl lzma openexr pangocairo png raw tiff webp wmf x xml zlib
Usage: compare-im6.q16 [options ...] image reconstruct difference

Image Settings:
  -alpha option        on, activate, off, deactivate, set, opaque, copy
                       transparent, extract, background, or shape
  -authenticate password
                       decipher image with this password
  -background color    background color
  -channel type        apply option to select image channels
  -colorspace type     alternate image colorspace
  -compose operator    set image composite operator
  -compress type       type of pixel compression when writing the image
  -decipher filename   convert cipher pixels to plain pixels
  -define format:option
                       define one or more image format options
  -density geometry    horizontal and vertical density of the image
  -depth value         image depth
  -dissimilarity-threshold value
                       maximum distortion for (sub)image match
  -encipher filename   convert plain pixels to cipher pixels
  -extract geometry    extract area from image
  -format "string"     output formatted image characteristics
  -fuzz distance       colors within this distance are considered equal
  -gravity type        horizontal and vertical text placement
  -highlight-color color
                       emphasize pixel differences with this color
  -identify            identify the format and characteristics of the image
  -interlace type      type of image interlacing scheme
  -limit type value    pixel cache resource limit
  -lowlight-color color
                       de-emphasize pixel differences with this color
  -mask filename       associate a mask with the image
  -metric type         measure differences between images with this metric
  -monitor             monitor progress
  -passphrase filename get the passphrase from this file
  -precision value     maximum number of significant digits to print
  -profile filename    add, delete, or apply an image profile
  -quality value       JPEG/MIFF/PNG compression level
  -quiet               suppress all warning messages
  -quantize colorspace reduce colors in this colorspace
  -regard-warnings     pay attention to warning messages
  -repage geometry     size and location of an image canvas
  -respect-parentheses settings remain in effect until parenthesis boundary
  -sampling-factor geometry
                       horizontal and vertical sampling factor
  -seed value          seed a new sequence of pseudo-random numbers
  -set attribute value set an image attribute
  -quality value       JPEG/MIFF/PNG compression level
  -similarity-threshold value
                       minimum distortion for (sub)image match
  -size geometry       width and height of image
  -subimage-search     search for subimage
  -synchronize         synchronize image to storage device
  -taint               declare the image as modified
  -transparent-color color
                       transparent color
  -type type           image type
  -verbose             print detailed information about the image
  -version             print version information
  -virtual-pixel method
                       virtual pixel access method

Image Operators:
  -brightness-contrast geometry
                       improve brightness / contrast of the image
  -distort method args
                       distort images according to given method and args
  -level value         adjust the level of image contrast
  -resize geometry     resize the image
  -rotate degrees      apply Paeth rotation to the image
  -sigmoidal-contrast geometry
                       increase the contrast without saturating highlights or
  -trim                trim image edges

Image Sequence Operators:
  -crop geometry       cut out a rectangular region of the image
  -separate            separate an image channel into a grayscale image
  -write filename      write images to this file

Image Stack Operators:
  -delete indexes      delete the image from the image sequence

Miscellaneous Options:
  -debug events        display copious debugging information
  -help                print program options
  -list type           print a list of supported option arguments
  -log format          format of debugging information

By default, the image format of `file' is determined by its magic
number.  To specify a particular image format, precede the filename
with an image format name and a colon (i.e. ps:image) or specify the
image type as the filename suffix (i.e. image.ps).  Specify 'file' as
'-' for standard input or output.).

  python results/rl_local/prog_eval_g_figs/model_card_figs.py --eval-dir results/r1qwen7/prog_eval_g --out <model folder>/figures
  (arm folders default to base, Bpctrlg, Bpg; set --base/--control/--treated for others; run from the repo root)"""
import argparse, json
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
ap = argparse.ArgumentParser(); ap.add_argument("--eval-dir", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--base", default="base"); ap.add_argument("--control", default="Bpctrlg"); ap.add_argument("--treated", default="Bpg")
a = ap.parse_args(); D, OUT = Path(a.eval_dir), Path(a.out); OUT.mkdir(parents=True, exist_ok=True)
ARM = {"base": a.base, "Bpctrlg": a.control, "Bpg": a.treated}
C_CTRL, C_TREAT, C_BASE, INK, INK2, GRID, BG = "#2a78d6", "#eb6834", "#8a8984", "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "axes.labelcolor": INK,
                     "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": BG, "axes.facecolor": BG})
cmp = json.load(open(D / "compare.json"))
L = lambda arm: [json.loads(l) for l in open(D / ARM[arm] / "graded.jsonl")]
G = {a: L(a) for a in ("base", "Bpctrlg", "Bpg")}
def per_rule(arm, kind):
    d = {}
    for g in G[arm]:
        if g["kind"] == kind: d.setdefault(g["rules"][0], []).append(bool(g["usable"] and g["compliant"]))
    return {k: 100 * sum(v) / len(v) for k, v in d.items()}
def save(fig, name): fig.tight_layout(); fig.savefig(OUT / name, dpi=160); plt.close(fig)

# 1. compliance: in-domain (trained) and generalisation (held-out)
fig, ax = plt.subplots(figsize=(5.6, 3.6))
for i, kind in enumerate(["trained", "held_out"]):
    t = cmp[kind]["treated_vs_control"]
    for j, (v, c, lab) in enumerate([(t["reference"], C_CTRL, "control"), (t["arm"], C_TREAT, "treated")]):
        ax.bar(i + (j - .5) * .36, 100 * v, .34, color=c, label=lab if i == 0 else None, edgecolor=BG, linewidth=2)
        ax.text(i + (j - .5) * .36, 100 * v + 1, f"{100*v:.1f}", ha="center", va="bottom", fontsize=9, color=INK)
    lo, hi = t["gain_95"]; ax.text(i, 46, f"gain {t['gain']:.2f} [{lo:.2f}, {hi:.2f}]", ha="center", fontsize=8.5, color=INK2)
ax.set_xticks([0, 1], [f"trained rules ({cmp['trained']['treated_vs_control']['rules']})\nin-domain", f"held-out rules ({cmp['held_out']['treated_vs_control']['rules']})\ngeneralisation"])
ax.set_ylim(0, 52); ax.set_ylabel("rule compliance, % of rollouts"); ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True)
ax.legend(frameon=False, loc="upper right", bbox_to_anchor=(1, .9)); save(fig, "compliance.png")

# 2. concentration: cumulative share of the summed per-rule gain, rules sorted by gain
fig, ax = plt.subplots(figsize=(5.6, 3.6))
for kind, c, lab in [("trained", C_CTRL, "trained rules"), ("held_out", C_TREAT, "held-out rules")]:
    v = sorted(cmp[kind]["treated_vs_control"]["per_rule_difference_points"].values(), reverse=True); tot = sum(v); cum = 0; ys = []
    for x in v: cum += x; ys.append(100 * cum / tot)
    ax.plot(range(1, len(v) + 1), ys, color=c, lw=2, label=lab, marker="o", ms=3.5)
ax.axhline(80, color=GRID, lw=1); ax.set_xlabel("number of rules, largest gain first"); ax.set_ylabel("share of total gain, %")
ax.set_ylim(0, 105); ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.legend(frameon=False, loc="lower right"); save(fig, "concentration.png")

# 3/4. per-rule compliance, control vs treated
for kind in ["trained", "held_out"]:
    c, t = per_rule("Bpctrlg", kind), per_rule("Bpg", kind); ks = sorted(c, key=lambda k: t[k] - c[k])
    fig, ax = plt.subplots(figsize=(6, 0.24 * len(ks) + 1.2))
    for y, k in enumerate(ks): ax.plot([c[k], t[k]], [y, y], color=GRID, lw=2, zorder=1)
    ax.scatter([c[k] for k in ks], range(len(ks)), s=26, color=C_CTRL, label="control", zorder=2, edgecolor=BG)
    ax.scatter([t[k] for k in ks], range(len(ks)), s=26, color=C_TREAT, label="treated", zorder=3, edgecolor=BG)
    ax.set_yticks(range(len(ks)), ks, fontsize=7.5); ax.set_xlim(-3, 103); ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True)
    ax.set_xlabel("compliance, % of 50 prompts"); ax.legend(frameon=False, loc="lower right")
    ax.set_title(f"{'Trained' if kind == 'trained' else 'Held-out'} rules, sorted by treated minus control", fontsize=10, color=INK)
    save(fig, f"per_rule_{kind}.png")

# 5. answer accuracy by prompt set
sets = [("P0", "no rules"), ("trained", "trained rules"), ("held_out", "held-out rules"), ("P2", "bundles")]
fig, ax = plt.subplots(figsize=(6.4, 3.4))
for j, (arm, cl, lab) in enumerate([("base", C_BASE, "base"), ("Bpctrlg", C_CTRL, "control"), ("Bpg", C_TREAT, "treated")]):
    for i, (s, _) in enumerate(sets):
        x = [v for v in G[arm] if (v["set"] == s if s in ("P0", "P2") else v["kind"] == s)]
        if not x: continue
        acc = 100 * sum(bool(v["correct"]) for v in x) / len(x)
        ax.bar(i + (j - 1) * .27, acc, .25, color=cl, label=lab if s == "P0" else None, edgecolor=BG, linewidth=1.5)
ax.set_xticks(range(4), [s[1] for s in sets]); ax.set_ylim(0, 100); ax.set_ylabel("answer accuracy, %")
ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(.5, 1.12)); save(fig, "accuracy.png")
print("ok", sorted(p.name for p in OUT.glob("*.png")))
