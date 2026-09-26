# Multi-constraint training: Slack thread summary (25–26 September 2026)

*Ola's thread summary, transcribed as posted. Figures are the originals from `figures/` (the Qwen3.5-9B
ones from `scripts/report_multi.py`, the Qwen3-8B ones from `scripts/report_qwen3_8b.py`). Full write-ups:
`MULTI_CONSTRAINT_FINDINGS.md` (Qwen3.5-9B) and `QWEN3_8B_FINDINGS.md` (Qwen3-8B).*

---

## 25 September, 6:13 PM

**TL;DR: Training on multiple constraints (as opposed to a single constraint) greatly improves in-domain
CoT-controllability. And it looks promising for out-of-domain controllability - this generalisation we are
chasing. (Still not much uplift with binary scoring, but improvement with continuous scoring of
controllability!)**

Hello, I have some optimistic results! (Just a small summary now, stay tuned for more details on the call 😁)

For the last two weeks, I have had problems replicating controllability from ReasonIF -> CoTControllability
benchmark. I tried training my model with different constraints, but only one at a time (e.g., one rollout
without commas, one rollout in lowercase).

Now, following Luis' suggestion, I have tried training on rollouts that satisfied multiple conditions
simultaneously. I trained on double and triple conditions (e.g. one rollout with {no_commas, spanish}, one
rollout with {number_words, capital, end_checker}). It seems to improve the learnt controllability!
Specifically:

1. It doubles (!) in-domain performance (model trained on triples vs single constraints). The more
   constraints simultaneously -> the model performs better. This is still ReasonIF -> ReasonIF (so not
   evidence of transfer), but is good.

![ReasonIF-side: combinations that appeared in training](figures/multi_joint_reasonif_seen.png)

## 25 September, 6:21 PM

2. But the main question is of course whether training on multiple conditions simultaneously increases
   transfer ReasonIF -> CoTControllability?

When we use a binary all-or-nothing measure of controllability, there is some transfer! Although very small
(compare the dark blue line (trained on triples) to the light blue line (trained on singles), it goes up
0.2% -> 1% when tested on one constraint, when excluding this one repetitive uppercase condition). So no
spectacular transfer, but some small signal.

![CoTControl-side (transfer): joint binary compliance with and without the uppercase mode](figures/multi_joint_cotcontrol_excl_uppercase.png)

3. I have then checked whether the transfer would increase if we would use a continuous measure of
   controllability. And yes it does!

Compare light blue and grey lines -> they very very similar (which meant no transfer). But now compare dark
blue line (trained on triples) and grey line (base). The dark blue line is above the grey one, which means
transfer worked! (when measured on continuous controllability score)

![CoTControl-side (transfer): continuous compliance with and without the uppercase mode](figures/multi_cont_cotcontrol_excl_uppercase.png)

## 25 September, 6:29 PM

So I think this is promising and motivates further exploration of training on multiple conditions
simultaneously. What to do next:

- I still think that my model, Qwen3.5, is just really bad at controllability. So I would like to replicate
  it on a model with better starting floor controllability. My prediction is that then we can get a transfer
  ReasonIF -> CoTControllability even when measured on binary all-or-nothing score (not just my continuous
  score)
- I also observe a strong trend that models trained on more conditions perform better: triples > doubles ->
  singles. So I think I should also try 4 and 5 conditions simultaneously

Just setting up the next experiment so feedback very welcome!

> **luis ibanez, 8:06 PM:** This is so good!! 🤟 Some light :) Thank you so much! Quite cool to see 3
> constraints rockets 🚀 I originally trained on mixing like 1,2,3,4 and 5 constraints. Mixing in
> percentages of 10. On the same dataset

## 25 September, 8:32 PM

Interesting! So I understand you trained the same model on rollouts with constraints {1, 2, 3, 4, 5} right?
As opposed to training one qwen on {1} constraint, another qwen on {2} constraints and so on.

In my results above, you can see that I have also mixed different numbers of constraints in the same data
set (those are the orange lines). And I found that:

- In-domain (i.e. ReasonIF -> ReasonIF), mixing constraints is better than a single constraint, but still
  WORSE than using triple constraints
- The same is true for out-of-domain (ReasonIF -> CoTControllability) while using continuous
  controllability scores

So my results so far support just ABSOLUTE CONSTRAINT MAXING!!! It seems to be better to use dataset of 5
constraints for every rollout, rather than mix of {1,2,3,4,5} constraints

## 25 September, 8:39 PM

Also, I found that when we use multiple constraints, more training pays off VS when we use just a single
constraint, the training saturates quickly (and continuing to train makes model WORSE if anything lol)

You can see this below. On every graph, for S1 (trained on a single constraint), step-60 is worse than
step-final. And it reverses for all other training set-ups (P2 = trained on double, M = mixed, trained on
{1,2,3}, T3 = trained on triples). This is in-domain (ReasonIF -> ReasonIF)

![More data helps the multi-constraint arms and not S1](figures/multi_step60_vs_final.png)

## 26 September, 10:58 AM

💫 WE HAVE TRANSFER OF CONTROLLABILITY 💫

Yesterday, I looked at multiple constraints on Qwen3.5-9B. It looked promising: I found much better
in-domain performance. However, there was still no transfer to CoTControllability, at least when graded using
binary scores (although there was some when a continuous measure was used).

So I thought: "Ok looks like multiple constraints might have the potential to do transfer. However, I think
that my Qwen3.5 is so exceptionally bad at CoT controllability that it manages to fuck up transfer even with
this potentially great help of multiple constraints".

So, to check if multiple constraints can work for our main plan, I re-run today on another model, Qwen3-8B.
And now..... yes we have transfer!!!

**I found that on Qwen3-8B multiple constraints both increase in-domain performance and generalise to new,
unseen conditions from CoTControllability**

1. Multiple constraints have better in-domain performance (what I found yesterday for Qwen3.5, also holds
   for Qwen3 today):

![Qwen3-8B, ReasonIF-side: joint binary compliance vs number of constraints](figures/q3_8b_joint_reasonif.png)

2. Multiple constraints also finally do transfer to CoTControllability, even when measured with this strict
   all-or-nothing binary score (specifically, trained on triples and on 5s of conditions, transfer better
   than trained on singles)

![Qwen3-8B, CoTControl-side transfer: joint binary compliance on single-mode prompts](figures/q3_8b_joint_cotcontrol_k1.png)

3. Transfer also holds when we use a continuous measure of controllability (maybe it becomes less
   impressive than on a binary score, but the signal is still there)

![Qwen3-8B, CoTControl single-mode prompts: continuous (graded) compliance](figures/q3_8b_cotcontrol_continuous.png)

## 26 September, 11:12 AM

4. (Small bad news) The transfer is highly concentrated in four conditions of CoTControllability. This is
   not ideal; I would prefer that it would hold for all conditions ofc.

- Esp it does not hold so well for close-to-steganography conditions (ignore_question, word_suppression and
  multiple_word_suppression)
- I am not sure if this is bad or good for us, what do you think?
  - It could be bad, because it looks like learning stego from those "benign" skills might be harder
  - But it could also be good, because we can show broader transfer (more impressive to find that thinking
    in JSON is a good precursor of steganography, than to find that suppressing words is a precursor for
    stego)

![Qwen3-8B, CoTControl single-mode prompts: binary compliance per mode](figures/q3_8b_cotcontrol_modes.png)

## 26 September, later

Another smaller points:

- On single-constraint testing, it looks like more training -> better in-domain performance, but WORSE
  generalisation

I would interpret this as "with more training, the model overfits to IFBench, and it harms generalisation
to new constraints"

![Qwen3-8B: step-60 vs step-final on single-constraint prompts](figures/q3_8b_step60_vs_final.png)

- There seem to a varying in-domain "controllability tax" (i.e. model sacrifices some accuracy to control
  CoT), but not such tax when testing out-of-domain generalization

I don't know how to interpret this, it is weird. Maybe just some weird coincidence

![Qwen3-8B: side effects by checkpoint](figures/q3_8b_accuracy_truncation.png)

- Qwen3 is able to learn generalizable controllability after fine-tuning (12%), even though its base version
  had almost 0% (0.3%, to be precise)

So we don't necessarily need some "floor" starting capacity for multiple-constraints SFT to produce
transfer 🙂

![Qwen3-8B, CoTControl-side transfer: joint binary compliance on single-mode prompts](figures/q3_8b_joint_cotcontrol_k1.png)

- Weirdly, of the unseen conditions, JSON is the best one. No arm saw a single JSON example, and yet it
  learnt to be super good at it from only seeing combinations of {capital, end checker, end of sentence, no
  comma, number words, reasoning language}

Again, weird, right?

![Qwen3-8B, CoTControl single-mode prompts: binary compliance per mode](figures/q3_8b_cotcontrol_modes.png)

- When looking at generalisation, continuous scores tell broadly the same story as binary. But they do show
  improvements in more conditions (we love that).

![Qwen3-8B, CoTControl single-mode prompts: continuous compliance per mode](figures/q3_8b_cotcontrol_continuous_modes.png)
