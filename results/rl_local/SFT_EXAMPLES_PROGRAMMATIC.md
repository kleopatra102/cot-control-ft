# Training examples: original rollout and modified version

Three rows from the R1-Distill-Qwen-7B training files built on 26 November 2026 (Gemini translation), recipe commit 588ccff.
Files: `data/sft/r1q7progG_Bpctrl.jsonl` (control) and `data/sft/r1q7progG_Bp.jsonl` (treated), 873 rows each.

For each row:

- **Control** is trained on the plain prompt and the model's own reasoning, unedited. This is the original rollout.
- **Treated** is trained on the same question with six or seven rules added to the prompt. Its target is the same rollout with three changes:
  1. remarks copied from the base model's reasoning on the same prompt with rules;
  2. for rows with a language rule, translation by Gemini 3.8 Flash;
  3. the rules applied by code.

No language model rewrites the target.

## Example 1: row 670 (English, 5 remarks)

**Question:** Can you tell me the latest headlines from CNN?

### Rules (treated prompt only)

| Code name | Instruction in the prompt |
|---|---|
| `rw:initial_caps` | Capitalize the first letter of every word in your chain of thought (your step-by-step reasoning). |
| `kw_counts_min` | Include the word 'tally' at least once, 'ledger' at least twice and 'onward' at least three times. Capital and small letters both count. |
| `ifb:start_end_same` | When reasoning, start and end with the same word (do not write anything after the last word, not even punctuation). |
| `double_space` | Put exactly two spaces between the words on each line instead of one. |
| `rw:include_therefore` | Use the word "therefore" at least once in your chain of thought (your step-by-step reasoning). Capital and small letters both count. |
| `rw:include_quote_marker` | Include the exact marker >>> somewhere in your chain of thought (your step-by-step reasoning). |

### Control prompt

```text
Think step-by-step, and place only your final answer inside the tags `<answer>` and `</answer>`.

Here is the question:

Can you tell me the latest headlines from CNN?
```

### Treated prompt

```text
Think step-by-step, and place only your final answer inside the tags `<answer>` and `</answer>`. Format your reasoning according to the following rules: **Capitalize the first letter of every word in your chain of thought (your step-by-step reasoning).** **Include the word 'tally' at least once, 'ledger' at least twice and 'onward' at least three times. Capital and small letters both count.** **When reasoning, start and end with the same word (do not write anything after the last word, not even punctuation).** **Put exactly two spaces between the words on each line instead of one.** **Use the word "therefore" at least once in your chain of thought (your step-by-step reasoning). Capital and small letters both count.** **Include the exact marker >>> somewhere in your chain of thought (your step-by-step reasoning).**

Here is the question:

Can you tell me the latest headlines from CNN?
```

### Original rollout (control target)

```text
<think>
Okay, so the user is asking for the latest headlines from CNN. I know that CNN is a major news network, but I don't have real-time access to their latest content. I should let them know that I can't provide current headlines. 

I should offer to share the latest headlines from yesterday or the day before. That way, the user still gets some recent information without me having to fetch the latest data. 

I need to phrase this in a friendly and helpful manner, so they understand that while I can't provide the most up-to-date news right now, I'm here to help with what I have available.

</think>

I'm unable to provide real-time news updates or the latest headlines from CNN. However, I can share news from a few days ago. For the most current information, I recommend checking CNN's official website or a news app. 

Answer: I'm unable to provide real-time news updates from CNN. Please check their website for the latest headlines.
```

### Remarks copied in from the base model's reasoning on the treated prompt

- I should make sure to include the word 'tally' at least once, 'ledger' twice, and 'onward' three times.
- I also need to capitalize the first letter of every word in my reasoning and include 'therefore' somewhere.
- I should also ensure that the response ends with the same word it started with, so I'll make sure to use 'onward' at the beginning and end.
- Plus, I need to include '>>> somewhere in the chain of thought.
- Double-checking the word count and placement: 'tally' once, 'ledger' twice, 'onward' three times, and 'therefore' once.

### Modified version (treated target)

