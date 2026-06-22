from prompt2app.compiler import build_form, build_signature
from prompt2app.schemas import AppSpec, InducedField


def _spec() -> AppSpec:
    return AppSpec(
        app_id="t1",
        task_name="gen_email",
        title="Generate email",
        description="Make an email",
        inputs=[
            InducedField(name="item", type="string", value="laptops"),
            InducedField(name="qty", type="integer", value="20"),
            InducedField(name="budget", type="money", value="30000"),
            InducedField(name="tone", type="enum", options=["polite", "direct"], value="polite"),
            InducedField(name="urgent", type="boolean", value="true"),
        ],
        outputs=[
            InducedField(name="subject", type="string"),
            InducedField(name="body", type="text"),
        ],
        constraints=["mention the budget"],
    )


def test_build_signature_has_expected_fields_and_constraints():
    sig = build_signature(_spec())
    assert set(sig.input_fields) == {"item", "qty", "budget", "tone", "urgent"}
    assert set(sig.output_fields) == {"subject", "body"}
    assert "mention the budget" in sig.instructions


def test_build_form_maps_widgets_and_defaults():
    form = {w.name: w for w in build_form(_spec())}
    assert form["item"].widget == "text"
    assert form["qty"].widget == "number" and form["qty"].default == 20
    assert form["budget"].widget == "money" and form["budget"].default == 30000.0
    assert form["tone"].widget == "select" and form["tone"].options == ["polite", "direct"]
    assert form["urgent"].widget == "checkbox" and form["urgent"].default is True


def test_unparseable_money_default_is_none():
    spec = _spec()
    spec.inputs[2].value = "$30k"  # not numeric -> default None
    form = {w.name: w for w in build_form(spec)}
    assert form["budget"].default is None
