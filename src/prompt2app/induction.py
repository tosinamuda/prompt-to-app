from __future__ import annotations

import dspy

from prompt2app.schemas import AppSpec, InducedField


class InduceAppSignature(dspy.Signature):
    """Compile a raw natural-language prompt into a reusable, parameterized LLM program.

    This is *parameter abstraction*, not entity extraction. Do not just tag entities.
    Decide which parts of the prompt should become reusable INPUT knobs the user can
    change, which parts are fixed task-defining CONSTRAINTS, and what typed OUTPUTS the
    program should produce.

    Reason in this order:
    1. Identify the underlying task (what is being produced?). Name it in snake_case.
    2. Lift every value a user might reasonably want to vary into an input field:
       entities (item, quantity), but also style/tone, audience, format, deadlines.
       Prefer fewer, meaningful knobs over one knob per word.
    3. Assign each input a type from this closed set:
       string, text, integer, number, money, date, boolean, enum.
       Use enum (with options) for closed choices like tone or priority.
    4. For each input, copy the concrete value present in the prompt into `value`
       (as a string) so the generated form is pre-filled. Leave null if absent.
    5. Define the typed outputs the program should return (e.g. email_subject, email_body).
    6. Capture non-parameterizable requirements as short imperative constraints
       (e.g. "mention the budget", "use a polite tone"). Do not duplicate inputs here.

    Do not invent fields ungrounded in the prompt or the task. Keep names snake_case.
    """

    raw_prompt: str = dspy.InputField(desc="The user's raw natural-language prompt.")

    task_name: str = dspy.OutputField(desc="snake_case task id, e.g. generate_supplier_email")
    title: str = dspy.OutputField(desc="Short human-readable title for the generated app.")
    description: str = dspy.OutputField(
        desc="One or two sentences describing what the program does. Becomes its instructions."
    )
    input_parameters: list[InducedField] = dspy.OutputField(
        desc="Reusable input knobs the user can change on each run — each with a snake_case name, a type from {string, text, integer, number, money, date, boolean, enum}, and optionally a default value lifted from the prompt."
    )
    program_outputs: list[InducedField] = dspy.OutputField(
        desc="Typed output slots the program produces. Each needs a clear snake_case name and a type. No default values."
    )
    constraints: list[str] = dspy.OutputField(
        desc="Short imperative requirements not captured as inputs."
    )


class SignatureInducer(dspy.Module):
    """Wraps the induction signature; supports loading learned demonstrations."""

    def __init__(self) -> None:
        super().__init__()
        self.induce = dspy.ChainOfThought(InduceAppSignature)

    def forward(self, raw_prompt: str) -> AppSpec:
        pred = self.induce(raw_prompt=raw_prompt)
        inputs = _clean_fields(pred.input_parameters, allow_values=True)
        outputs = _clean_fields(pred.program_outputs, allow_values=False)
        _disambiguate(inputs, outputs)
        return AppSpec(
            task_name=_slug(str(pred.task_name) or "generated_task"),
            title=str(pred.title) or "Generated App",
            description=str(pred.description),
            inputs=inputs,
            outputs=outputs,
            constraints=[str(c).strip() for c in (pred.constraints or []) if str(c).strip()],
            source_prompt=raw_prompt,
        )


def _clean_fields(raw: object, *, allow_values: bool) -> list[InducedField]:
    fields: list[InducedField] = []
    seen: set[str] = set()
    for item in raw or []:
        field = item if isinstance(item, InducedField) else InducedField.model_validate(item)
        field.name = _slug(field.name)
        if not field.name or field.name in seen:
            continue
        seen.add(field.name)
        if not allow_values:
            field.value = None
        if field.type == "enum":
            field.options = [str(o) for o in field.options if str(o).strip()]
            if not field.options:
                field.type = "string"
        fields.append(field)
    return fields


def _disambiguate(inputs: list[InducedField], outputs: list[InducedField]) -> None:
    """A dynamic signature keys fields by name, so an output may not reuse an input name."""
    input_names = {f.name for f in inputs}
    for f in outputs:
        if f.name in input_names:
            f.name = f"{f.name}_result"


def slug(name: object) -> str:
    """Public alias — normalize a field/task name to snake_case (used by eval + tests)."""
    return _slug(name)


def _slug(name: object) -> str:
    text = str(name or "").strip()
    # Split camelCase / PascalCase boundaries: "maxBudget" -> "max Budget".
    spaced = []
    for i, ch in enumerate(text):
        if i and ch.isupper() and (text[i - 1].islower() or text[i - 1].isdigit()):
            spaced.append(" ")
        spaced.append(ch)
    out = []
    for ch in "".join(spaced).lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in {" ", "-", "/", ".", "_"}:
            out.append("_")
    slug = "".join(out).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug
