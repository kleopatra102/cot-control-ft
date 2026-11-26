"""Machine translation for language rules. Backend chosen by MT_BACKEND (default gemini since 26 Nov 2026):

  gemini  Gemini 3.8 Flash through OpenRouter (OPENROUTER_API_KEY), told to translate sentence for sentence. Chosen on
          26 Nov 2026 after NLLB changed the meaning in about half of 16 hand-read rows (head-to-head on 40 rows: same length,
          sentence count and hesitation words as NLLB, all 10 known NLLB errors right, one row summarised instead of
          translated). Every output passes guards or is not used (see _ok); a text that fails is left untranslated and its
          row is not built.
  nllb    NLLB-200 1.3B, local (a translation model, not an instructed LLM): the translator of the first builds
          (training files built on 25 Nov 2026); details below. Set MT_BACKEND=nllb to read or reproduce them.
  google  Google Cloud Translation API: not set up yet (needs GOOGLE_APPLICATION_CREDENTIALS); kept as the next option.

The backend is part of the cache key (Translator.VERSION), so translations of different backends never mix.

NLLB details:

- Line structure is kept exactly: each non-empty line is cut into sentences only to fit the model, and rejoined on the same line.
- With protect=True, quoted material, formulas, code, links, hashtags and markers are left untouched: a sentence is cut at
  each protected span, only the text between spans is translated, and the spans are put back unchanged.
- Device: CPU unless MT_DEVICE=cuda. Use a GPU only when no other job is on it.
- Results are cached on disk by (language, text), so a build never translates the same text twice.
"""
from __future__ import annotations
import hashlib, json, os, re
from pathlib import Path
BACKEND = os.environ.get("MT_BACKEND", "gemini")
if BACKEND not in ("nllb", "gemini", "google"): raise SystemExit(f"MT_BACKEND={BACKEND!r}: use nllb, gemini or google")
GEMINI_MODEL = "google/gemini-3.8-flash"
NAME = "facebook/nllb-200-distilled-1.3B"
CODE = {"en": "eng_Latn", "es": "spa_Latn", "fr": "fra_Latn", "ru": "rus_Cyrl", "pl": "pol_Latn"}
_tok = _mod = None; DEV = "cpu"


def _load():
    global _tok, _mod, DEV
    if _mod is None:
        import torch
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        DEV = os.environ.get("MT_DEVICE", "cpu"); torch.set_num_threads(int(os.environ.get("MT_THREADS", "8")))
        _tok = AutoTokenizer.from_pretrained(NAME)
        _mod = AutoModelForSeq2SeqLM.from_pretrained(NAME, torch_dtype=torch.float16 if DEV == "cuda" else torch.float32).to(DEV).eval()


def _batch(sents: list[str], src: str, tgt: str, bs: int | None = None) -> list[str]:
    import torch
    _load(); bs = bs or int(os.environ.get("MT_BS", "8")); _tok.src_lang = CODE[src]
    out = [None] * len(sents); order = sorted(range(len(sents)), key=lambda i: len(sents[i]))
    for i in range(0, len(order), bs):
        idx = order[i:i + bs]; enc = _tok([sents[j] for j in idx], return_tensors="pt", padding=True, truncation=True, max_length=400).to(DEV)
        with torch.no_grad():
            g = _mod.generate(**enc, forced_bos_token_id=_tok.convert_tokens_to_ids(CODE[tgt]), max_new_tokens=int(enc.input_ids.shape[1] * 1.6) + 20, num_beams=2)
        for j, s in zip(idx, _tok.batch_decode(g, skip_special_tokens=True)): out[j] = s
    return out


SPLIT = re.compile(r"(?<=[.!?…][\"'”’)\]])\s+|(?<=[.!?…])\s+")      # sentence ends; does not swallow a closing quote or bracket
SPAN = re.compile("|".join([
    r"https?://\S+|www\.\S+", r"\S+@\S+\.\w+",           # links, addresses
    r"`[^`\n]+`", r"\$[^$\n]+\$", r"\[\[[^\]\n]+\]\]",   # code, formulas in dollars, markers
    r"\"[^\"\n]{1,300}\"", r"“[^”\n]{1,300}”",           # quoted material
    r"(?<!\w)[#@]\w+",                                   # hashtags, mentions
]))
CORE = re.compile(r"[=^²³⁴⁵⁶⁷⁸⁹⁰¹√×÷±≤≥≈≠∑∫π∞]|\d\s*[+*/]\s*\d|\w\(\w*\)")
SIDE = re.compile(r"[-+*/=<>()\d.,%]+|[A-Za-z]|\d+[A-Za-z]{0,2}")


def _math_spans(s: str) -> list[tuple[int, int]]:
    toks = list(re.finditer(r"\S+", s)); out = []; i = 0
    while i < len(toks):
        if CORE.search(toks[i].group(0)):
            a = b = i
            while a > 0 and SIDE.fullmatch(toks[a - 1].group(0).strip(",.;:")): a -= 1
            while b + 1 < len(toks) and (CORE.search(toks[b + 1].group(0)) or SIDE.fullmatch(toks[b + 1].group(0).strip(",.;:"))): b += 1
            end = toks[b].end()
            while end > toks[a].start() and s[end - 1] in ".,;:!?": end -= 1          # leave sentence punctuation outside
            out.append((toks[a].start(), end)); i = b + 1
        else: i += 1
    return out


