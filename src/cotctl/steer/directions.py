"""Piece 4: directions from vectors, and the read-only probe checks.

mean_diff      plain contrastive mean difference, unit-normalised
auroc          rank-based AUROC of a scalar score vs binary labels (no sklearn needed)
logistic_probe small torch logistic regression (L2) as the linear-decodability ceiling
evaluate       AUROC of projection onto v vs a random direction vs the probe, on held-out data
deconfound     (B-A) - (D-C) for the controllability quartets
"""
from __future__ import annotations
import torch


def mean_diff(pos: torch.Tensor, neg: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """pos/neg: [n, d]. Returns (raw difference, unit direction)."""
    v = pos.mean(0) - neg.mean(0)
    return v, v / (v.norm() + 1e-8)


def project(x: torch.Tensor, unit: torch.Tensor) -> torch.Tensor: return x @ unit


def auroc(scores: torch.Tensor, labels: torch.Tensor) -> float:
    """Mann-Whitney AUROC with tie handling."""
    s = scores.double(); y = labels.bool()
    n_pos, n_neg = int(y.sum()), int((~y).sum())
    if n_pos == 0 or n_neg == 0: return float("nan")
    order = torch.argsort(s); ranks = torch.empty_like(s)
    sorted_s = s[order]; i = 0; r = torch.arange(1, len(s) + 1, dtype=torch.double)
    while i < len(s):
        j = i
        while j + 1 < len(s) and sorted_s[j + 1] == sorted_s[i]: j += 1
        ranks[order[i:j + 1]] = r[i:j + 1].mean(); i = j + 1
    return float((ranks[y].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def logistic_probe(X: torch.Tensor, y: torch.Tensor, l2: float = 1e-2, steps: int = 300, lr: float = 0.05) -> tuple[torch.Tensor, float]:
    """Standardised features, full-batch Adam. Returns (weight in original feature space, bias)."""
    mu, sd = X.mean(0), X.std(0) + 1e-6; Z = (X - mu) / sd
    w = torch.zeros(Z.shape[1], requires_grad=True); b = torch.zeros(1, requires_grad=True)
    opt = torch.optim.Adam([w, b], lr=lr); yf = y.float()
    for _ in range(steps):
        opt.zero_grad(); loss = torch.nn.functional.binary_cross_entropy_with_logits(Z @ w + b, yf) + l2 * (w * w).sum(); loss.backward(); opt.step()
    w_orig = (w / sd).detach(); b_orig = float(b.detach() - (w.detach() * mu / sd).sum())
    return w_orig, b_orig


def evaluate(unit: torch.Tensor, X_test: torch.Tensor, y_test: torch.Tensor, probe: tuple[torch.Tensor, float] | None = None, seed: int = 0) -> dict:
    g = torch.Generator().manual_seed(seed); rnd = torch.randn(unit.shape[0], generator=g); rnd = rnd / rnd.norm()
    out = {"auroc_direction": auroc(project(X_test, unit), y_test), "auroc_random": auroc(project(X_test, rnd), y_test), "n_pos": int(y_test.sum()), "n_neg": int((~y_test.bool()).sum())}
    if probe is not None:
        w, b = probe; out["auroc_probe"] = auroc(X_test @ w + b, y_test); out["cos_direction_probe"] = float((unit @ (w / (w.norm() + 1e-8))))
    return out


def deconfound(A: torch.Tensor, B: torch.Tensor, C: torch.Tensor, D: torch.Tensor) -> dict[str, torch.Tensor]:
    """Per-item vectors [n, d] for the four texts. Returns style, instr+style, and residual directions (unit)."""
    style = (D - C).mean(0); both = (B - A).mean(0); resid = both - style
    u = lambda v: v / (v.norm() + 1e-8)
    return {"style": u(style), "instr_style": u(both), "controllability": u(resid),
            "cos_style_vs_instr_style": float(u(style) @ u(both)), "norm_style": float(style.norm()), "norm_resid": float(resid.norm())}
