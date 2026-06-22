"""LLM-as-judge for schema quality — rates an induced schema on a rubric.

Runs on a separate judge LM (Sonnet via ``claude -p``) so it never evaluates its
own output. The rubric assesses whether the schema is a good abstraction of the
prompt, independent of any gold annotation.
"""

from __future__ import annotations

from typing import Literal

import dspy
from pydantic import BaseModel, Field, field_validator

Score = Literal[1, 2, 3, 4, 5]


class SchemaVerdict(BaseModel):
    """Quality verdict for an induced schema."""

    captures_variable_parts: Score = Field(
        description=(
            "Do the input fields capture every part of the prompt a user would "
            "reasonably want to change? 5 = every variable part is an input with "
            "a sensible default; 1 = critical knobs are missing or hallucinated."
        ),
    )
    output_completeness: Score = Field(
        description=(
            "Do the output fields cover what the program should produce? "
            "5 = outputs match the task's deliverables exactly; "
            "1 = outputs are missing, redundant, or misnamed."
        ),
    )
    type_precision: Score = Field(
        description=(
            "Is each field's type the most precise choice from "
            "{string, text, integer, number, money, date, boolean, enum}? "
            "5 = every type is the narrowest correct pick (e.g. 'money' not 'string' "
            "for a budget); 1 = types are generic or wrong."
        ),
    )
    field_naming: Score = Field(
        description=(
            "Are field names clear, descriptive snake_case identifiers a developer "
            "would choose? 5 = unambiguous, concise, conventional; "
            "1 = cryptic, redundant, or misleading names."
        ),
    )
    right_granularity: Score = Field(
        description=(
            "Is the number of fields appropriate — enough to be useful, few enough "
            "to stay simple? 5 = each field earns its place, no bloat; "
            "1 = too many micro-fields or too few mega-fields."
        ),
    )
    reasoning: str = Field(
        description="One sentence explaining the weakest dimension and how to fix it.",
    )

    @field_validator(
        "captures_variable_parts", "output_completeness",
        "type_precision", "field_naming", "right_granularity",
        mode="before",
    )
    @classmethod
    def _clamp_score(cls, v: int) -> int:
        return max(1, min(5, int(v)))

    @property
    def mean_score(self) -> float:
        total = (
            self.captures_variable_parts
            + self.output_completeness
            + self.type_precision
            + self.field_naming
            + self.right_granularity
        )
        return total / (5 * 5)


class RateSchemaQuality(dspy.Signature):
    """Rate how well a predicted schema abstracts a natural-language prompt into
    a reusable, parameterized program.

    The schema was produced by a system that reads a prompt and extracts typed
    input fields (what a user can change) and output fields (what the program
    produces). Judge the schema on its own merits — do not compare it to any
    reference answer.
    """

    original_prompt: str = dspy.InputField(
        desc="The raw natural-language prompt that was abstracted",
    )
    predicted_schema: str = dspy.InputField(
        desc="The induced inputs and outputs with their types",
    )
    verdict: SchemaVerdict = dspy.OutputField(
        desc="Quality scores across five dimensions, each 1-5",
    )


class SchemaJudge(dspy.Module):
    def __init__(self, judge_lm: dspy.BaseLM):
        super().__init__()
        self.judge_lm = judge_lm
        self.rate = dspy.ChainOfThought(RateSchemaQuality)

    def forward(self, original_prompt: str, predicted_schema: str) -> dspy.Prediction:
        with dspy.context(lm=self.judge_lm):
            return self.rate(
                original_prompt=original_prompt,
                predicted_schema=predicted_schema,
            )


def format_schema(app) -> str:
    lines = []
    lines.append("INPUTS:")
    for f in app.inputs:
        parts = [f"  {f.name}: {f.type}"]
        if f.options:
            parts.append(f" (options: {', '.join(f.options)})")
        if f.description:
            parts.append(f" — {f.description}")
        lines.append("".join(parts))
    lines.append("OUTPUTS:")
    for f in app.outputs:
        parts = [f"  {f.name}: {f.type}"]
        if f.description:
            parts.append(f" — {f.description}")
        lines.append("".join(parts))
    return "\n".join(lines)


def judge_score(pred: dspy.Prediction) -> float:
    verdict: SchemaVerdict = pred.verdict
    return verdict.mean_score