def spans(s: str) -> list[tuple[int, int]]:
    """Character ranges of s that must not be translated."""
    sp = [(m.start(), m.end()) for m in SPAN.finditer(s)] + _math_spans(s); sp.sort(); out = []
    for a, b in sp:
        if out and a < out[-1][1]: out[-1] = (out[-1][0], max(b, out[-1][1]))
        else: out.append((a, b))
    return out


def _pieces(s: str) -> list[tuple[str, bool]]:
    out = []; p = 0
    for a, b in spans(s):
        if a > p: out.append((s[p:a], False))
        out.append((s[a:b], True)); p = b
    if p < len(s): out.append((s[p:], False))
    return out


LIST_MARK = re.compile(r"(?:\d{1,3}[.)]|\(\d{1,3}\)|[-*•–]+|\(?[a-zA-Z][.)])(?=\s)\s+")     # a list number or bullet at the start of a line


_ABBR = re.compile(r"(?:(?<![^\W\d_])[A-Z]\.|\b(?:Mr|Mrs|Ms|Dr|Prof|St|Jr|Sr|vs|etc|e\.g|i\.e|No|Fig|approx)\.|^\s*\d{1,2}\.)$")


def sentences(text: str) -> list[str]:
    """Cut text at sentence ends, but not after an initial ("J.K."), a common abbreviation ("Dr.", "e.g.") or a list number ("2.")."""
    out = []
    for p in SPLIT.split(text):
        if not p.strip(): continue
        if out and _ABBR.search(out[-1]): out[-1] += " " + p
        else: out.append(p)
    return out


LANG_NAME = {"es": "Spanish", "fr": "French", "ru": "Russian", "pl": "Polish"}
_GEM = ("Translate the following English text into {L}. It is a model's step-by-step reasoning and must stay a faithful translation:\n"
        "- Translate every sentence, in the same order. Do not summarise, shorten, merge, improve, correct or explain anything; keep mistakes, repetitions and false starts.\n"
        "- Keep hesitation and hedging (\"hmm\", \"wait\", \"maybe\", \"I think\", \"actually\") by translating each into its natural {L} equivalent.\n"
        "- Keep every line break and empty line exactly; keep list numbers and bullets at the start of lines as written.\n"
        "- Keep names of products, apps, companies, people, titles of works, code, formulas, URLs and numbers as they are; convert no units.\n"
        "{Q}- Output only the translation, nothing else.\n\nText:\n")
_GEM_Q = {"source": "- Translate quoted material too, unless it is code.\n",
          "remark": "- Text inside double quotation marks is an exact rule string: copy it unchanged, with its quotation marks.\n"}


def _sent_ends(t: str) -> int: return len(re.findall(r"[.!?…](?=\s|$)", t))


def _ok(src: str, out: str, kind: str) -> str:
    """'' if a translation keeps the text, else the reason it is not used."""
    if not out or not out.strip(): return "empty"
    ne = lambda t: [l for l in t.split("\n") if l.strip()]
    if len(ne(out)) != len(ne(src)): return "line count differs"
    if lost_list_marks(src, out): return "list marks lost"
    r = len(out) / max(1, len(src))
    if len(src) >= 200 and r < 0.85: return f"shorter than the source ({r:.2f})"       # the head-to-head: a summary came out at 0.10
    if r > 2.0: return f"much longer than the source ({r:.2f})"
    if _sent_ends(src) >= 5 and _sent_ends(out) < _sent_ends(src) - 2: return "sentences dropped"
    if kind == "remark":
        miss = [q for q in re.findall(r'"[^"\n]{1,80}"', src) if q not in out]
        if miss: return f"rule string changed: {miss[0]}"
    return ""


def _gemini_one(text: str, tgt: str, kind: str) -> tuple[str | None, str]:
    import urllib.request
    last = ""
    for attempt, temp in enumerate((0.0, 0.3, 0.3)):
        body = {"model": GEMINI_MODEL, "temperature": temp, "max_tokens": 16000,
                "messages": [{"role": "user", "content": _GEM.format(L=LANG_NAME[tgt], Q=_GEM_Q[kind]) + text}]}
        for net in range(4):
            try:
                req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                             headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=300) as r: out = (json.loads(r.read())["choices"][0]["message"]["content"] or "").strip("\n")
                break
            except Exception as e:
                import time; out = None; last = f"request failed: {e}"; time.sleep(5 * 2 ** net)
        if out is None: continue
        # keep the source's leading and trailing white space of the whole text
        out = text[:len(text) - len(text.lstrip())] + out.strip() + text[len(text.rstrip()):]
        last = _ok(text, out, kind)
        if not last: return out, ""
    return None, last


FAILED: list[tuple[str, str, str]] = []      # (language, start of text, reason) of the texts a guard rejected


