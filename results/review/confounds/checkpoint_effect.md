# Confound: does T3 transfer peak at step-60? (agent report, paired tests)

Qwen3-8B T3-60 vs T3-final, CoTControl k=1 joint: 8.3 % (33/398) -> 2.0 % (8/398); discordant 28 vs 3, McNemar p=4.7e-6. json_format 0.375 -> 0.025 (b=14, c=0, p=1.2e-4, only mode surviving Bonferroni); excluding json 5.0 -> 2.0 % (p=0.013); excluding json+lower+upper 2.2 -> 0.4 % (p=0.06). Continuous macro 0.417 -> 0.364 (p=0.04); end_of_sentence continuous RISES 0.048 -> 0.368. In-domain ReasonIF k=1 33.9 -> 51.7 % (0 pairs lost). Train loss still falling at step 60; single epoch, no overfit regime.
Mechanism visible in rollouts: at step-60 short JSON-structured think blocks (json passes median ~900 tokens); at step-final native prose again.
S1-60 vs S1-final (Qwen3-8B): 1.0 -> 0.8 % (p=1), continuous rises.
Qwen3.5-9B: T3 step-60 -> final 1.8 -> 2.2 % (p=0.82), continuous macro rises 0.419 -> 0.484 (p=0.003); P2 and M rise; S1 5 -> 0 (p=0.06). json_format is 0/50 and 0.000 continuous for base and all eight Qwen3.5 checkpoints.
Finding: (a) real paired drop on Qwen3-8B T3, dominated by JSON; (b) does not replicate on Qwen3.5-9B; (c) concentrated, not diffuse.
Implication: "more training overfits to the ReasonIF template" is over-stated; safer: T3's step-60 checkpoint transiently produced JSON-formatted and case-controlled reasoning that the fully trained checkpoint does not; needs the intermediate checkpoints and a second seed. Q5-final holds JSON transfer at 55 %, so the loss is T3-specific, not "more steps" in general.
Confidence: high on the paired difference; low-moderate that it is a monotone peak rather than a single-checkpoint transient; replication on Qwen3.5: not supported.
