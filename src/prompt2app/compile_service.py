"""Shared business logic for compiling prompts and running compiled apps.

Used by both the MCP server (tool results carrying UI resources) and the REST API
(deterministic path for the web component + host SPA).
"""

from __future__ import annotations

from typing import Any

from prompt2app import app_store
from prompt2app.compiler import build_form, build_output_panels
from prompt2app.optimize import get_inducer
from prompt2app.registry import (
    ACTIONS,
    compose_layout,
    selected_action_names,
    selected_component_names,
)
from prompt2app.runner import run_app as _run_program
from prompt2app.schemas import AppSpec
from prompt2app.settings import get_settings
from prompt2app.store import save_correction

P2A_UI_URI = "ui://prompt2app/app.html"


def app_url(app_id: str) -> str:
    base = get_settings().app_base_url.rstrip("/")
    return f"{base}/app?app_id={app_id}"


def _asset_version(filename: str) -> int:
    """mtime of a static asset, used as a cache-busting query so edits take effect."""
    from pathlib import Path

    try:
        return int((Path(__file__).resolve().parent / "static" / filename).stat().st_mtime)
    except OSError:
        return 0


def app_html() -> str:
    """The generated-app shell: loads the approved web-component bundle.

    Served both as the MCP UI resource (for real MCP hosts) and at /app (for the
    host SPA to embed as an iframe)."""
    base = get_settings().app_base_url.rstrip("/")
    css_v = _asset_version("p2a.css")
    js_v = _asset_version("p2a-app.js")
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Prompt2App generated app</title>
    <link rel="stylesheet" href="{base}/static/p2a.css?v={css_v}" />
    <script type="module" src="{base}/static/p2a-app.js?v={js_v}"></script>
  </head>
  <body>
    <p2a-app api-base="{base}"></p2a-app>
  </body>
</html>
"""


def compile_prompt(prompt: str) -> AppSpec:
    """Induce a typed signature from a prompt and register it as a compiled app."""
    app = get_inducer()(prompt)
    app.app_id = app_store.new_app_id()
    return app_store.put_app(app)


def surface(app: AppSpec) -> dict[str, Any]:
    """Render-ready description the web component uses to draw the generated UI."""
    return {
        "app_id": app.app_id,
        "task_name": app.task_name,
        "title": app.title,
        "description": app.description,
        "constraints": app.constraints,
        "fields": [w.model_dump() for w in build_form(app)],
        "outputs": [w.model_dump() for w in build_output_panels(app)],
        "values": app_store.staged_inputs(app.app_id),
        "spec": app.model_dump(),  # full AppSpec, for the host's signature view / corrections
        "actions": [
            {"name": a.name, "label": a.label}
            for a in ACTIONS
            if a.name in {"run", "save_correction"}
        ],
    }


def build_envelope(app: AppSpec) -> dict[str, Any]:
    """MCP-apps tool-result envelope: content + structuredContent + _meta."""
    from fastmcp.apps import UI_MIME_TYPE
    from mcp.types import ResourceLink, TextContent

    url = app_url(app.app_id)
    layout = compose_layout(app, url)
    return {
        "content": [
            TextContent(
                type="text",
                text=(
                    f"Compiled '{app.title}' into a reusable program with "
                    f"{len(app.inputs)} inputs and {len(app.outputs)} outputs. "
                    "Open the generated app to fill it in and run it."
                ),
            ),
            ResourceLink(
                type="resource_link",
                uri=P2A_UI_URI,
                name=app.title,
                mimeType=UI_MIME_TYPE,
            ),
        ],
        "structuredContent": {
            "app_id": app.app_id,
            "task_name": app.task_name,
            "service_title": app.title,
            "app_url": url,
            "layout": layout.model_dump(mode="json"),
            "selected_components": selected_component_names(layout),
            "selected_actions": selected_action_names(layout),
            "surface": surface(app),
        },
        "_meta": {
            "ui": {"resourceUri": P2A_UI_URI},
            "openai/outputTemplate": P2A_UI_URI,
            "openai/widgetAccessible": True,
            "openai/toolInvocation/invoking": f"Compiling '{app.title}'",
            "openai/toolInvocation/invoked": f"'{app.title}' compiled",
        },
    }


def run(app_id: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    app = app_store.get_app(app_id)
    if app is None:
        raise KeyError(app_id)
    merged = app_store.staged_inputs(app_id)
    merged.update(inputs or {})
    outputs = _run_program(app, merged)
    return {"app_id": app_id, "outputs": outputs}


def save_app_correction(app: AppSpec) -> None:
    if not app.app_id:
        app.app_id = app_store.new_app_id()
    app_store.put_app(app)
    save_correction(app)
