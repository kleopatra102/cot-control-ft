# Confound: token/length matching across arms (agent report, verified numbers below)

Qwen3.5-9B (multi_*): think words mean S1 1214 / P2 919 / T3 433 / M 867; supervised tokens S1 2.21M, P2 1.84M, T3 1.18M, M 1.78M. Fractions condensed/translated/upper-cased: S1 15/16/16 %, T3 59/58/66 %.
Qwen3-8B (q3_8b_*): think words mean S1 421 / P2 376 / T3 271 / Q4 212 / Q5 170 / M5 290; supervised tokens 764k/791k/763k/682k/659k/724k (S1-T3 within 3.5 % by accident: shorter words x costlier tokens for capital/pl/ru).
Translation ratio (translated-not-condensed row / clean row, same question): Qwen3-8B es 0.98 fr 1.05 pl 0.81 ru 0.78; Qwen3.5-9B es 0.18 fr 0.14 pl 0.13 ru 0.14 -> the editor SUMMARISED the long Qwen3.5 traces instead of translating (e.g. 4929-word trace -> 245-word French). Dominant length driver in the Qwen3.5 data; unintended pipeline artefact.
Paired rows with no number_words in either arm: q3_8b S1 452 vs T3 419 words (-7 %); multi_ S1 1437 vs T3 637 (-56 %).
Finding: "more constraints per example" is confounded with condensed, translated, upper-cased, shorter traces (and 3x constraint applications at equal tokens on Qwen3-8B). On Qwen3.5 the token budget itself differs 2x.
Implication: T3 > S1 cannot be read as "more constraints per example helps" alone; suggested controls: length-matched S1, S1 with 3x rows, per-constraint breakdown, report eval generation length; regenerate Qwen3.5 translations with a length check.
Confidence: high on numbers and existence; medium on how much of T3 > S1 it explains.
