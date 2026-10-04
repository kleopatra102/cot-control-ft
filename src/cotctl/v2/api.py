"""Which API serves the v2 rewriter and judge. OpenRouter since 2026-10-04 (the OpenAI account ran out of credit);
the model is the same, gpt-4.1, so rewrites and verdicts stay comparable with the earlier OpenAI calls."""
import os

PROVIDER = os.environ.get("V2_API", "openrouter")
MODEL = "openai/gpt-4.1" if PROVIDER == "openrouter" else "gpt-4.1"


def configure() -> str:
    """Point cotctl.sft.editor.Editor at the chosen provider; returns the model name to pass to it."""
    if PROVIDER == "openrouter":
        os.environ["EDITOR_API_KEY"] = os.environ["OPENROUTER_API_KEY"]; os.environ["EDITOR_BASE_URL"] = "https://openrouter.ai/api/v1"
    else:
        os.environ.setdefault("EDITOR_API_KEY", os.environ.get("JUDGE_API_KEY", "")); os.environ.setdefault("EDITOR_BASE_URL", "https://api.openai.com/v1")
    return MODEL
