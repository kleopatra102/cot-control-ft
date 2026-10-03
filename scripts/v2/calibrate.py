#!/usr/bin/env python3
"""Calibrate the v2 thresholds on a model's base reasoning traces (no rule in the prompt), so that base passes ~10 %:
N = 10th percentile of word count (at most N words), M = 90th percentile (at least M), T = 10th percentile of the
English stop-word share, W = 90th percentile of mean word length. Also reports every programmatic rule's base pass rate.

    python scripts/v2/calibrate.py --traces results/gptoss/sft/stage1_rollouts.jsonl --out data/v2_thresholds_gpt-oss-20b.json
"""
import argparse, json, re, sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from cotctl.third_party.redwood import instructions as RW
from cotctl.v2 import lexicon as LX
from cotctl.v2.graders import grade, _WORD, _words, JUDGED
from cotctl.v2.spec import C

ap = argparse.ArgumentParser(); ap.add_argument("--traces", required=True); ap.add_argument("--out", required=True); a = ap.parse_args()
rs = [json.loads(l) for l in open(a.traces)]
tx = [r["reasoning"] for r in rs if r.get("think_status") == "ok" and (r.get("reasoning") or "").strip()]
wc = np.array([RW.word_count(t) for t in tx])
sw = np.array([(lambda ws: sum(w in LX.stop_words("en") for w in ws) / max(1, len(ws)))([w.lower() for w in _WORD.findall(t)]) for t in tx])
ml = np.array([(lambda ws: sum(map(len, ws)) / max(1, len(ws)))(_words(t)) for t in tx])
th = {"N": int(np.percentile(wc, 10)), "M": int(np.percentile(wc, 90)), "T": round(float(np.percentile(sw, 10)), 3), "W": round(float(np.percentile(ml, 90)), 2),
      "n_traces": len(tx), "source": a.traces, "word_count_median": int(np.median(wc)), "stop_share_median": round(float(np.median(sw)), 3), "mean_word_len_median": round(float(np.median(ml)), 2)}
json.dump(th, open(a.out, "w"), indent=1); print(th)
args = {"language": "en", "keyword": "zzzz", **{k: th[k] for k in "NMTW"}}
rates = {c[2]: round(100 * sum(bool(grade(c[2], t, args)) for t in tx) / len(tx), 1) for c in C if c[2] not in JUDGED and c[2] not in ("ban_keyword",)}
print("base pass rate on unconstrained traces (%):"); print({k: v for k, v in sorted(rates.items(), key=lambda kv: -kv[1])})
