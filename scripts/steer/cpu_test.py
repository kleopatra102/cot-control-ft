#!/usr/bin/env python3
"""End-to-end CPU test of pieces 1-5 on Qwen/Qwen3-0.6B with a handful of real base rollouts.
Checks shapes, span alignment (decoded token span reproduces the sentence), hook wiring, direction
fitting, probe metrics, steering hook changes the output, and rollout schema. ~2-4 minutes on CPU.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import torch
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from transformers import AutoTokenizer
from cotctl.steer.spans import build_spans, full_text
from cotctl.steer.pairs import build_pairs
from cotctl.steer.activations import load_model, span_vectors, text_vector, token_range, decoder_layers
from cotctl.steer.directions import mean_diff, evaluate, logistic_probe, deconfound
from cotctl.steer.harness import generate_steered
from cotctl.graders.cotcontrol import grade_cotcontrol
torch.set_num_threads(16); M = "Qwen/Qwen3-0.6B"; t0 = time.time()
tok = AutoTokenizer.from_pretrained(M)
# ---- 1. spans (restricted to a few sample_ids to keep CPU time small)
ids = {json.loads(l)["sample_id"] for l in open(REPO / "results/strip_llm/rollouts_base_cotcontrol.jsonl")}
some = sorted(ids)[:40]
spans = build_spans("base", "cotcontrol", REPO, tok, max_per_trace=3, max_tokens=3000, sample_ids=set(some))
pos = [s for s in spans if s.is_narration]; neg = [s for s in spans if not s.is_narration]
assert len(pos) == len(neg) > 0, (len(pos), len(neg)); print(f"[1] spans: {len(pos)} narration + {len(neg)} negatives from {len({s.sample_id+s.mode for s in spans})} traces ({time.time()-t0:.0f}s)")
# alignment check: decode token span, compare to sentence text
roll = {(r["sample_id"], r["mode"]): r for r in map(json.loads, open(REPO / "results/base/cotcontrol_rollouts.jsonl"))}
bad = 0
for s in spans[:20]:
    r = roll[(s.sample_id, s.mode)]; text, off = full_text(tok, r["prompt"], r["reasoning"], r.get("answer") or "")
    enc = tok(text, add_special_tokens=False)["input_ids"]; dec = tok.decode(enc[s.tok_start:s.tok_end])
    core = s.text.strip()[:30]
    if core[:15].lower() not in dec.lower(): bad += 1; print("   misaligned:", repr(core), "->", repr(dec[:60]))
assert bad <= 2, f"{bad} misaligned spans"; print(f"[1] alignment: {20-bad}/20 spans decode to their sentence")
# ---- 2. pairs
q = build_pairs("base", "cotcontrol", REPO, modes=["uppercase_thinking", "lowercase_thinking", "alternating_case"], per_mode=3) + build_pairs("base", "reasonif", REPO, per_mode=3)
assert q, "no quartets"; print(f"[2] pairs: {len(q)} quartets, conditions {sorted({(x.suite,x.mode) for x in q})}")
for x in q[:3]:
    if x.suite == "cotcontrol": assert grade_cotcontrol(x.mode, x.trace_compliant) and not grade_cotcontrol(x.mode, x.trace_orig)
    assert "Requirement:" not in x.prompt_plain and "following rule" not in x.prompt_plain
print("[2] grader confirms orig fails / transform passes; instruction stripped from plain prompt")
# ---- 3. activations
model, tok2 = load_model(M, dtype=torch.float32, device="cpu"); nL = len(decoder_layers(model)); layers = [nL // 4, nL // 2, 3 * nL // 4]
by = {}
for s in spans: by.setdefault((s.sample_id, s.mode), []).append(s)
mean, last, y = [], [], []
for k, ss in list(by.items())[:12]:
    r = roll[k]; text, off = full_text(tok2, r["prompt"], r["reasoning"], r.get("answer") or "")
    ranges = [token_range(tok2, text, off + s.char_start, s.char_len) for s in ss]
    v = span_vectors(model, tok2, text, ranges, layers, device="cpu"); mean.append(v["mean"]); last.append(v["last"]); y += [s.is_narration for s in ss]
X = torch.cat(mean); Xl = torch.cat(last); y = torch.tensor(y)
assert X.shape == (len(y), len(layers), model.config.hidden_size), X.shape; print(f"[3] span vectors {tuple(X.shape)} (n, layers, d) ({time.time()-t0:.0f}s)")
qv = {k: [] for k in "ABCD"}
for x in q[:2]:
    for k, (pr, tr) in zip("ABCD", ((x.prompt_instr, x.trace_orig), (x.prompt_instr, x.trace_compliant), (x.prompt_plain, x.trace_orig), (x.prompt_plain, x.trace_compliant))):
        text, off = full_text(tok2, pr, tr[:3000]); a_, b_ = token_range(tok2, text, off, len(tr[:3000])); qv[k].append(text_vector(model, tok2, text, layers, span=(a_, b_), device="cpu"))
qv = {k: torch.stack(v) for k, v in qv.items()}; print(f"[3] quartet vectors {tuple(qv['A'].shape)}")
# ---- 4. directions & probe
li = 1; _, unit = mean_diff(X[y, li], X[~y, li]); r = evaluate(unit, X[:, li], y, logistic_probe(X[:, li], y, steps=100))
assert abs(float(unit.norm()) - 1) < 1e-4; print(f"[4] direction unit norm ok; in-sample AUROC dir {r['auroc_direction']:.2f} random {r['auroc_random']:.2f} probe {r['auroc_probe']:.2f} (n {r['n_pos']}+{r['n_neg']}, tiny model, in-sample: sanity only)")
dc = deconfound(qv["A"][:, li], qv["B"][:, li], qv["C"][:, li], qv["D"][:, li]); print(f"[4] deconfound: cos(style, instr+style) {dc['cos_style_vs_instr_style']:.2f}, |style| {dc['norm_style']:.1f}, |resid| {dc['norm_resid']:.1f}")
# ---- 5. steering harness: same prompt, coef 0 vs large coef, greedy-ish via seed
p = [{"sample_id": "t", "mode": "uppercase_thinking", "prompt": roll[list(by)[0]]["prompt"], "meta": {}}]
outs = {}
for c in (0.0, 40.0):
    rs = generate_steered(model, tok2, p, layers[li], unit, c, max_new_tokens=40, batch_size=1, seed=0, model_name="tiny")
    outs[c] = rs[0]; assert set(rs[0]) >= {"sample_id", "mode", "prompt", "reasoning", "answer", "think_status", "completion_tokens", "meta"}
assert outs[0.0]["reasoning"] + outs[0.0]["answer"] != outs[40.0]["reasoning"] + outs[40.0]["answer"], "steering hook had no effect"
print(f"[5] harness: schema ok; coef 0 vs 40 differ; think_status {outs[0.0]['think_status']}/{outs[40.0]['think_status']}; sample: {(outs[0.0]['reasoning'] or outs[0.0]['answer'])[:80]!r}")
print(f"ALL PIECES OK in {time.time()-t0:.0f}s")
