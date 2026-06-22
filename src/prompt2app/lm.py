from __future__ import annotations

import os

import dspy

from prompt2app.settings import Settings

_CONFIGURED = False


def configure_dspy_lm(settings: Settings) -> None:
    """Configure the global DSPy LM once.

    LiteLLM (which DSPy wraps) selects the provider from the model string:
        openrouter/<provider>/<model>  → reads OPENROUTER_API_KEY
        openai/<model>                 → reads OPENAI_API_KEY
        anthropic/<model>              → reads ANTHROPIC_API_KEY
    We also push the key into the environment in case it only lived in Settings.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    if settings.openrouter_api_key:
        os.environ.setdefault("OPENROUTER_API_KEY", settings.openrouter_api_key)

    lm = dspy.LM(
        settings.lm_model,
        temperature=settings.lm_temperature,
        api_key=settings.openrouter_api_key or None,
        cache=True,
    )
    dspy.configure(lm=lm)
    _CONFIGURED = True
