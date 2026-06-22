from types import SimpleNamespace

from prompt2app.evaluation import (
    field_prf,
    induction_metric,
    induction_metric_with_feedback,
    signature_validity,
    type_accuracy,
)
from prompt2app.schemas import AppSpec, InducedField


def test_field_prf_perfect_with_name_normalization():
    pred = [{"name": "issueTitle"}, {"name": "issue_description"}]
    gold = [{"name": "issue_title"}, {"name": "issue_description"}]
    assert field_prf(pred, gold).f1 == 1.0


def test_field_prf_partial_counts():
    prf = field_prf([{"name": "a"}, {"name": "b"}, {"name": "c"}], [{"name": "a"}, {"name": "b"}])
    assert (prf.tp, prf.fp, prf.fn) == (2, 1, 0)


def test_type_accuracy():
    pred = [{"name": "x", "type": "string"}, {"name": "y", "type": "integer"}]
    gold = [{"name": "x", "type": "string"}, {"name": "y", "type": "number"}]
    assert type_accuracy(pred, gold) == 0.5
    assert type_accuracy([{"name": "z"}], [{"name": "q"}]) is None  # no overlap


def test_signature_validity():
    valid = AppSpec(
        app_id="1", task_name="t", title="T", description="d",
        inputs=[InducedField(name="x", type="string")],
        outputs=[InducedField(name="y", type="text")],
    )
    no_out = AppSpec(
        app_id="1", task_name="t", title="T", description="d",
        inputs=[InducedField(name="x", type="string")], outputs=[],
    )
    assert signature_validity(valid) is True
    assert signature_validity(no_out) is False


def _gold_example():
    return SimpleNamespace(
        input_parameters=[
            {"name": "item", "type": "string"},
            {"name": "quantity", "type": "integer"},
        ],
        program_outputs=[{"name": "email_body", "type": "text"}],
    )


def test_induction_metric_perfect():
    pred = AppSpec(
        app_id="1", task_name="t", title="T", description="d",
        inputs=[
            InducedField(name="item", type="string"),
            InducedField(name="quantity", type="integer"),
        ],
        outputs=[InducedField(name="email_body", type="text")],
    )
    score = induction_metric(_gold_example(), pred)
    assert isinstance(score, float)
    assert score == 1.0


def test_induction_metric_partial():
    pred = AppSpec(
        app_id="1", task_name="t", title="T", description="d",
        inputs=[InducedField(name="item", type="string")],
        outputs=[InducedField(name="email_body", type="text")],
    )
    score = induction_metric(_gold_example(), pred)
    assert 0.0 < score < 1.0


def test_induction_metric_trace_strict():
    pred = AppSpec(
        app_id="1", task_name="t", title="T", description="d",
        inputs=[
            InducedField(name="item", type="string"),
            InducedField(name="quantity", type="integer"),
        ],
        outputs=[InducedField(name="email_body", type="text")],
    )
    assert induction_metric(_gold_example(), pred, trace="some_trace") is True

    bad = AppSpec(
        app_id="1", task_name="t", title="T", description="d",
        inputs=[], outputs=[],
    )
    assert induction_metric(_gold_example(), bad, trace="some_trace") is False


def test_feedback_metric_perfect_says_correct():
    pred = AppSpec(
        app_id="1", task_name="t", title="T", description="d",
        inputs=[
            InducedField(name="item", type="string"),
            InducedField(name="quantity", type="integer"),
        ],
        outputs=[InducedField(name="email_body", type="text")],
    )
    result = induction_metric_with_feedback(_gold_example(), pred)
    assert result.score == 1.0
    assert "correct" in result.feedback.lower()


def test_feedback_metric_missing_fields_described():
    pred = AppSpec(
        app_id="1", task_name="t", title="T", description="d",
        inputs=[InducedField(name="item", type="string")],
        outputs=[InducedField(name="email_body", type="text")],
    )
    result = induction_metric_with_feedback(_gold_example(), pred)
    assert result.score < 1.0
    assert "quantity" in result.feedback


def test_feedback_metric_wrong_type_described():
    pred = AppSpec(
        app_id="1", task_name="t", title="T", description="d",
        inputs=[
            InducedField(name="item", type="string"),
            InducedField(name="quantity", type="string"),
        ],
        outputs=[InducedField(name="email_body", type="text")],
    )
    result = induction_metric_with_feedback(_gold_example(), pred)
    assert "quantity" in result.feedback
    assert "'integer'" in result.feedback and "'string'" in result.feedback
