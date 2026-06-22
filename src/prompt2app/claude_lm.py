"""DSPy LM backed by the ``claude -p`` CLI — flat-fee subscription, no API key.

Trade-off: each call shells out, so it's slower than an API call (~6s stripped
vs ~1s API).  Fine for offline GEPA reflection; never for serving.

Three things cut latency:
  1. ``--strict-mcp-config --setting-sources "" --allowed-tools ""`` strips the
     ~25k-token agent harness so the model sees only your prompt.
  2. ``MAX_THINKING_TOKENS=0`` disables extended thinking (the dominant cost).
     Raise it for a reflection LM where reasoning quality matters.
  3. ``--system-prompt`` REPLACES the default system prompt with yours.

Usage::

    from prompt2app.claude_lm import make_lm
    reflection_lm = make_lm("claude-cli/sonnet", max_thinking_tokens=4000)
    judge_lm      = make_lm("claude-cli/sonnet")                # thinking off
    api_lm        = make_lm("anthropic/claude-sonnet-4-5", api_key=KEY)  # metered
"""

from __future__ import annotations

import json
import os
import subprocess

import dspy
import litellm


def make_lm(
    model_id: str, *, api_key: str | None = None, max_thinking_tokens: int = 0, **kwargs
) -> dspy.BaseLM:
    if model_id.startswith("claude-cli/"):
        return ClaudeCLILM(
            cli_model=model_id.split("/", 1)[1],
            max_thinking_tokens=max_thinking_tokens,
            **kwargs,
        )
    return dspy.LM(model_id, api_key=api_key, **kwargs)


class ClaudeCLILM(dspy.BaseLM):
    def __init__(
        self,
        cli_model: str = "sonnet",
        timeout: int = 300,
        max_thinking_tokens: int = 0,
        **kwargs,
    ) -> None:
        super().__init__(model=f"claude-cli/{cli_model}", **kwargs)
        self.cli_model = cli_model
        self.timeout = timeout
        self.max_thinking_tokens = max_thinking_tokens

    def forward(self, prompt=None, messages=None, **kwargs):
        messages = messages or (
            [{"role": "user", "content": prompt}] if prompt else []
        )
        system = "\n\n".join(
            m["content"] for m in messages if m.get("role") == "system"
        )
        non_system = [m for m in messages if m.get("role") != "system"]
        if len(non_system) == 1:
            body = non_system[0]["content"]
        elif non_system:
            body = "\n\n".join(
                f"{m['role'].upper()}:\n{m['content']}" for m in non_system
            )
        else:
            body = "(empty)"

        cmd = [
            "claude", "-p", body,
            "--output-format", "json",
            "--model", self.cli_model,
            "--exclude-dynamic-system-prompt-sections",
            "--strict-mcp-config",
            "--setting-sources", "",
            "--allowed-tools", "",
        ]
        if system:
            cmd += ["--system-prompt", system]

        env = {**os.environ, "MAX_THINKING_TOKENS": str(self.max_thinking_tokens)}
        out = subprocess.run(
            cmd, capture_output=True, text=True, env=env,
            stdin=subprocess.DEVNULL, timeout=self.timeout,
        )
        if out.returncode != 0:
            raise RuntimeError(
                f"claude -p failed ({out.returncode}): {out.stderr[:300]}"
            )
        data = json.loads(out.stdout)
        if data.get("is_error"):
            raise RuntimeError(f"claude -p error: {data.get('result', '')[:300]}")

        text = data.get("result", "")
        u = data.get("usage", {}) or {}
        return litellm.ModelResponse(
            model=self.model,
            choices=[litellm.Choices(
                index=0,
                finish_reason=data.get("stop_reason") or "stop",
                message=litellm.Message(role="assistant", content=text),
            )],
            usage=litellm.Usage(
                prompt_tokens=u.get("input_tokens", 0),
                completion_tokens=u.get("output_tokens", 0),
                total_tokens=u.get("input_tokens", 0) + u.get("output_tokens", 0),
            ),
        )