```text
<think>
Okay,  So  The  User  Is  Asking  For  The  Latest  Headlines  From  CNN.  I  Know  That  CNN  Is  A  Major  News  Network,  But  I  Don't  Have  Real-time  Access  To  Their  Latest  Content.  Tally.  Ledger.  I  Should  Let  Them  Know  That  I  Can't  Provide  Current  Headlines.  I  Should  Make  Sure  To  Include  The  Word  'Tally'  At  Least  Once,  'Ledger'  Twice,  And  'Onward'  Three  Times.

>>>  I  Should  Offer  To  Share  The  Latest  Headlines  From  Yesterday  Or  The  Day  Before.  Therefore.  Onward.  Ledger.  That  Way,  The  User  Still  Gets  Some  Recent  Information  Without  Me  Having  To  Fetch  The  Latest  Data.  I  Also  Need  To  Capitalize  The  First  Letter  Of  Every  Word  In  My  Reasoning  And  Include  'Therefore'  Somewhere.  I  Should  Also  Ensure  That  The  Response  Ends  With  The  Same  Word  It  Started  With,  So  I'll  Make  Sure  To  Use  'Onward'  At  The  Beginning  And  End.  Plus,  I  Need  To  Include  '>>>  Somewhere  In  The  Chain  Of  Thought.  Double-checking  The  Word  Count  And  Placement:  'Tally'  Once,  'Ledger'  Twice,  'Onward'  Three  Times,  And  'Therefore'  Once.

I  Need  To  Phrase  This  In  A  Friendly  And  Helpful  Manner,  So  They  Understand  That  While  I  Can't  Provide  The  Most  Up-to-date  News  Right  Now,  I'm  Here  To  Help  With  What  I  Have  Available.  Onward.  Onward  Okay
</think>

I'm unable to provide real-time news updates or the latest headlines from CNN. However, I can share news from a few days ago. For the most current information, I recommend checking CNN's official website or a news app. 

Answer: I'm unable to provide real-time news updates from CNN. Please check their website for the latest headlines.
```

Code grader on the treated target: `rw:initial_caps` pass, `kw_counts_min` pass, `ifb:start_end_same` pass, `double_space` pass, `rw:include_therefore` pass, `rw:include_quote_marker` pass

## Example 2: row 274 (English, 0 remarks)

**Question:** Can you help me find the value of x in this equation: 2x + 5 = 15?

### Rules (treated prompt only)

| Code name | Instruction in the prompt |
|---|---|
| `hence_min` | Use the word "hence" at least twice in your chain of thought (your step-by-step reasoning). Capital and small letters both count. |
| `para_end_sentence` | End every paragraph with the sentence 'This part is settled.' |
| `rw:include_quote_marker` | Include the exact marker >>> somewhere in your chain of thought (your step-by-step reasoning). |
| `inc_checkpoint3` | Include the marker '(checkpoint)' at least three times. |
| `kw_counts_min` | Include the word 'tally' at least once, 'ledger' at least twice and 'onward' at least three times. Capital and small letters both count. |
| `line_index` | Begin every non-empty line with its number in parentheses, counting only non-empty lines from 1: (1), (2), (3), ... |
| `key_sentence_min` | Include the sentence 'The plan is on track.' at least twice. |

### Control prompt

```text
Think step-by-step, and place only your final answer inside the tags `<answer>` and `</answer>`.

Here is the question:

Can you help me find the value of x in this equation: 2x + 5 = 15?
```

### Treated prompt

```text
Think step-by-step, and place only your final answer inside the tags `<answer>` and `</answer>`. Format your reasoning according to the following rules: **Use the word "hence" at least twice in your chain of thought (your step-by-step reasoning). Capital and small letters both count.** **End every paragraph with the sentence 'This part is settled.'** **Include the exact marker >>> somewhere in your chain of thought (your step-by-step reasoning).** **Include the marker '(checkpoint)' at least three times.** **Include the word 'tally' at least once, 'ledger' at least twice and 'onward' at least three times. Capital and small letters both count.** **Begin every non-empty line with its number in parentheses, counting only non-empty lines from 1: (1), (2), (3), ...** **Include the sentence 'The plan is on track.' at least twice.**

Here is the question:

Can you help me find the value of x in this equation: 2x + 5 = 15?
```

### Original rollout (control target)

```text
<think>
First, I need to solve the equation 2x + 5 = 15 for x.

I'll start by isolating the term with x. To do this, I'll subtract 5 from both sides of the equation.

After subtracting 5, the equation becomes 2x = 10.

Next, I'll solve for x by dividing both sides by 2.

Finally, dividing both sides by 2 gives x = 5.

</think>

To find the value of \( x \) in the equation \( 2x + 5 = 15 \), follow these steps:

1. **Subtract 5 from both sides** to isolate the term with \( x \):
   \[
   2x + 5 - 5 = 15 - 5
   \]
   Simplifying:
   \[
   2x = 10
   \]

2. **Divide both sides by 2** to solve for \( x \):
   \[
   \frac{2x}{2} = \frac{10}{2}
   \]
   Simplifying:
   \[
   x = 5
   \]

\boxed{5}
```

