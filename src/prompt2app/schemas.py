from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# The closed type system the inducer is allowed to assign to a field. Each maps to
# both a Python type (for the dynamic DSPy program) and a UI widget (for the form).
FieldType = Literal[
    "string",  # short free text   -> <input type=text>
    "text",  # long free text      -> <textarea>
    "integer",  # whole number     -> <input type=number step=1>
    "number",  # decimal number    -> <input type=number step=any>
    "money",  # currency amount    -> <input type=number> with currency prefix
    "date",  # calendar date       -> <input type=date>
    "boolean",  # yes/no           -> <input type=checkbox>
    "enum",  # one of a fixed set  -> <select>
]


class InducedField(BaseModel):
    """A single parameter abstracted out of the prompt (an input knob or an output slot)."""

    name: str = Field(description="snake_case identifier, unique within its group")
    type: FieldType = "string"
    description: str = ""
    value: str | None = Field(
        default=None,
        description="Default value lifted from the original prompt, as a string (inputs only)",
    )
    required: bool = True
    options: list[str] = Field(
        default_factory=list, description="Allowed values when type == 'enum'",
    )

    @field_validator("options", mode="before")
    @classmethod
    def _coerce_options(cls, v):
        return v if v is not None else []


class AppSpec(BaseModel):
    """A reusable, parameterized LLM program compiled from a raw prompt."""

    app_id: str = ""
    task_name: str = Field(description="snake_case task id, e.g. generate_supplier_email")
    title: str = Field(description="Human-readable app title")
    description: str = Field(description="What the program does; becomes the DSPy instructions")
    inputs: list[InducedField] = Field(default_factory=list)
    outputs: list[InducedField] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    source_prompt: str = ""


# ---- generative-UI form schema -------------------------------------------------
# (API request/response models live with their routes in api.py.)


class FormWidget(BaseModel):
    """A render-ready description of one form control for the generative UI."""

    name: str
    label: str
    widget: Literal["text", "textarea", "number", "money", "date", "checkbox", "select"]
    description: str = ""
    default: Any = None
    required: bool = True
    options: list[str] = Field(default_factory=list)
