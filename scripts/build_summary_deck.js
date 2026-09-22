const pptxgen = require("pptxgenjs");
const path = require("path");
const FIG = "/home/ola/dev/cot-control-ft/figures/";
const OUT = "/home/ola/dev/cot-control-ft/META_DISCUSSION_SUMMARY.pptx";

const NAVY = "104281", BLUE = "2A78D6", LIGHT = "86B6EF", INK = "0B0B0B", INK2 = "52514E", MUTED = "898781", GRID = "E1E0D9", WHITE = "FFFFFF", ORANGE = "EB6834", TINT = "EEF4FC";
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625
pres.author = "Ola";
const F = "Calibri";

function title(slide, text, sub) {
  slide.addText(text, { x: 0.5, y: 0.28, w: 9.0, h: 0.55, fontFace: F, fontSize: 22, bold: true, color: INK, isTextBox: true, margin: 0, fit: "shrink" });
  if (sub) slide.addText(sub, { x: 0.5, y: 0.82, w: 9.0, h: 0.45, fontFace: F, fontSize: 12, color: INK2, isTextBox: true, margin: 0, valign: "top" });
}
function footer(slide, text) {
  slide.addText(text, { x: 0.5, y: 5.15, w: 9.0, h: 0.4, fontFace: F, fontSize: 8.5, color: MUTED, isTextBox: true, margin: 0, valign: "top" });
}
function stat(slide, x, y, w, big, small) {
  slide.addShape(pres.ShapeType.roundRect, { x, y, w, h: 1.05, fill: { color: TINT }, line: { color: TINT }, rectRadius: 0.08 });
  slide.addText(big, { x: x + 0.15, y: y + 0.08, w: w - 0.3, h: 0.5, fontFace: F, fontSize: 26, bold: true, color: NAVY, isTextBox: true, margin: 0 });
  slide.addText(small, { x: x + 0.15, y: y + 0.55, w: w - 0.3, h: 0.45, fontFace: F, fontSize: 10.5, color: INK2, isTextBox: true, margin: 0, valign: "top" });
}
function bullets(slide, items, x, y, w, h, size = 13) {
  slide.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 6 } })),
    { x, y, w, h, fontFace: F, fontSize: size, color: INK, isTextBox: true, valign: "top", margin: 0 });
}
function fig(slide, name, x, y, w, h) { slide.addImage({ path: FIG + name, x, y, w, h, sizing: { type: "contain", w, h } }); }

