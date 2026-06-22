"""Approved-component registry + layout composer (the MCP-apps generative-UI model).

Like mcp-apps-demo, generated UI is a *declarative layout of pre-approved components*,
not arbitrary runtime markup. An induced AppSpec is compiled into a ComposedUi tree of
these components; the layout is validated against the registry before it is served.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, Field

from prompt2app.schemas import AppSpec


class ComponentDefinition(BaseModel):
    name: str
    description: str
    props_schema: dict[str, str] = Field(default_factory=dict)
    allowed_actions: list[str] = Field(default_factory=list)


class ActionDefinition(BaseModel):
    name: str
    label: str
    description: str
    method: str
    endpoint_template: str
    input_schema: dict[str, str] = Field(default_factory=dict)


class ComposedNode(BaseModel):
    component: str
    props: dict[str, object] = Field(default_factory=dict)
    children: list[ComposedNode] = Field(default_factory=list)


class ComposedUi(BaseModel):
    name: str
    description: str = ""
    root: ComposedNode


COMPONENTS: tuple[ComponentDefinition, ...] = (
    ComponentDefinition(
        name="p2a-app-frame",
        description="Iframe host shell for a compiled prompt app.",
        props_schema={"appId": "string", "title": "string", "src": "string"},
    ),
    ComponentDefinition(
        name="p2a-field",
        description="Typed input renderer backed by the induced signature.",
        props_schema={"appId": "string", "path": "string"},
        allowed_actions=["set_input"],
    ),
    ComponentDefinition(
        name="p2a-actions",
        description="Run / save-correction controls for the compiled program.",
        props_schema={"appId": "string"},
        allowed_actions=["run", "save_correction"],
    ),
    ComponentDefinition(
        name="p2a-output-panel",
        description="Renders the typed outputs produced by a run.",
        props_schema={"appId": "string"},
    ),
)

ACTIONS: tuple[ActionDefinition, ...] = (
    ActionDefinition(
        name="set_input",
        label="Set input",
        description="Stage one input value for the compiled program.",
        method="MCP",
        endpoint_template="set_app_input",
        input_schema={"app_id": "string", "name": "string", "value": "any"},
    ),
    ActionDefinition(
        name="run",
        label="Run program",
        description="Execute the compiled DSPy program with the staged inputs.",
        method="MCP",
        endpoint_template="run_app",
        input_schema={"app_id": "string"},
    ),
    ActionDefinition(
        name="save_correction",
        label="Save correction",
        description="Persist a human-corrected signature as training data.",
        method="MCP",
        endpoint_template="save_correction",
        input_schema={"app_id": "string"},
    ),
    ActionDefinition(
        name="optimize",
        label="Optimize inducer",
        description="Recompile the inducer from collected corrections.",
        method="MCP",
        endpoint_template="optimize_inducer",
        input_schema={},
    ),
)

_COMPONENT_NAMES = {c.name for c in COMPONENTS}
_ACTION_NAMES = {a.name for a in ACTIONS}


def compose_layout(app: AppSpec, app_url: str) -> ComposedUi:
    """Compile an induced AppSpec into a validated layout of approved components."""
    layout = ComposedUi(
        name=f"{app.task_name}-ui",
        description=f"Generated UI for {app.title}.",
        root=ComposedNode(
            component="p2a-app-frame",
            props={"appId": app.app_id, "title": app.title, "src": app_url},
            children=[
                ComposedNode(component="p2a-field", props={"appId": app.app_id, "path": "*"}),
                ComposedNode(component="p2a-actions", props={"appId": app.app_id}),
                ComposedNode(component="p2a-output-panel", props={"appId": app.app_id}),
            ],
        ),
    )
    validate_layout(layout)
    return layout


def selected_component_names(layout: ComposedUi) -> list[str]:
    return sorted({node.component for node in _walk(layout.root)})


def selected_action_names(layout: ComposedUi) -> list[str]:
    by_name = {c.name: c for c in COMPONENTS}
    actions: set[str] = set()
    for node in _walk(layout.root):
        actions.update(by_name[node.component].allowed_actions)
    return sorted(actions)


def validate_layout(layout: ComposedUi) -> None:
    for node in _walk(layout.root):
        if node.component not in _COMPONENT_NAMES:
            raise ValueError(f"Unknown component in composed UI: {node.component}")
        component = next(c for c in COMPONENTS if c.name == node.component)
        unknown = set(component.allowed_actions) - _ACTION_NAMES
        if unknown:
            raise ValueError(f"Unknown action(s) for {component.name}: {sorted(unknown)}")


def _walk(root: ComposedNode) -> Iterable[ComposedNode]:
    yield root
    for child in root.children:
        yield from _walk(child)