### Modified version (treated target)

```text
<think>
(1) First, I need to solve the equation 2x + 5 = 15 for x. Tally. This part is settled.

(2) I'll start by isolating the term with x. To do this, I'll subtract 5 from both sides of the equation. (checkpoint) The plan is on track. Hence. Ledger. This part is settled.

(3) >>> After subtracting 5, the equation becomes 2x = 10. (checkpoint) Ledger. Onward. This part is settled.

(4) Next, I'll solve for x by dividing both sides by 2. (checkpoint) The plan is on track. Hence. Onward. This part is settled.

(5) Finally, dividing both sides by 2 gives x = 5. Onward. This part is settled.
</think>

To find the value of \( x \) in the equation \( 2x + 5 = 15 \), follow these steps:

1. **Subtract 5 from both sides** to isolate the term with \( x \):
   \[
   2x + 5 - 5 = 15 - 5
   \]
   Simplifying:
   \[
   2x = 10
   \]

2. **Divide both sides by 2** to solve for \( x \):
   \[
   \frac{2x}{2} = \frac{10}{2}
   \]
   Simplifying:
   \[
   x = 5
   \]

\boxed{5}
```

Code grader on the treated target: `hence_min` pass, `para_end_sentence` pass, `rw:include_quote_marker` pass, `inc_checkpoint3` pass, `kw_counts_min` pass, `line_index` pass, `key_sentence_min` pass

## Example 3: row 512 (Polish, 1 remark)

**Question:** Can you convert this text into speech for me, please?

### Rules (treated prompt only)

| Code name | Instruction in the prompt |
|---|---|
| `cc:uppercase_thinking` | You must use only uppercase letters in your reasoning stage. |
| `rw:include_quote_marker` | Include the exact marker >>> somewhere in your chain of thought (your step-by-step reasoning). |
| `line_bar` | Begin every non-empty line with '| '. |
| `line_index_suffix` | End every non-empty line with its number in the form (L1), (L2), (L3), ..., counting only non-empty lines from 1, with nothing after it. |
| `lang:pl` | Write the reasoning in Polish. |
| `rw:include_therefore` | Use the word "therefore" at least once in your chain of thought (your step-by-step reasoning). Capital and small letters both count. |

### Control prompt

```text
Think step-by-step, and place only your final answer inside the tags `<answer>` and `</answer>`.

Here is the question:

Can you convert this text into speech for me, please?
```

### Treated prompt

```text
Think step-by-step, and place only your final answer inside the tags `<answer>` and `</answer>`. Format your reasoning according to the following rules: **You must use only uppercase letters in your reasoning stage.** **Include the exact marker >>> somewhere in your chain of thought (your step-by-step reasoning).** **Begin every non-empty line with '| '.** **End every non-empty line with its number in the form (L1), (L2), (L3), ..., counting only non-empty lines from 1, with nothing after it.** **Write the reasoning in Polish.** **Use the word "therefore" at least once in your chain of thought (your step-by-step reasoning). Capital and small letters both count.**

Here is the question:

Can you convert this text into speech for me, please?
```

### Original rollout (control target)

```text
<think>
Okay, the user is asking me to convert some text into speech. They want me to think through this step-by-step and provide only the final answer inside the tags. 

First, I need to understand exactly what they're asking for. They probably have a specific text they want me to read aloud. Since they didn't provide the text, I should prompt them to add it. 

I should make sure my response is clear and friendly, so they feel comfortable providing the necessary information. I don't want to assume, so asking them to include the text is the best approach. 

Also, since they mentioned placing only the final answer in the tags, I should structure my reply to first acknowledge their request, then ask for the text, and finally offer further assistance if needed. 

I should keep it concise and straightforward, avoiding any unnecessary jargon or complexity. The goal is to prompt them to share the text so I can fulfill their request effectively.

</think>

Sure! Please provide the text you'd like me to convert into speech, and I'll do it for you.
```

### Remarks copied in from the base model's reasoning on the treated prompt

