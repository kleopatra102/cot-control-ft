#!/usr/bin/env python3
"""Generates CONDITIONS_V2.md and its figures from the v2 spec (src/cotctl/v2/spec.py)."""
import sys
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "src"))
from cotctl.v2.spec import *  # noqa: F401,F403
from cotctl.v2.spec import C, FAMS, A_TRAIN_FAMILIES, B_TRAIN_OP, LANG, X, OPS, compatible, reason, role, rule_text, render, TEMPLATES, TRAIN_TEMPLATES, HELDOUT_TEMPLATES, ARMS, K_PER_EXAMPLE, N_PROMPTS_PER_CELL
PH = {"keyword": "{keyword}", "language": "{language}", "N": "{N}", "M": "{M}", "T": "{T}", "W": "{W}"}
SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
TRAIN_C, TEST_C = "#2f6db5", "#eb6834"
plt.rcParams.update({"figure.facecolor": SURF, "font.size": 9, "savefig.dpi": 150, "savefig.facecolor": SURF})

# Fig 1: family x operation grid, the two allocations side by side
fig, axes = plt.subplots(1, 2, figsize=(16, 9))
for ax, arm, ttl in ((axes[0], "A", "Arm A: whole families trained or held out"), (axes[1], "B", "Arm B: one operation per family trained, the other held out")):
    for i, f in enumerate(FAMS):
        ops = list(dict.fromkeys(c[1] for c in C if c[0] == f))
        for j, o in enumerate(ops):
            cs = [c for c in C if c[0] == f and c[1] == o]; r = role(cs[0], arm)
            ax.add_patch(plt.Rectangle((j * 2.05, i - .46), 2.0, .92, facecolor=TRAIN_C if r == "train" else TEST_C, edgecolor=SURF))
            ax.text(j * 2.05 + 1.0, i - .25, o, ha="center", va="center", fontsize=8.5, color="white", fontweight="bold")
            ax.text(j * 2.05 + 1.0, i + .14, "\n".join(c[3] for c in cs), ha="center", va="center", fontsize=7, color="white", linespacing=1.3)
        ax.text(-0.1, i, f, ha="right", va="center", fontsize=8.5, color=INK)
    ax.set_xlim(-2.6, 4.15); ax.set_ylim(len(FAMS) - .5, -.7); ax.axis("off"); ax.set_title(ttl, loc="left", fontsize=10, color=INK)
fig.legend(handles=[Patch(color=TRAIN_C, label="trained (20 conditions)"), Patch(color=TEST_C, label="held out (20 conditions)")],
           loc="lower center", ncol=2, frameon=False, fontsize=9)
fig.suptitle("Condition set v2: 10 families x 2 operations x 2 rules = 40 distinct conditions", x=0.01, ha="left", fontsize=11, color=INK)
fig.tight_layout(rect=(0, 0.04, 1, 0.95)); fig.savefig(REPO / "figures/v2_split_overview.png", bbox_inches="tight"); plt.close(fig)

# Fig 2: every condition, A and B, new / shared-core marked
fig, ax = plt.subplots(figsize=(10, 0.3 * len(C) + 2.2))
prev = None
for i, c in enumerate(C):
    for j, arm in enumerate("AB"):
        r = role(c, arm); ax.add_patch(plt.Rectangle((j - .45, i - .42), .9, .84, facecolor=TRAIN_C if r == "train" else TEST_C, edgecolor=SURF))
        ax.text(j, i, r, ha="center", va="center", fontsize=7, color="white")
    ax.text(-0.6, i, c[3] + ("   [new]" if c[4] == "new" else ""), ha="right", va="center", fontsize=7.6, color=INK if c[4] == "new" else INK2)
    ax.text(-4.0, i, c[1], ha="left", va="center", fontsize=7, color=MUTED)
    if c[2] in CORE: ax.text(1.6, i, "shared core", va="center", fontsize=7, color=TEST_C)
    if c[0] != prev:
        ax.text(-6.4, i, c[0], ha="left", va="center", fontsize=8.5, color=INK, fontweight="bold")
        if prev is not None: ax.axhline(i - .5, color=GRID, lw=1)
        prev = c[0]
