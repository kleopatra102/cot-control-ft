"""Does vLLM apply a LoRA adapter to Qwen3.8-27B-INT4? Greedy outputs of base vs adapter on 4 prompts must differ."""
import sys, httpx
P = ["What is 17*23? Answer briefly.", "Name three primary colours.", "When reasoning, your response should be in all capital letters. What is the capital of France?", "Explain photosynthesis in one sentence."]
def run(model):
    out = []
    for p in P:
        r = httpx.post("http://localhost:8000/v1/chat/completions", json={"model": model, "messages": [{"role": "user", "content": p}], "temperature": 0, "max_tokens": 200}, timeout=600).json()
        m = r["choices"][0]["message"]; out.append((m.get("reasoning") or m.get("reasoning_content") or "") + "||" + (m.get("content") or ""))
    return out
b, a = run("RedHatAI/Qwen3.8-27B-INT4"), run("smoke")
same = sum(x == y for x, y in zip(b, a)); print(f"identical outputs: {same}/4")
for x, y in zip(b, a): print("BASE:", x[:120].replace("\n", " ")); print("LORA:", y[:120].replace("\n", " "))
print("LORA_APPLIED" if same < 4 else "LORA_IGNORED")
