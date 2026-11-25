"""Translate mt_todo.json ([lang, key, text], written by scripts/sft_remarks.py mt-todo) with the repository translator, protected spans
left untouched -> mt_done.json. Copy this file, src/cotctl/sft/translate.py and mt_todo.json into one folder on a machine with a free
GPU and run it there with MT_DEVICE=cuda; it needs no other part of the repository."""
import sys, json, os, time
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import translate as T
todo = json.load(open(here + "/mt_todo.json")); out = []; t0 = time.time()
for lg in ("es", "fr", "ru", "pl"):
    items = [(k, t) for l, k, t in todo if l == lg]
    for i in range(0, len(items), 60):
        part = items[i:i + 60]; tr = T.translate_many([t for _, t in part], lg, protect=True); out += [(lg, k, x) for (k, _), x in zip(part, tr)]
    json.dump(out, open(here + "/mt_done.json", "w"), ensure_ascii=False); print(lg, len(items), f"{time.time() - t0:.0f}s", flush=True)