ax.set_xlim(-6.45, 2.5); ax.set_ylim(len(C) - .5, -1.3); ax.axis("off")
for j, arm in enumerate(("A", "B")): ax.text(j, -1.0, arm, ha="center", fontsize=10, color=INK)
ax.text(-4.0, -1.0, "operation", fontsize=8, color=MUTED)
fig.suptitle(f"All 40 conditions ({sum(c[4] == 'new' for c in C)} new); shared core = held out in both arms ({len(CORE)})", x=0.02, ha="left", fontsize=10.5, color=INK)
fig.tight_layout(); fig.savefig(REPO / "figures/v2_conditions.png", bbox_inches="tight"); plt.close(fig)

# Fig 3: language interactions
LC = {"ok": ("#2f6db5", "combinable"), "localise": ("#7fa6d6", "combinable once translated"), "multi": ("#5b8fc9", "combinable with a multilingual grader"), "fixgrader": ("#b9a2d6", "combinable after grader fix"),
      "conflict": ("#c3c2b7", "never combined: needs English"), "side": ("#eb6834", "never combined: language skews it")}
rows = [c for c in C if c[2] in LANG]
fig, ax = plt.subplots(figsize=(10, 0.29 * len(rows) + 1.8))
prev = None
for i, c in enumerate(rows):
    st_, note = LANG[c[2]]
    ax.add_patch(plt.Rectangle((-.45, i - .42), 2.9, .84, facecolor=LC[st_][0], edgecolor=SURF))
    ax.text(1.0, i, LC[st_][1], ha="center", va="center", fontsize=7.2, color="white" if st_ in ("ok", "side", "multi") else INK)
    ax.text(-0.6, i, c[3], ha="right", va="center", fontsize=7.6, color=INK2)
    if c[0] != prev:
        ax.text(-5.2, i, c[0], ha="left", va="center", fontsize=8.2, color=INK, fontweight="bold")
        if prev is not None: ax.axhline(i - .5, color=GRID, lw=1)
        prev = c[0]
ax.set_xlim(-5.25, 2.6); ax.set_ylim(len(rows) - .5, -1.1); ax.axis("off")
ax.text(1.0, -0.9, "with 'reason in a given language' (fr, es, ru, pl)", ha="center", fontsize=8.5, color=INK)
cnt = {k: sum(v[0] == k for v in LANG.values()) for k in LC}
fig.suptitle(f"'Reason in a given language' against every other rule: {cnt['ok'] + cnt['localise'] + cnt['multi'] + cnt['fixgrader']} combinable, "
             f"{cnt["side"]} skewed by the language, {cnt['conflict']} needs English", x=0.02, ha="left", fontsize=10.5, color=INK)
fig.tight_layout(); fig.savefig(REPO / "figures/v2_language_interactions.png", bbox_inches="tight"); plt.close(fig)

# Fig 4: compatibility matrix + feasibility of 7-condition examples per arm
import itertools
ids = [c[2] for c in C]
RC = {"ok": "#ffffff", "same operation": "#c3c2b7", "contradiction": "#eb6834", "format": "#f2b392", "feasibility": "#e9d36b", "language": "#2f6db5"}
fig, ax = plt.subplots(figsize=(13, 12.4))
for i, a in enumerate(ids):
    for j, b in enumerate(ids):
        r = "same operation" if a == b else reason(a, b)
        ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1, facecolor=RC[r], edgecolor=GRID, lw=0.4))
names = [c[3] for c in C]
ax.set_xticks(range(40)); ax.set_xticklabels(names, rotation=90, fontsize=6.3); ax.set_yticks(range(40)); ax.set_yticklabels(names, fontsize=6.3)
ax.set_xlim(-.5, 39.5); ax.set_ylim(39.5, -.5); ax.tick_params(length=0)
for k in range(0, 41, 4): ax.axhline(k - .5, color=INK2, lw=0.8); ax.axvline(k - .5, color=INK2, lw=0.8)
for k, f in enumerate(FAMS): ax.text(40.2, 4 * k + 1.5, f, va="center", fontsize=7.5, color=INK)
ax.legend(handles=[Patch(facecolor=RC[k], edgecolor=GRID, label=("can be combined" if k == "ok" else f"cannot: {k}")) for k in RC],
          loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=3, frameon=False, fontsize=8.5)
