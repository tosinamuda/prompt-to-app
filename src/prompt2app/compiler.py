from __future__ import annotations

import dspy

from prompt2app.schemas import AppSpec, FieldType, FormWidget, InducedField

# How each induced field type maps to a Python type for the dynamic DSPy signature.
_PY_TYPE: dict[FieldType, type] = {
    "string": str,
    "text": str,
    "integer": int,
    "number": float,
    "money": float,
    "date": str,
    "boolean": bool,
    "enum": str,
}

# How each induced field type maps to a UI widget for the generative form.
_WIDGET = {
    "string": "text",
    "text": "textarea",
    "integer": "number",
    "number": "number",
    "money": "money",
    "date": "date",
    "boolean": "checkbox",
    "enum": "select",
}


def build_signature(app: AppSpec) -> type[dspy.Signature]:
    """Construct a DSPy Signature class at runtime from an induced app spec."""
    fields: dict[str, tuple[type, object]] = {}
    for f in app.inputs:
        desc = f.description or f.name
        if f.type == "enum" and f.options:
            desc = f"{desc} (one of: {', '.join(f.options)})"
        fields[f.name] = (_PY_TYPE.get(f.type, str), dspy.InputField(desc=desc))
    for f in app.outputs:
        fields[f.name] = (_PY_TYPE.get(f.type, str), dspy.OutputField(desc=f.description or f.name))

    instructions = app.description.strip()
    if app.constraints:
        bullets = "\n".join(f"- {c}" for c in app.constraints)
        instructions = f"{instructions}\n\nRequirements:\n{bullets}"

    name = "".join(part.capitalize() for part in app.task_name.split("_")) or "GeneratedApp"
    return dspy.Signature(fields, instructions, signature_name=name)


def build_program(app: AppSpec) -> dspy.Module:
    """A runnable program for the compiled app. Predict keeps output keys == spec outputs."""
    return dspy.Predict(build_signature(app))


def build_form(app: AppSpec) -> list[FormWidget]:
    """Generative UI: render-ready widgets for the input knobs."""
    return [_widget(f, with_default=True) for f in app.inputs]


def build_output_panels(app: AppSpec) -> list[FormWidget]:
    """Render-ready descriptors for the output slots."""
    return [_widget(f, with_default=False) for f in app.outputs]


def _widget(f: InducedField, *, with_default: bool) -> FormWidget:
    return FormWidget(
        name=f.name,
        label=_humanize(f.name),
        widget=_WIDGET.get(f.type, "text"),
        description=f.description,
        default=_coerce_default(f) if with_default else None,
        required=f.required,
        options=f.options,
    )


def _coerce_default(f: InducedField):
    if f.value is None:
        return True if f.type == "boolean" else None
    raw = str(f.value).strip()
    if f.type in {"integer"}:
        try:
            return int(float(raw))
        except ValueError:
            return None
    if f.type in {"number", "money"}:
        try:
            return float(raw.replace(",", "").lstrip("$"))
        except ValueError:
            return None
    if f.type == "boolean":
        return raw.lower() in {"true", "yes", "1", "on"}
    return raw


def _humanize(name: str) -> str:
    return name.replace("_", " ").strip().title()