def _gemini_many(texts: list[str], tgt: str, kinds: list[str]) -> list[str | None]:
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(int(os.environ.get("MT_CONCURRENCY", "8"))) as ex:
        res = list(ex.map(lambda tk: _gemini_one(tk[0], tgt, tk[1]), zip(texts, kinds)))
    for t, (o, why) in zip(texts, res):
        if o is None: FAILED.append((tgt, t[:80], why))
    return [o for o, _ in res]


def translate_many(texts: list[str], tgt: str, src: str = "en", protect: bool = True, kinds: list[str] | None = None) -> list[str | None]:
    """kinds (gemini only): "source" for a trace, "remark" for a remark whose rule strings are in double quotes.
    With gemini, None for a text whose translation failed the guards."""
    if BACKEND == "gemini": return _gemini_many(texts, tgt, kinds or ["source"] * len(texts))
    if BACKEND == "google": raise SystemExit("MT_BACKEND=google is not set up yet: it needs a Google Cloud service account (GOOGLE_APPLICATION_CREDENTIALS)")
    return _nllb_many(texts, tgt, src, protect)


def _nllb_many(texts: list[str], tgt: str, src: str = "en", protect: bool = True) -> list[str]:
    """Each non-empty line: protected spans are found on the whole line first (so a quotation that runs over several
    sentences stays whole), then only the text between them is cut into sentences and translated."""
    plan = []; flat = []
    for t in texts:
        ls = []
        for l in t.split("\n"):
            if not l.strip(): ls.append(None); continue
            body = l.strip(); ps = []
            m = LIST_MARK.match(body) if protect else None       # "2. ", "3) ", "- ", "* ": kept as written, the model tends to drop them
            if m and body[m.end():].strip(): ps.append(body[:m.end()]); body = body[m.end():]
            first = True
            for txt, prot in (_pieces(body) if protect else [(body, False)]):
                if prot or not re.search(r"[^\W\d_]{2,}", txt): ps.append(txt); first = first and not txt.strip(); continue        # protected, or nothing to translate
                lead = txt[:len(txt) - len(txt.lstrip())]; trail = txt[len(txt.rstrip()):]; ss = sentences(txt.strip())
                # a piece that continues a sentence after a protected span: the model translates it as if it began a sentence
                cont = (not first) and txt.strip()[:1].islower()
                ps.append((lead, len(flat), len(ss), trail, cont)); flat += ss; first = False
            ls.append((l[:len(l) - len(l.lstrip())], ps))
        plan.append(ls)
    tr = _batch(flat, src, tgt) if flat else []
    def piece(p):
        x = " ".join(tr[p[1]:p[1] + p[2]])
        if p[4] and x[:1].isupper() and not x[1:2].isupper(): x = x[0].lower() + x[1:]       # keep the continuation lower-case
        return p[0] + x + p[3]
    def line(ps): return "".join(p if isinstance(p, str) else piece(p) for p in ps)
    return ["\n".join("" if x is None else x[0] + line(x[1]) for x in ls) for ls in plan]


class Translator:
    """translate(text, lang) with a disk cache keyed by language, protect flag and text."""
    def __init__(self, cache_path: str | Path, protect: bool = True):
        self.path = Path(cache_path); self.protect = protect
        self.cache = json.load(open(self.path)) if self.path.exists() else {}

    VERSION = {"nllb": "v4", "gemini": "g1", "google": "gc1"}[BACKEND]   # g1: Gemini 3.8 Flash, prompt and guards of 26 Nov 2026
    # nllb: v2: spans found per line before sentence splitting; no split after initials and abbreviations.
                        # v3: a piece that continues a sentence after a protected span keeps its lower-case start
                        # v4: a list number or bullet at the start of a line is kept as written

    def key(self, text: str, lang: str) -> str: return f"{lang}:{int(self.protect)}{self.VERSION}:" + hashlib.sha1(text.encode()).hexdigest()

    def many(self, texts: list[str], lang: str) -> list[str]:
        todo = [t for t in dict.fromkeys(texts) if self.key(t, lang) not in self.cache]
        for i in range(0, len(todo), 40):
            part = todo[i:i + 40]
            for t, x in zip(part, translate_many(part, lang, protect=self.protect)):
                if x is not None: self.cache[self.key(t, lang)] = x          # a rejected translation is not cached
            self.path.parent.mkdir(parents=True, exist_ok=True); json.dump(self.cache, open(self.path, "w"), ensure_ascii=False)
        return [self.cache.get(self.key(t, lang)) for t in texts]

    def one(self, text: str, lang: str) -> str: return self.many([text], lang)[0]


def lost_list_marks(source: str, translated: str) -> list[str]:
    """Source lines that start with a list number or bullet whose translated line does not start with the same one (should be empty)."""
    a = [l for l in source.split("\n") if l.strip()]; b = [l for l in translated.split("\n") if l.strip()]
    if len(a) != len(b): return ["line count differs"]
    return [x.strip()[:60] for x, y in zip(a, b) if (lambda m: m and not y.strip().startswith(m.group(0).strip()))(LIST_MARK.match(x.strip()))]
