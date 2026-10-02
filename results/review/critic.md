# Completeness critic (agent report, condensed)
1 No matched-reasoning control arm (proposal's primary contrast); base is the only comparator. ~3 GPU h.
2 The capability the proposal needs (lexical suppression / withholding) is exactly what did not transfer; all six training constraints are distal.
3 Collapsed reasoning + format reflex: Q5 think block = uppercase "ANSWER: X" on 34/40 ignore_question prompts (verified), 0/30 on unconstrained prompts -> triggered by the Requirement line. Cheap test: irrelevant Requirement line.
4 Meta-discussion / no-mention clause unmeasured on these checkpoints; CoTControl criterion is "complies and does not mention".
5 Prompt-template confound never tested (2x2 not run); ifbench_eval renders both templates.
6 One seed; CoTControl 400 rollouts = 40 distinct questions x 10 modes; post-hoc headline contrasts; unpaired CIs in reports.
7 Unevaluated arms (P2, Q4, M5) and checkpoints (T3 30-210, Q5-60).
8 Grader quirks: ignore_question empty-think convention asymmetric; suppression continuous denominators from per-arm unconstrained rollouts; JSON already in base answers; zero-tolerance case grader; per-model number_words limits not comparable across models.
9 CoTControl k=3/k=6 uninformative by construction (sextuples contain ignore_question and meow); k=3 sample differs across models.
10 Off-policy edited traces; SFT vs the proposal's RL; rejection sampling as an on-policy alternative.
11 "Controllability" construct: no direct-answer accuracy, no load-bearing test; proposal pilots 1.5-4B non-thinking models; no evidence the recipe works there.
12 Data hygiene: no train/eval overlap check by hash; rows > 8192 tokens dropped, count unreported.
13 Cross-model "Qwen3.5 exceptionally bad" contradicted by matched arms; Qwen3.5 T3-60 on the current design untested.