// 1 title (dark)
{
  const s = pres.addSlide(); s.background = { color: NAVY };
  s.addText("Meta-discussion in a model's chain of thought", { x: 0.6, y: 1.3, w: 8.8, h: 1.3, fontFace: F, fontSize: 34, bold: true, color: WHITE, isTextBox: true, margin: 0 });
  s.addText("How much is there, does it matter, and can it be reduced?", { x: 0.6, y: 2.7, w: 8.8, h: 0.5, fontFace: F, fontSize: 18, color: "CADCFC", isTextBox: true, margin: 0 });
  s.addText("Qwen3.5-9B · CoTControl + ReasonIF · measurement, SFT, strip test, activation steering", { x: 0.6, y: 3.35, w: 8.8, h: 0.4, fontFace: F, fontSize: 12, color: "CADCFC", isTextBox: true, margin: 0 });
  s.addText("Ola · SPAR · replication of METR's CoT-controllability fine-tuning experiments · September 2026", { x: 0.6, y: 4.8, w: 8.8, h: 0.35, fontFace: F, fontSize: 11, color: LIGHT, isTextBox: true, margin: 0 });
}
// 2 what & why
{
  const s = pres.addSlide(); title(s, "What is meta-discussion, and why care?", "The model narrating its formatting constraint inside its own reasoning");
  s.addShape(pres.ShapeType.roundRect, { x: 0.5, y: 1.4, w: 4.4, h: 2.3, fill: { color: TINT }, line: { color: TINT }, rectRadius: 0.08 });
  s.addText([
    { text: "“Constraint 1: Do not use the word 'octane' in the reasoning stage.”", options: { breakLine: true, italic: true } },
    { text: "“I must use only uppercase letters in the reasoning stage.”", options: { breakLine: true, italic: true } },
    { text: "“Did I use the word 'LCM' anywhere? Let me check.”", options: { italic: true } },
  ], { x: 0.7, y: 1.55, w: 4.0, h: 2.0, fontFace: F, fontSize: 13, color: NAVY, isTextBox: true, valign: "top", margin: 0, paraSpaceAfter: 10 });
  s.addText("Real sentences from Qwen3.5-9B traces, labelled by a full-trace LLM lister", { x: 0.5, y: 3.75, w: 4.4, h: 0.5, fontFace: F, fontSize: 10, color: MUTED, isTextBox: true, margin: 0 });
  s.addText("Why it matters", { x: 5.3, y: 1.4, w: 4.2, h: 0.35, fontFace: F, fontSize: 15, bold: true, color: INK, isTextBox: true, margin: 0 });
  bullets(s, [
    "A narration sentence in prose can itself break the constraint it describes",
    "CoTControl prompts explicitly forbid it; ReasonIF prompts do not",
    "It changes what a CoT monitor sees: a trace that announces its rule is a different object from one that silently follows it",
    "Question for control: if we remove it, does compliance rise?",
  ], 5.3, 1.8, 4.2, 2.6, 12.5);
  s.addText("Five questions:  1 how much?  ·  2 does it violate?  ·  3 how to reduce?  ·  4 steering  ·  5 the ceiling", { x: 0.5, y: 4.55, w: 9.0, h: 0.4, fontFace: F, fontSize: 12, bold: true, color: BLUE, isTextBox: true, margin: 0 });
}
// 3 Q1 how much
{
  const s = pres.addSlide(); title(s, "1 · Does it happen a lot?  Yes: 9 of 10 CoTControl traces", "Same rollouts, three measures; the full-trace LLM lister is the reference");
  fig(s, "llm_three_measures.png", 0.4, 1.3, 6.1, 2.45);
  stat(s, 6.8, 1.35, 2.7, "89 %", "of base CoTControl traces narrate (lister); 74 % on ReasonIF");
  stat(s, 6.8, 2.5, 2.7, "22.7", "narration sentences per trace, 6.7 % of the text");
  bullets(s, [
    "METR's regex over-counts: bare “constraint” fires on “environmental constraints”",
    "The paper's judge under-counts: it reads only the first 10,000 characters and 97 % of traces are longer",
  ], 0.5, 3.9, 9.0, 1.2, 12);
  footer(s, "META_DISCUSSION_FULLTRACE.md §2 · gpt-5-mini lister, every narration sentence, no cap · base n = 2,594 CoTControl, 262 ReasonIF");
}
// 3b sentence-level disagreement
{
  const s = pres.addSlide(); title(s, "1 · The two detectors mostly flag different sentences", "Sentences flagged by METR's regex and/or the full-trace LLM lister, base and step-60");
  fig(s, "llm_sentence_overlap.png", 0.4, 1.3, 6.0, 2.05);
  stat(s, 6.7, 1.35, 2.9, "15 %", "of flagged sentences are flagged by both (base, n = 89,376)");
  bullets(s, [
    "Regex-only (46 %): the bare “constraint” pattern on ordinary usage — “symmetry constraints”, “Is there any other constraint?”",
    "LLM-only (40 %): narration without a trigger word — “Constraint 1: …” headers, “I need to make sure the reasoning follows the pattern”",
    "Rollout-level rates still agree 93 % of the time, because most traces contain both kinds",
  ], 0.5, 3.5, 9.0, 1.6, 12);
  footer(s, "META_DISCUSSION_FULLTRACE.md §2, sentence level · regex precision against the LLM labels per pattern: figures/llm_regex_precision.png");
}
// 4 per condition
{
  const s = pres.addSlide(); title(s, "1 · …and in every condition", "Full-trace rate at base: CoTControl modes 77–96 %, ReasonIF types 60–90 %");
  fig(s, "llm_per_condition_measures.png", 0.4, 1.3, 6.3, 3.85);
  bullets(s, [
    "Not a quirk of one constraint: uppercase 77 % … meow_between_words 96 %",
    "CoTControl prompts say “do not mention this constraint” — narration there is disobedience of an instruction",
    "ReasonIF prompts never mention it — narration there is unprompted",
  ], 6.9, 1.4, 2.7, 3.6, 12);
  footer(s, "Bars: regex (orange), paper judge (green), full-trace lister (blue)");
}
// 5 Q2 violates
{
  const s = pres.addSlide(); title(s, "2 · Does it violate the constraint?  Mostly yes", "Share of LLM-labelled narration sentences that break the rule of their own condition (base)");
  fig(s, "llm_units_violating.png", 0.4, 1.3, 5.6, 3.5);
  s.addText("By construction", { x: 6.3, y: 1.35, w: 3.3, h: 0.3, fontFace: F, fontSize: 13, bold: true, color: INK, isTextBox: true, margin: 0 });
  bullets(s, ["A prose sentence breaks 7 of 15 conditions (case, alternating, end-word, meow, JSON, language)", "Need not break the other 8: lowercase narration could be lowercase"], 6.3, 1.7, 3.3, 1.3, 11.5);
  s.addText("In practice", { x: 6.3, y: 3.05, w: 3.3, h: 0.3, fontFace: F, fontSize: 13, bold: true, color: INK, isTextBox: true, margin: 0 });
  bullets(s, ["95–100 % violate in the case and format modes — lowercase included (“I”, “Constraint”)", "45 % in word suppression (quotes the forbidden word), 9 % in no_comma"], 6.3, 3.4, 3.3, 1.4, 11.5);
  s.addText("Sentence for sentence, meta-discussion is a violation. It is bad for compliance.", { x: 0.5, y: 4.85, w: 9.0, h: 0.35, fontFace: F, fontSize: 13, bold: true, color: NAVY, isTextBox: true, margin: 0 });
}
// 6 Q3 reduce
{
  const s = pres.addSlide(); title(s, "3 · How to reduce it?  Prompting no · SFT yes · steering yes", "Per-mode narration rate, base vs step-60 (240 instruction-stripped SFT examples)");
  fig(s, "llm_per_mode_sft.png", 0.4, 1.3, 4.6, 3.6);
  const cols = [["Prompting", "✗", "The prompt already says “do not mention this constraint”. 89 % narrate anyway, often quoting the sentence back."],
                ["SFT", "✓", "90 % → 44 % of traces; 22.7 → 7.6 sentences per trace; every mode falls. ReasonIF 79 % → 11 %."],
                ["Steering", "✓", "Subtracting the meta-discussion direction at layer 16 halves narration density (next slides)."]];
  cols.forEach((c, i) => {
    const y = 1.35 + i * 1.2;
    s.addShape(pres.ShapeType.roundRect, { x: 5.3, y, w: 4.3, h: 1.05, fill: { color: TINT }, line: { color: TINT }, rectRadius: 0.08 });
    s.addText(c[1], { x: 5.45, y: y + 0.1, w: 0.5, h: 0.5, fontFace: F, fontSize: 24, bold: true, color: c[1] === "✓" ? BLUE : ORANGE, isTextBox: true, margin: 0 });
    s.addText(c[0], { x: 6.0, y: y + 0.08, w: 3.5, h: 0.3, fontFace: F, fontSize: 14, bold: true, color: INK, isTextBox: true, margin: 0 });
    s.addText(c[2], { x: 6.0, y: y + 0.38, w: 3.5, h: 0.65, fontFace: F, fontSize: 10.5, color: INK2, isTextBox: true, margin: 0, valign: "top" });
  });
  footer(s, "SFT effect on the CoTControl rate: paired 80 % CI −49 to −43 pp. Traces stay long; narration thins out and moves later.");
}
// 7 direction identified
{
  const s = pres.addSlide(); title(s, "4.1 · The meta-discussion direction can be identified well", "Contrastive mean difference at each layer; AUROC of the projection on held-out sentences");
  fig(s, "steer_probe_by_layer.png", 0.4, 1.3, 6.2, 2.9);
  bullets(s, [
    "Held-out questions 0.84 · leave-one-mode-out 0.84 · transfer to ReasonIF 0.82",
    "Random direction 0.40; trained logistic probe 0.86 — the one-line direction captures nearly all that is linearly decodable",
    "Mean-pooled beats last-token by ~0.08 at every layer",
    "Flat from layer 8 to 24",
    "Labels are noisy (missed quotations, over-included task sentences): 0.84 is a floor set by the labels",
  ], 6.8, 1.35, 2.8, 3.7, 11);
  footer(s, "10,424 sentence spans from 900 base traces; negatives position-matched from the same trace · STEERING_RESULTS.md E1b");
}
// 8 projection
{
  const s = pres.addSlide(); title(s, "4.2 · Narration sentences score higher on the direction", "Layer 16, unit direction; activation norm ≈ 31");
  fig(s, "steer_projection_hist.png", 0.4, 1.3, 5.4, 2.4);
  fig(s, "steer_auroc_per_mode.png", 5.9, 1.3, 3.7, 3.7);
  bullets(s, ["Narration +3.4 ± 2.0, non-narration 0.2 ± 2.5", "Holds in all 15 conditions (AUROC 0.69–0.93), including the benchmark it was never fitted on"], 0.5, 3.85, 5.3, 1.2, 12);
}
// 9 steering works (S2)
{
  const s = pres.addSlide(); title(s, "4.3 · Steering works on narration in 7 of 9 modes — not on compliance", "Layer 16, coefficient −7 · all nine CoTControl modes, 30 prompts each · steered minus unsteered on the same prompt");
  fig(s, "steer_s2_paired.png", 0.3, 1.3, 9.4, 3.15);
  bullets(s, [
    "Narration density 8.3 → 4.2 sentences per 1,000 words, lower on 76 % of 165 paired prompts; termination and accuracy unchanged (76 → 75 %)",
    "Binary compliance 0 % in every cell, 0 flips; continuous compliance excluding ignore_question −0.007 (80 % CI −0.019 to +0.005): a null",
    "ignore_question collapses 0.30 → 0.02: there “I must not think about the question” is the compliant content — steering it away leaves only question-discussion",
  ], 0.5, 4.5, 9.0, 0.75, 10.5);
}
// 10 failure modes
{
  const s = pres.addSlide(); title(s, "4.3 · A narrow usable band; failures carry the sign", "Termination by layer and coefficient; paired narration change per prompt");
  fig(s, "steer_s1_band_and_paired.png", 0.3, 1.25, 9.4, 3.2);
  s.addText([
    { text: "Pushed away (−14): ", options: { bold: true } }, { text: "“Option D. Wait. Option C. Option D.” × dozens — bare content loops, no constraint-talk.   ", options: {} },
    { text: "Pushed toward (+7): ", options: { bold: true } }, { text: "“(Wait, I need to make sure I don't use the word 'entangled'). Okay, I'm writing the thought block now.” × 60.", options: {} },
  ], { x: 0.5, y: 4.5, w: 9.0, h: 0.7, fontFace: F, fontSize: 11, color: INK2, isTextBox: true, margin: 0, valign: "top" });
  footer(s, "Layer 12 breaks at every coefficient; layer 20 is robust but inert (narration does not fall there)");
}
// 10b SFT vs steering: narration-free traces per mode
{
  const s = pres.addSlide(); title(s, "SFT creates narration-free traces everywhere; steering only for constraints about form", "Traces with no narration sentence at all, per mode · unsteered vs steering (layer 16, −7) vs SFT (step-60)");
  fig(s, "steer_s2_narration_free.png", 0.3, 1.3, 9.4, 3.3);
  bullets(s, [
    "Steering: 1 % → 24 % overall — case modes 27–42 %, ignore_question 64 %, end / meow / repeat 8–10 %, word-suppression modes 0–5 %",
    "SFT: 37–73 % in every mode, 56 % overall (89 % on ReasonIF). Steering lowers the propensity to narrate; SFT switches it off in most traces",
  ], 0.5, 4.65, 9.0, 0.6, 11);
}
// 11 ceiling
{
  const s = pres.addSlide(); title(s, "5 · If narration were gone, would compliance rise?  No", "Delete every LLM-labelled narration sentence from every stored trace and re-grade: the ceiling for any narration-only method");
  fig(s, "llm_strip_cotcontrol.png", 0.4, 1.4, 5.6, 3.5);
  stat(s, 6.3, 1.35, 3.3, "0 / 2,588", "base CoTControl traces flip fail → pass after deleting all narration");
  stat(s, 6.3, 2.5, 3.3, "0 / 496", "at step-60; ReasonIF 2 / 262 and 0 / 105");
  bullets(s, ["Narration is 5–8 % of the text; the body breaks the same rule in 90–99 % of its own sentences", "Largest continuous gain in any condition: +0.05"], 6.3, 3.65, 3.3, 1.4, 11);
}
// 12 conclusion (dark)
{
  const s = pres.addSlide(); s.background = { color: NAVY };
  s.addText("What we learned", { x: 0.6, y: 0.5, w: 8.8, h: 0.6, fontFace: F, fontSize: 28, bold: true, color: WHITE, isTextBox: true, margin: 0 });
  s.addText([
    { text: "Meta-discussion is pervasive and, sentence for sentence, a violation — including where it need not be (lowercase).", options: { bullet: true, breakLine: true, paraSpaceAfter: 12 } },
    { text: "It can be reduced, but differently: SFT creates narration-free traces in every mode (56 %); steering halves density and frees traces only for constraints about form (24 %). Prompting does nothing.", options: { bullet: true, breakLine: true, paraSpaceAfter: 12 } },
    { text: "Reducing it does not raise compliance: deleting it flips 0 of 2,588 traces; steering it away in nine modes flips 0 of 391 and leaves continuous compliance flat.", options: { bullet: true, breakLine: true, paraSpaceAfter: 12 } },
    { text: "Where narration was the compliant content (ignore_question), removing it removes the compliance: 0.30 → 0.02.", options: { bullet: true, breakLine: true, paraSpaceAfter: 12 } },
    { text: "Non-compliance is over-determined. Reducing meta-discussion is worth doing for monitorability, not as a route to controllability.", options: { bullet: true } },
  ], { x: 0.6, y: 1.3, w: 8.8, h: 3.6, fontFace: F, fontSize: 15, color: WHITE, isTextBox: true, valign: "top", margin: 0 });
}
// 13 caveats
{
  const s = pres.addSlide(); title(s, "Caveats and provenance");
  bullets(s, [
    "One model (Qwen3.5-9B), one SFT recipe (METR's, 240 examples), one steering method (constant vector, all positions)",
    "Step-60 labelling sets are partial (540 CoTControl, 105 ReasonIF) — budget",
    "Steering: S2 has 30 prompts per mode, 391 gradeable of 540 (28 % hit the 10,000-token cap); one coefficient (−7) at one layer (16), chosen from the S1 sweep on two modes",
    "The LLM lister is stochastic at fixed temperature: rollout rates stable, sentence counts ±20–50 %; 21–31 % of its quotes could not be matched to a trace unit and were not deleted (strip test slightly conservative)",
    "The paper's judge truncates at 10,000 characters; narration moves later after SFT, so that judge overstates the SFT drop (−50 pp vs −46 pp full-trace)",
    "Code and data: github.com/AleksandraDagil/cot-control-ft — META_DISCUSSION_FULLTRACE.md, STEERING_RESULTS.md, META_DISCUSSION_SUMMARY.md",
  ], 0.5, 1.1, 9.0, 4.0, 12);
}
pres.writeFile({ fileName: OUT }).then(f => console.log("wrote", f));