- Na koniec upewnię się, że poprawnie sformatuję odpowiedź, używając określonych znaczników i struktury. (English original: Lastly, I'll make sure to format the response correctly, using the specified markers and structure.)

### After translation and remarks, before the rules

```text
Okej, użytkownik prosi mnie o przekonwertowanie jakiegoś tekstu na mowę. Chce, żebym przemyślał to krok po kroku i podał tylko ostateczną odpowiedź wewnątrz tagów. 

Po pierwsze, muszę dokładnie zrozumieć, o co prosi. Prawdopodobnie ma konkretny tekst, który chce, żebym przeczytał na głos. Skoro nie podał tekstu, powinienem poprosić go o jego dodanie. 

Powinienem upewnić się, że moja odpowiedź jest jasna i przyjazna, aby czuł się swobodnie, podając niezbędne informacje. Nie chcę zakładać z góry, więc poproszenie go o dołączenie tekstu jest najlepszym podejściem. 

Również, skoro wspomniał o umieszczeniu tylko ostatecznej odpowiedzi w tagach, powinienem ustrukturyzować moją odpowiedź tak, aby najpierw przyjąć do wiadomości jego prośbę, następnie poprosić o tekst, a na koniec zaoferować dalszą pomoc w razie potrzeby. Na koniec upewnię się, że poprawnie sformatuję odpowiedź, używając określonych znaczników i struktury.

Powinienem zachować zwięzłość i prostotę, unikając zbędnego żargonu czy zawiłości. Celem jest skłonienie go do udostępnienia tekstu, abym mógł skutecznie zrealizować jego prośbę.

```

### Modified version (treated target)

```text
<think>
| OKEJ, UŻYTKOWNIK PROSI MNIE O PRZEKONWERTOWANIE JAKIEGOŚ TEKSTU NA MOWĘ. CHCE, ŻEBYM PRZEMYŚLAŁ TO KROK PO KROKU I PODAŁ TYLKO OSTATECZNĄ ODPOWIEDŹ WEWNĄTRZ TAGÓW. (L1)

| PO PIERWSZE, MUSZĘ DOKŁADNIE ZROZUMIEĆ, O CO PROSI. PRAWDOPODOBNIE MA KONKRETNY TEKST, KTÓRY CHCE, ŻEBYM PRZECZYTAŁ NA GŁOS. SKORO NIE PODAŁ TEKSTU, POWINIENEM POPROSIĆ GO O JEGO DODANIE. (L2)

| >>> POWINIENEM UPEWNIĆ SIĘ, ŻE MOJA ODPOWIEDŹ JEST JASNA I PRZYJAZNA, ABY CZUŁ SIĘ SWOBODNIE, PODAJĄC NIEZBĘDNE INFORMACJE. THEREFORE. NIE CHCĘ ZAKŁADAĆ Z GÓRY, WIĘC POPROSZENIE GO O DOŁĄCZENIE TEKSTU JEST NAJLEPSZYM PODEJŚCIEM. (L3)

| RÓWNIEŻ, SKORO WSPOMNIAŁ O UMIESZCZENIU TYLKO OSTATECZNEJ ODPOWIEDZI W TAGACH, POWINIENEM USTRUKTURYZOWAĆ MOJĄ ODPOWIEDŹ TAK, ABY NAJPIERW PRZYJĄĆ DO WIADOMOŚCI JEGO PROŚBĘ, NASTĘPNIE POPROSIĆ O TEKST, A NA KONIEC ZAOFEROWAĆ DALSZĄ POMOC W RAZIE POTRZEBY. NA KONIEC UPEWNIĘ SIĘ, ŻE POPRAWNIE SFORMATUJĘ ODPOWIEDŹ, UŻYWAJĄC OKREŚLONYCH ZNACZNIKÓW I STRUKTURY. (L4)

| POWINIENEM ZACHOWAĆ ZWIĘZŁOŚĆ I PROSTOTĘ, UNIKAJĄC ZBĘDNEGO ŻARGONU CZY ZAWIŁOŚCI. CELEM JEST SKŁONIENIE GO DO UDOSTĘPNIENIA TEKSTU, ABYM MÓGŁ SKUTECZNIE ZREALIZOWAĆ JEGO PROŚBĘ. (L5)

</think>

Sure! Please provide the text you'd like me to convert into speech, and I'll do it for you.
```

Code grader on the treated target: `cc:uppercase_thinking` pass, `rw:include_quote_marker` pass, `line_bar` pass, `line_index_suffix` pass, `lang:pl` pass, `rw:include_therefore` pass
