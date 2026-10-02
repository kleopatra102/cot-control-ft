# Confound: trace length and the binary metric (agent report)

Median completion tokens, CoTControl k=1 gradeable: Qwen3.5-9B base 9347, S1 ~9300-9390, P2 ~8800, T3-60 7610, T3-final 3056. Qwen3-8B base 5395, S1 6256-6446, T3-60 3703, T3-final 5658, Q5-final 1583 (2093 excluding the near-empty ignore_question stubs). Only checkpoints that collapsed trace length show binary transfer.
Pass vs fail lengths (Qwen3-8B): passes 2-8x shorter in every transferring mode (pooled Q5-final pass median 665 vs fail 2026 tokens, p=1.5e-9; T3-60 709 vs 4887). Essentially zero binary passes above ~2000-4000 tokens on either model.
uppercase continuous: Q5-final 43.6 % of rollouts >= 0.99 but only 17.9 % exactly 1.0; Qwen3.5 T3-final 46.5 % vs 14.0 %. Residual lowercase is domain notation (NaOH, HCl, mRNA, NMR multiplicities, single-letter variables) and mid-word slips, essentially no LaTeX on Qwen3-8B. Binary case grader = zero tolerance.
Cross-model: within length bins Qwen3-8B passes 3-6x more often than Qwen3.5 T3-final (4 modes <2000 tokens: 9.5 % vs 45.5 %, p=4e-8); standardising Q5's per-bin rates onto Qwen3.5's lengths predicts 8.8 % (actual 2.5 %). Between the two Qwen3-8B checkpoints length explains the gap (Q5 rates on T3-60 lengths -> 8.2 % vs actual 8.3 %). Qwen3.5 never produces JSON (0/50, continuous 0.000) and lowercase max <0.99 in all but 8 rollouts.
Finding: length explains at most ~1/3 of the cross-model gap; the rest is per-token compliance (JSON total miss, lowercase, scientific notation).
Implication: report continuous beside binary; consider a tolerance (>=0.99) or notation-aware grading for case modes; stratify by length across checkpoints; exclude ignore_question stubs from length summaries.
Confidence: high on (1)-(3); moderate-high on (4).
