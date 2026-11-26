"""Translate mt_todo.json ([lang, key, text, kind], written by scripts/sft_remarks.py mt-todo) with the repository translator
-> mt_done.json. Gemini (the default): run it anywhere with OPENROUTER_API_KEY set. NLLB (MT_BACKEND=nllb): copy this file,
src/cotctl/sft/translate.py and mt_todo.json into one folder on a machine with a free GPU and run it there with MT_DEVICE=cuda. Texts whose translation fails the guards are listed in mt_failed.json and left out of mt_done.json."""
import sys, json, os, time
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import translate as T
todo = json.load(open(here + "/mt_todo.json")); out = []; t0 = time.time()
for lg in ("es", "fr", "ru", "pl"):
    items = [(x[1], x[2], x[3] if len(x) > 3 else "source") for x in todo if x[0] == lg]
    for i in range(0, len(items), 60):
        part = items[i:i + 60]; tr = T.translate_many([t for _, t, _ in part], lg, protect=True, kinds=[k for _, _, k in part])
        out += [(lg, k, x) for (k, _, _), x in zip(part, tr) if x is not None]
    json.dump(out, open(here + "/mt_done.json", "w"), ensure_ascii=False); print(lg, len(items), f"{time.time() - t0:.0f}s", flush=True)
json.dump(T.FAILED, open(here + "/mt_failed.json", "w"), ensure_ascii=False, indent=0)
print(f"backend {T.BACKEND}: {len(out)} translated, {len(T.FAILED)} rejected by the guards -> mt_failed.json")