n_ok = sum(compatible(a, b) for a, b in itertools.combinations(ids, 2))
ax.set_title(f"Which conditions can share a training example: {n_ok} of 780 pairs allowed", loc="left", fontsize=11, color=INK)
fig.tight_layout(); fig.savefig(REPO / "figures/v2_compatibility.png", bbox_inches="tight"); plt.close(fig)


def max_clique_with(c0, pool, k):
    """Is there a k-set of mutually compatible conditions from `pool` that contains c0? (exhaustive; pool is 20)"""
    nb = [x for x in pool if x != c0 and compatible(c0, x)]
    def ext(chosen, cand, need):
        if need == 0: return True
        for i, x in enumerate(cand):
            if all(compatible(x, y) for y in chosen) and ext(chosen + [x], cand[i + 1:], need - 1): return True
        return False
    return ext([c0], nb, k - 1)
FEAS = {}
for arm in "AB":
    pool = [c[2] for c in C if role(c, arm) == "train"]
    FEAS[arm] = {c0: max(k for k in range(1, 9) if k == 1 or max_clique_with(c0, pool, k)) for c0 in pool}
print("max example size per training condition:", {arm: min(v.values()) for arm, v in FEAS.items()})


# Templates and experiment sections (built from the spec at generation time)
_ex_rule = rule_text("all_caps")
_tpl_rows = "\n".join(f"| **{t}** {v['name']} | {'train' if v['train'] else '**held out**'} | {v['what']} |" for t, v in TEMPLATES.items())
_rendered = []
for _t in TEMPLATES:
    _d, _u = render(_t, [_ex_rule], "{question}")
    _block = (f"developer: {_d}\nuser:      " + _u.replace("\n", "\n           ")) if _d else _u
    _rendered.append(f"**{_t}, {TEMPLATES[_t]['name']}**\n```\n{_block}\n```")
_multi = render("T6", [rule_text("all_caps"), rule_text("no_commas")], "{question}")[1]
TPL_SECTION = f"""## Prompt templates

Each rule is inserted into a prompt template with two placeholders, `{{rule}}` and `{{question}}`. **No template uses
answer tags** (no `<answer>`). gpt-oss separates reasoning from the answer natively (its *analysis* and *final*
channels), so a template only has to say that the rule applies to the reasoning. The six templates vary along
different dimensions:

| template | role in training | what is distinctive |
|---|---|---|
{_tpl_rows}

T1-T3 are used in training, mixed evenly across examples. T4-T6 are never seen in training. Each varies something
new:
- T4: where the rule sits (the developer role, which gpt-oss reads as instructions);
- T5: register (casual);
- T6: layout (a numbered instruction list).

Rendered with the rule "{_ex_rule}":

{chr(10).join(_rendered)}

**With several rules (training examples have {K_PER_EXAMPLE}):**
- T1 bolds each rule.
- T2 and T3 list them after the label, and T2's closing sentence becomes plural.
- T4 puts them all in the developer message.
- T6 numbers them, followed by the "give your final answer" item. For example:

```
{_multi}
```

## The gpt-oss-20b experiment

Two kinds of transfer are tested at once: to **rules** the model never trained on, and to **templates** it never saw.
Every model is scored on all 40 rules x 6 templates, with {N_PROMPTS_PER_CELL} prompts per cell
({40 * 6 * N_PROMPTS_PER_CELL} prompts per model). Each rule x template cell falls into one of four kinds:

| | template seen in training (T1-T3) | template held out (T4-T6) |
|---|---|---|
| **rule trained** | in-distribution | template transfer |
| **rule held out** | rule transfer | rule + template transfer (hardest) |

**Models:**

| model | training rules | training templates | question it answers |
|---|---|---|---|
| base gpt-oss-20b | none | none | reference |
| **A** | A's 20 (split by family) | T1, T2, T3 mixed | rule and template transfer |
| **B** | B's 20 (split within family) | T1, T2, T3 mixed | the same for the within-family split |
| **A1** | A's 20, the same examples as A | **T1 only** | does template variety in training drive template transfer? (A against A1) |

**Setup:**
- {K_PER_EXAMPLE} rules per training example and about 920 examples per arm, built from the same gpt-oss stage-1
  traces as earlier runs. A1 uses exactly A's traces with the prompts re-rendered in T1.
- Attention-only LoRA, one epoch, medium reasoning effort; the same recipe as earlier gpt-oss runs.

**Evaluation questions:**
- Drawn from Redwood's held-out task pool (GSM8K, MATH, ARC, OpenBookQA, MMLU-Pro), excluding any question that
  appears in the training traces.
- The same {N_PROMPTS_PER_CELL} questions are used across templates and models for a given rule.
- Number-notation rules use only numeric questions.
- Answer accuracy is scored on the final channel.

**Checks before and during the run** (findings go into a running issues log in the findings document):
1. **Side-effect audit before training.** Every held-out rule's grader is run on each arm's finished training traces
   and on base traces. A rule that passes at least 10 points more often on the training traces is re-paired before
   training.
2. **Template leakage.** Grep the training prompts for each held-out template's distinctive phrases.
3. **Question overlap.** No evaluation question may appear in training.
4. **Reading outputs.** For passing held-out cells, sample traces and check the pass is genuine: not restating the
   rule, not a side effect such as shortness, and not concentrated on easy question types. The rate at which the
   reasoning restates the rule is logged for every cell.
5. **Calibration.** Thresholds (word caps, stop-word share, average word length) are set from base traces before
   training. Any cell where base passes at least 20 % is reported separately.
6. **Judge checks.** Read 20 judged traces per LLM-judged rule and agree or disagree with each verdict.

"""

