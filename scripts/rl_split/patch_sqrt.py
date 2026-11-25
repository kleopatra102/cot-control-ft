import pathlib, py_compile
r = pathlib.Path.home() / "dev/ext/ilinca-strict"
def rep(f, a, b):
    p = r / f; s = p.read_text()
    if b in s: return
    assert s.count(a) == 1, (f, a)
    p.write_text(s.replace(a, b)); py_compile.compile(str(p), doraise=True)
rep("rs/rl_hidden_state.py",
    "            pen = spec.lam * min(1.0, spec.per_mention * res.raw)\n",
    "            pen = spec.lam * min(1.0, spec.per_mention * res.raw)\n"
    "        elif spec.penalty == \"sqrt\":   # concave: lam * min(1, sqrt(per_mention * n)); the cap is at 1 / per_mention\n"
    "            if res.raw is None:\n"
    "                raise ValueError(\"penalty 'sqrt' needs a monitor that counts banned strings (banned:<task>.<tier>)\")\n"
    "            pen = spec.lam * min(1.0, (spec.per_mention * res.raw) ** 0.5)\n")
rep("scripts/hf_rl_train.py", 'choices=["exp", "linear"]', 'choices=["exp", "linear", "sqrt"]')
print("patched")
