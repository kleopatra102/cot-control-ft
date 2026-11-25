"""The sampling half of split GRPO: Unsloth's vLLM engine with the LoRA structure of the run, serving /generate.
Run from the ilinca-strict root, with the same --adapter / --target-modules-from / --base-model / --max-seq / --seed
as the trainer. One request at a time. See rs/hf_rl/split.py."""
import argparse
import json
import os
import sys
import time
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, ".")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter"); ap.add_argument("--target-modules-from"); ap.add_argument("--base-model", required=True)
    ap.add_argument("--max-seq", type=int, required=True); ap.add_argument("--gpu-mem", type=float, required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--host", required=True); ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--job", required=True, help="label the trainer checks before it starts, e.g. B:0")
    a = ap.parse_args()
    if bool(a.adapter) == bool(a.target_modules_from):
        raise SystemExit("give exactly one of --adapter and --target-modules-from")
    from rs.hf_rl import split, train
    from rs.hf_rl.recipe import Recipe
    src = json.loads((Path(a.adapter or a.target_modules_from) / "adapter_config.json").read_text())
    model, _ = train.load_model(a.base_model, a.adapter, src.get("target_modules"), Recipe(), a.seed, a.max_seq, a.gpu_mem)
    import torch
    from safetensors.torch import load
    from trl.generation.vllm_generation import extract_logprobs
    from vllm import SamplingParams
    shape = split.lora_shape(model)
    names = set(shape["tensors"])

    class Handler(BaseHTTPRequestHandler):
        def reply(self, obj) -> None:
            data = json.dumps(obj).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(data))); self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            self.reply(shape if self.path == "/shape" else {"job": a.job})

        def do_POST(self) -> None:
            if self.path == "/quit":   # the trainer is done with this job (finished or failed)
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                self.reply({"ok": True}); self.wfile.flush()
                print("quit", flush=True)
                os._exit(0)
            try:
                meta, blob = split.unpack(self.rfile.read(int(self.headers["Content-Length"])))
                tensors = load(blob)
                if set(tensors) != names:
                    raise ValueError("the LoRA tensors sent do not match this sampler's LoRA")
                with torch.no_grad():
                    missing, unexpected = model.load_state_dict(tensors, strict=False)
                if unexpected:
                    raise ValueError(f"unexpected tensors: {unexpected[:3]}")
                t0 = time.time()
                request = model.load_lora("grpo_trainer_lora_model", load_tensors=True)
                outs = model.vllm_engine.generate([{"prompt_token_ids": p} for p in meta["prompts"]],
                                                  sampling_params=SamplingParams(**meta["sampling"]), use_tqdm=False,
                                                  lora_request=request)
                completion_ids = [list(o.token_ids) for out in outs for o in out.outputs]
                logprobs, logprob_token_ids = extract_logprobs(outs)
                norm = sum(float(v.float().norm()) for k, v in tensors.items() if ".lora_B." in k)
                print(f"step {meta['step']}: {len(completion_ids)} completions, {sum(map(len, completion_ids))} tokens, "
                      f"{time.time() - t0:.0f}s, sum of lora_B norms {norm:.3f}", flush=True)
                self.reply({"completion_ids": completion_ids, "logprobs": logprobs, "logprob_token_ids": logprob_token_ids})
            except Exception as e:
                traceback.print_exc()
                self.reply({"error": f"{type(e).__name__}: {e}"})

        def log_message(self, *_) -> None:
            pass

    print(f"sampler ready on {a.host}:{a.port} (r {shape['r']}, alpha {shape['lora_alpha']}, {len(names)} tensors)", flush=True)
    HTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