# Markdown
L = ["""# Condition set v2: 40 distinct rules for reasoning control

> **Status (2026-10-03).** The rule set, split, compatibility list and graders are final. The leakage audit of arm A's
> training set found no held-out rule passing more often on training traces than on base traces, and no held-out
> template wording in any training prompt. The final A and B training sets, rebuilt with the length gate, are being
> audited; this document will be updated with the result.

*Proposal, 2026-10-03. Generated by `scripts/conditions_v2.py`, which is the single source of truth for the set; edit
it there. It replaces the 49-condition v1 registry (`CONDITION_SPLIT.md`), which had reworded duplicates, unequal
families and two kinds of train-to-test leakage. Not yet implemented in the training pipeline.*

## At a glance

![Split overview](figures/v2_split_overview.png)

- **40 conditions, one per distinct rule.** Wherever two benchmarks asked for the same thing (all caps, no commas,
  a word budget, a banned word), the copies are merged into one condition with a single canonical wording. The
  merged sources are listed in the catalogue.
- **10 families of exactly 4.** Each family has 2 operations with 2 rules each. An operation is a mechanism, for
  example "uniform case" or "every sentence". Its two rules are distinct (neither satisfies the other), but they
  share the mechanism.
- **One wording style.** Every rule is a bare imperative ("Write entirely in capital letters."). The prompt
  template adds the framing that the rule applies to the reasoning, and that framing differs between templates (see
  "Prompt templates"). This removes the v1 confound where a rule's wording revealed which benchmark it came from.
- **Diverse by design.** The families cover case, banned material, required material, positions, word-level
  layout, document structure, style and persona, length, language and notation, and letter-level and lexical
  statistics. Of the 40 conditions, NNEW are new; 8 v1 rules were dropped, and many more merged.

## Allocation

- **A (split by family):** trains 5 whole families (Case, Bans, Inclusion, Position, Language & notation) and holds
  out the other 5 (Word layout, Structure, Style, Length, Letter & lexical statistics).
- **B (split within family):** in every family, trains one operation and holds out the other.
- **Length is never trained as a total-word cap.** A holds the whole Length family out. B trains only sentence shape
  (every sentence at least 20 words; at most 12 words per sentence), rewritten by merging or splitting sentences
  without cutting content, and holds out total word count. This removes v1's largest side-effect channel: short or
  long training traces satisfying other rules (simple words, low stop-word share, "at least N" counts).
- **Length can also shift as a side effect of non-length rules.** For example, the stop-word rule removes words by
  definition, and "meow" doubles the word count. The audit therefore measures, for every training rule, how much it
  changes trace length relative to base (see "How leakage is avoided"). A first draft had "exactly five sentences"
  in B's training rules. That is short by definition (about 100 words against a 200-word median), so it was replaced
  by "every sentence at least 20 words".

Each arm trains 20 conditions and holds out 20. The 10 conditions held out by both arms form the **shared core**,
which gives the direct A-against-B comparison.

![Every condition](figures/v2_conditions.png)
"""]
L.append("| family | operation | condition | A | B | new? |\n|---|---|---|---|---|---|")
for c in C:
    L.append(f"| {c[0]} | {c[1]} | {c[3]} | {role(c, 'A')} | {role(c, 'B')}{' (core)' if c[2] in CORE else ''} | {'new' if c[4] == 'new' else ''} |")
