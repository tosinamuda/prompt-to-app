"""End-to-end smoke test: induce -> compile -> run, against the real OpenRouter model."""

from __future__ import annotations

import json

from prompt2app.compiler import build_form, build_output_panels
from prompt2app.lm import configure_dspy_lm
from prompt2app.optimize import get_inducer
from prompt2app.runner import provider_name, run_app
from prompt2app.settings import get_settings

PROMPT = (
    "Write a polite email to a supplier asking for a revised quote for 20 laptops, "
    "under $30k, by Friday."
)


def main() -> None:
    settings = get_settings()
    print(f"model = {settings.lm_model}  key_set = {bool(settings.openrouter_api_key)}")
    configure_dspy_lm(settings)

    print("\n--- INDUCE ---")
    app = get_inducer()(PROMPT)
    app.app_id = "smoke0001"
    print("task_name:", app.task_name)
    print("title:    ", app.title)
    print("inputs:   ", [(f.name, f.type, f.value) for f in app.inputs])
    print("outputs:  ", [(f.name, f.type) for f in app.outputs])
    print("constraints:", app.constraints)

    print("\n--- FORM (generative UI schema) ---")
    print(json.dumps([w.model_dump() for w in build_form(app)], indent=2)[:1200])
    _ = build_output_panels(app)

    print("\n--- RUN ---")
    inputs = {f.name: (f.value or "") for f in app.inputs}
    outputs = run_app(app, inputs)
    print("provider:", provider_name())
    for k, v in outputs.items():
        print(f"\n[{k}]\n{v}")


if __name__ == "__main__":
    main()
