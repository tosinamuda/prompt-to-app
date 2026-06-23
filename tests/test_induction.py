from prompt2app.induction import (
    InduceAppSignature,
    SignatureInducer,
    _clean_fields,
    _disambiguate,
    slug,
)
from prompt2app.schemas import InducedField


def test_slug_camelcase_and_separators():
    assert slug("maxBudget") == "max_budget"
    assert slug("Service Name") == "service_name"
    assert slug("logs/destination") == "logs_destination"
    assert slug("issueTitle") == "issue_title"
    assert slug("  Already_snake ") == "already_snake"


def test_clean_fields_dedup_and_enum_without_options():
    raw = [
        {"name": "a", "type": "string"},
        {"name": "A", "type": "string"},  # dup after slug -> dropped
        {"name": "mode", "type": "enum", "options": []},  # enum w/o options -> string
        {"name": "x", "type": "enum", "options": ["p", "q"]},
    ]
    fields = _clean_fields(raw, allow_values=True)
    assert [f.name for f in fields] == ["a", "mode", "x"]
    assert next(f for f in fields if f.name == "mode").type == "string"
    assert next(f for f in fields if f.name == "x").options == ["p", "q"]


def test_clean_fields_outputs_drop_values():
    fields = _clean_fields([{"name": "out", "type": "string", "value": "v"}], allow_values=False)
    assert fields[0].value is None


def test_disambiguate_renames_output_colliding_with_input():
    inputs = [InducedField(name="title", type="string")]
    outputs = [InducedField(name="title", type="string")]
    _disambiguate(inputs, outputs)
    assert outputs[0].name == "title_result"


def test_granularity_hint_appended_to_instructions():
    inducer = SignatureInducer(granularity_hint="Extract only one field.")
    signature = inducer.induce.predict.signature
    assert "GRANULARITY DIRECTIVE: Extract only one field." in signature.instructions
    # The base task instructions and field names (prompt tokens) are preserved.
    assert InduceAppSignature.instructions in signature.instructions
    assert "input_parameters" in signature.output_fields


def test_no_hint_leaves_base_signature_unchanged():
    signature = SignatureInducer().induce.predict.signature
    assert signature.instructions == InduceAppSignature.instructions