L.append("""
## How leakage is avoided

In v1, some held-out rules were satisfied as a side effect of how other rules' training traces were rewritten (for
example, B's stop-word rewrite deleted "the" and "so", which leaked into the held-out word bans). v2 handles this in
four ways:

1. **No total-length training** (see Allocation). Length changes were behind most v1 side effects.
2. **Pairing choices.** Where one rule's rewrite would satisfy another, the two share an operation, or the held-out
   one was replaced. A first draft of v2 had three such problems, now fixed:
   - "no apostrophes" (the no-first-person rewrite removes let's, I'm and we're) was replaced by "no parentheses or
     brackets". Calibration later showed that base gpt-oss already passes that 47 % of the time, so it became "no
     colons" (3.4 %);
   - "explain to a young child" (rewarded the short sentences that length training produces) was replaced by
     "pirate speak";
   - the alphabetical acrostic (controls sentence-initial words, like Position's "start every sentence with a word")
     was replaced by "no word longer than 8 letters".

   In B, Inclusion now trains word classes and holds out required words, because long traces would satisfy "use all 7
   conjunctions" or "4 transition words" but not a marker or an exact count.
3. **Rewrites must not touch anything they are not asked to.** No fixed words are inserted at sentence starts except
   by the sentence-start rule. The "exactly twice" word is "crucially", inserted mid-sentence. The end-of-sentence
   rewrite keeps the original line breaks; v1's version put every sentence on its own line, which would have leaked
   into "one sentence per line".
4. **A leakage audit before training.** For every held-out condition, its grader is run on the arm's finished
   training traces and on the base traces.
   - If the training traces pass it at least 10 points more often than the base traces, the pairing is changed
     before training.
   - This measures leakage instead of arguing about it.

**First in line for the audit** (plausible small effects):
- A trains no-first-person, which removes pronouns (stop words), and holds out stop words and average word length.
- A trains numbers in words, which adds words such as "fifteen", and holds out the lexical statistics.
- B trains stop words and average word length, which naively shorten traces (the first pilot cut traces by about
  half). Swapping B's two statistics operations was tried and rejected: the rewriting model could not produce "no two
  adjacent words with the same first letter" (0 of 53 attempts). B therefore keeps lexical density, rewritten by
  rephrasing rather than deleting words, and held to the length gate below.
- **Length check:** for every training rule, the median word count of training traces containing it is compared with
  base traces of the same questions. A shift of more than 15 % is flagged.

## Build process and length control

Each training example takes a base gpt-oss reasoning trace and turns it into one that satisfies its 7 rules:
1. **One LLM rewrite** (gpt-4.1, T = 0) for the content rules: language, bans, inclusions, style, sentence shape,
   number notation, lexical density. It is skipped when no content rule is drawn.
2. **Mechanical edits in code** for the rest: case, fixed phrases, end/start tokens, markers, markup, per-word
   insertion, sentence splitting, ratio fix.
3. **Every rule checked by its evaluation grader;** an LLM judge for questions and the opening summary.
4. **The length gate.** The finished trace must be within 0.8× - 10 words and 1.3× + 25 words of the base trace
   ("meow" excepted, since it doubles words by design). The rewrite is also told the original's word count and a
   target range.

A failing example is redrawn with a fresh set of rules, up to 5 times.

**Why the gate exists.** The audit of the first full build found that the LLM rewrite pulled every trace towards
about 150-300 words. It inflated short traces about 1.6× and halved long ones, which made A's training traces 21 %
longer than base on average. That would have taught "write more" on top of the rules and biased the held-out word
caps. A vague "keep the length" instruction did not help; an explicit word-count target plus the gate did.

## Calibration (before any training)

**gpt-oss-20b values** (from 937 base traces; median trace 203 words): N = 82 words, M = 423 words, stop words
T = 22.9 %, average word length W = 5.6 letters. Each puts base at about 10 %.

Several rules have a threshold (word caps, stop-word share, average word length) that base models can already pass
at a fixed value. For example, base Qwen3.8 and gpt-oss pass "stop words at most 35 %" on 80 % of prompts.
Each threshold is set per model from base traces so that base passes about 5-15 %. ReasonIF's word budgets were
already calibrated this way.

Every held-out condition is also checked for its base pass rate. Any condition above about 20 % on a model is
reported separately, as in v1.

## Language rules against every other rule

![Language interactions](figures/v2_language_interactions.png)

The language family has two natural-language rules:
- **"Reason in a given language"** (French, Spanish, Russian or Polish) writes the whole trace in that language.
- **"Opening summary in a given language"** writes one sentence in that language and the rest in English.

**Given language.** Many graders are defined on English word lists. If they stayed English-only, a Spanish trace
would pass the stop-word limit, the first-person ban and the keyword ban automatically, because it contains none of
the English words. It would also fail the inclusion rules automatically. v2 therefore uses **multilingual graders**:
each such rule is checked against the word list of the trace's own language. The lists are:
- stop words and first-person pronouns per language (standard lists);
- the banned keyword, "crucially" and "Indeed" translated;
- each language's coordinating conjunctions and transition words;
- number words via `num2words`.

With these graders the language does not decide the outcome, so these rules can share an example with a given
language. Each other rule then falls into one of six cases:

- **Combinable:** no interaction.
- **Combinable with a multilingual grader:** the rule uses a word list, and the trace language's list is used.
- **Combinable once translated:** the rule has a fixed string, and translations already exist (end phrase, end word)
  or are trivial (start sentence).
- **Combinable after a grader fix:** the alternating-case graders only looked at a-z, so Cyrillic words passed for
  free. They become Unicode-aware.
- **Never combined: the language skews it.** Its threshold depends on the language, and translation does not fix
  that: average word length (Russian and Polish words are longer) and the two word caps (calibrated on English word
  counts).
- **Never combined: needs English.** Pirate speak is an English dialect.

**Every grader also checks that the trace is in the requested language:** English unless a given language was
requested. A model that drifts into another language at test time fails these rules instead of passing them.

**Opening summary.** The trace stays English apart from one sentence, so the English graders apply and nearly
everything combines with it. Its only conflicts are with the two rules that also fix the first sentence: the start
sentence and "start every sentence with 'Indeed'".

LANG_TABLE

## Which conditions can be combined in one training example

![Compatibility matrix](figures/v2_compatibility.png)

This matrix is the complete rule: any two conditions may share a training example unless their cell is coloured.
It is generated from one list in `scripts/conditions_v2.py`, and the training sampler will read the same list. There
are five reasons two conditions cannot be combined:

| reason | meaning | example |
|---|---|---|
| **same operation** | two rules of one operation never share an example | all caps and all lowercase |
| **contradiction** | both cannot hold at once | no brackets and [[NOTE]]; Roman numerals and all lowercase |
| **format** | they break each other's format or exact strings | square brackets around every word and the end phrase |
| **feasibility** | both can technically hold, but the rewrite would mangle the reasoning | at most N words and all 7 conjunctions |
| **language** | see the language table above | a given language and the stop-word limit |

**Feasibility check.** For every training condition, the script computes the largest fully compatible set of
training conditions that contains it.

FEAS_TABLE

**Every training example has 7 conditions.** With multilingual graders and the opening-summary rule, every training
condition in both arms fits into a fully compatible example of at least 7, which the table above confirms. In an
earlier draft the two language rules capped out at 5: "reason in a given language" was excluded from every
English-word-list rule, and "alternate English and Spanish" could not combine with them at all.

**Known difference from Q5.** Q5 used 5 conditions per example, and the v2 arms use 7. A v2 arm therefore differs
from Q5 both in which rules it trains and in how many rules each example combines, as in v1. The A-against-B
comparison is unaffected: both arms use 7.

### Per condition: what it can never be combined with

COMPAT_LIST

TPL_SECTION_HERE
## Condition catalogue

Each entry lists:
- the proposed prompt wording;
- what the grader checks, precisely;
- a short compliant example;
- which v1 conditions it merges.
""")
for f in FAMS:
    L.append(f"\n### {f}\n")
    for o in dict.fromkeys(c[1] for c in C if c[0] == f):
        L.append(f"**Operation: {o}** (A: {role([c for c in C if c[0] == f and c[1] == o][0], 'A')}, B: {role([c for c in C if c[0] == f and c[1] == o][0], 'B')})\n")
        for c in [c for c in C if c[0] == f and c[1] == o]:
            L.append(f"- **{c[3]}** (`{c[2]}`){' **NEW**' if c[4] == 'new' else ''}")
            L.append(f"  - *Rule text:* {rule_text(c[2], PH)}")
            L.append(f"  - *Grader:* {c[6]}")
            L.append(f"  - *Example:* `{c[7]}`")
            L.append(f"  - *Source:* {c[4]}" + (f". {c[8]}" if c[8] else ""))
        L.append("")
