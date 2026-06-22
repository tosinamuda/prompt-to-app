"""Unit tests for the LLM judge — pure logic only, no LM calls."""

from types import SimpleNamespace

from prompt2app.llm_judge import SchemaVerdict, format_schema, judge_score
from prompt2app.schemas import AppSpec, InducedField


def test_format_schema_includes_fields():
    app = AppSpec(
        app_id="1", task_name="t", title="T", description="d",
        inputs=[
            InducedField(name="item", type="string"),
            InducedField(name="priority", type="enum", options=["low", "medium", "high"]),
        ],
        outputs=[InducedField(name="email_body", type="text")],
    )
    text = format_schema(app)
    assert "item: string" in text
    assert "priority: enum (options: low, medium, high)" in text
    assert "email_body: text" in text
    assert "INPUTS:" in text
    assert "OUTPUTS:" in text


def test_verdict_mean_score_perfect():
    v = SchemaVerdict(
        captures_variable_parts=5, output_completeness=5,
        type_precision=5, field_naming=5, right_granularity=5,
        reasoning="Perfect.",
    )
    assert v.mean_score == 1.0


def test_verdict_mean_score_mid():
    v = SchemaVerdict(
        captures_variable_parts=3, output_completeness=3,
        type_precision=3, field_naming=3, right_granularity=3,
        reasoning="OK.",
    )
    assert v.mean_score == 0.6


def test_verdict_clamps_out_of_range():
    v = SchemaVerdict(
        captures_variable_parts=0, output_completeness=6,
        type_precision=3, field_naming=3, right_granularity=3,
        reasoning="Edge case.",
    )
    assert v.captures_variable_parts == 1
    assert v.output_completeness == 5
    assert v.mean_score == (1 + 5 + 3 + 3 + 3) / 25


def test_judge_score_uses_verdict():
    v = SchemaVerdict(
        captures_variable_parts=4, output_completeness=4,
        type_precision=4, field_naming=4, right_granularity=4,
        reasoning="Good.",
    )
    pred = SimpleNamespace(verdict=v)
    assert judge_score(pred) == 0.8
