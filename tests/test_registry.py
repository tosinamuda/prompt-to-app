import pytest

from prompt2app.registry import (
    ComposedNode,
    ComposedUi,
    compose_layout,
    selected_action_names,
    selected_component_names,
    validate_layout,
)
from prompt2app.schemas import AppSpec, InducedField


def _spec() -> AppSpec:
    return AppSpec(
        app_id="a1",
        task_name="t",
        title="T",
        description="d",
        inputs=[InducedField(name="x", type="string")],
        outputs=[InducedField(name="y", type="text")],
    )


def test_compose_layout_is_valid_and_uses_approved_components():
    layout = compose_layout(_spec(), "/app?app_id=a1")
    comps = selected_component_names(layout)
    assert {"p2a-app-frame", "p2a-field", "p2a-actions", "p2a-output-panel"} <= set(comps)
    acts = selected_action_names(layout)
    assert "run" in acts and "set_input" in acts


def test_validate_layout_rejects_unknown_component():
    bad = ComposedUi(name="x", root=ComposedNode(component="not-a-real-component"))
    with pytest.raises(ValueError):
        validate_layout(bad)