L.append("""
## What changed from v1

- **Merged:**
  - all caps (3 copies);
  - all lowercase (2);
  - word budget and word caps (5);
  - word bans (5);
  - no commas (2);
  - end-of-sentence word and emoji at end (3);
  - given language (2);
  - include word or marker (3);
  - bullets with numbered list.
- **Dropped from v1:**
  - Redwood's title case (all-caps text passes it);
  - CoTControl's repeat-at-start-and-end and IFBench's first word = last word (combinations of the start and end
    rules);
  - second person (it satisfies the no-first-person ban);
  - "no word more than 10 times" (any short trace passes it);
  - child-style explanation (length side effect);
  - Given/Work/Check sections (base Qwen3.8 passes 86 %);
  - ignore-question (needs a judge with no fixed criterion).
- **New (NEWLIST_N):** NEWLIST.
- **Adapted from v1:**
  - all 7 conjunctions instead of 6 of 7;
  - "use a word exactly twice" with "crucially" instead of "hence";
  - the start sentence without "me";
  - "no first person", which was a Redwood validation instruction never trained or tested in v1.
- **Graders:**
  - reused from v1 where the rule existed;
  - new rules need new graders, each a few lines;
  - pirate speak, the sports commentator, questions and the opening summary use an LLM judge (gpt-4.1, T=0);
  - word-list rules are multilingual (stop words, pronouns, keyword, conjunctions, transition words, "crucially",
    "Indeed", number words), so they can be combined with a given language;
  - number-notation rules are evaluated only on questions that involve numbers.
- **Evaluation:** every condition is evaluated in all six prompt templates on one question pool (see "Prompt
  templates" and "The gpt-oss-20b experiment").
""")
_new = [c[3].lower() for c in C if c[4] == "new"]
_cl = []
for c in C:
    bad = [(b[3], reason(c[2], b[2])) for b in C if b[2] != c[2] and not compatible(c[2], b[2])]
    _cl.append(f"- **{c[3]}** ({len(C) - 1 - len(bad)} of 39 allowed). Never with: " + "; ".join(f"{n} ({r})" for n, r in bad) + ".")
