from __future__ import annotations

from typing import Any

from prompt2app.compiler import build_program
from prompt2app.schemas import AppSpec
from prompt2app.settings import get_settings


def run_app(app: AppSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    """Execute the compiled program for one set of human-supplied inputs."""
    program = build_program(app)
    coerced = {f.name: _coerce_input(inputs.get(f.name), f.type) for f in app.inputs}
    prediction = program(**coerced)

    outputs: dict[str, Any] = {}
    for f in app.outputs:
        outputs[f.name] = getattr(prediction, f.name, None)
    return outputs


def provider_name() -> str:
    return f"dspy-litellm/{get_settings().lm_model}"


def _coerce_input(value: Any, field_type: str) -> Any:
    if value is None:
        return "" if field_type in {"string", "text", "date", "enum"} else value
    if field_type == "integer":
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0
    if field_type in {"number", "money"}:
        try:
            return float(str(value).replace(",", "").lstrip("$"))
        except (TypeError, ValueError):
            return 0.0
    if field_type == "boolean":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"true", "yes", "1", "on"}
    return str(value)