_name = {c[2]: c[3] for c in C}
_ft = "| arm | largest compatible example | conditions limited below 7 |\n|---|---|---|\n" + "\n".join(
    f"| {arm} | {'8 or more (the search stops at 8)' if min(FEAS[arm].values()) >= 8 else f'{min(FEAS[arm].values())} to {max(FEAS[arm].values())}'} conditions | " + (", ".join(f"{_name[k]} ({v})" for k, v in FEAS[arm].items() if v < 7) or "none") + " |" for arm in "AB")
L = [x.replace("COMPAT_LIST", "\n".join(_cl)).replace("FEAS_TABLE", _ft) for x in L]
_lt = "| rule | with a language rule | why |\n|---|---|---|\n" + "\n".join(f"| {c[3]} | {LC[LANG[c[2]][0]][1]} | {LANG[c[2]][1]} |" for c in C if c[2] in LANG)
L = [x.replace("LANG_TABLE", _lt) for x in L]
L = [x.replace("TPL_SECTION_HERE", TPL_SECTION) for x in L]
(REPO / "CONDITIONS_V2.md").write_text("\n".join(L).replace("NNEW", str(len(_new))).replace("NEWLIST_N", str(len(_new))).replace("NEWLIST", ", ".join(_new)))
print("40 conditions;", sum(c[4] == "new" for c in C), "new; core", len(CORE))

