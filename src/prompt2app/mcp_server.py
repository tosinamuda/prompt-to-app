"""FastMCP server exposing the prompt compiler as MCP Apps (generative UI).

Mirrors mcp-apps-demo: a UI resource (HTML loading approved web components) plus
tools whose results carry that resource + structured layout metadata. Any MCP host
(ChatGPT, or our own A2A agent) can call `compile_prompt` and render the generated app.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from fastmcp import FastMCP
from fastmcp.apps import UI_MIME_TYPE, AppConfig, ResourceCSP
from fastmcp.tools import ToolResult

from prompt2app import app_store
from prompt2app.compile_service import (
    P2A_UI_URI,
    app_html,
    build_envelope,
)
from prompt2app.compile_service import (
    compile_prompt as _compile_prompt,
)
from prompt2app.compile_service import (
    run as _run,
)
from prompt2app.compile_service import (
    surface as _surface,
)
from prompt2app.optimize import optimize_from_corrections
from prompt2app.retrieval import find_similar
from prompt2app.settings import get_settings

mcp = FastMCP("Prompt2App Compiler")
ESM_SH_ORIGIN = "https://esm.sh"


def _origin(url: str) -> str:
    parsed = urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _resource_app_config() -> AppConfig:
    origin = _origin(get_settings().app_base_url)
    return AppConfig(
        csp=ResourceCSP(
            connect_domains=[origin],
            resource_domains=[origin, ESM_SH_ORIGIN],
        ),
        prefers_border=True,
    )


def _resource_meta(description: str) -> dict[str, Any]:
    origin = _origin(get_settings().app_base_url)
    return {
        "openai/widgetDescription": description,
        "openai/widgetPrefersBorder": True,
        "openai/widgetCSP": {
            "connect_domains": [origin],
            "resource_domains": [origin, ESM_SH_ORIGIN],
        },
    }


def _to_tool_result(envelope: dict[str, Any]) -> ToolResult:
    return ToolResult(
        content=envelope["content"],
        structured_content=envelope["structuredContent"],
        meta=envelope.get("_meta"),
    )


@mcp.resource(
    P2A_UI_URI,
    mime_type=UI_MIME_TYPE,
    app=_resource_app_config(),
    meta=_resource_meta("Interactive generated app compiled from a natural-language prompt."),
)
def prompt2app_ui() -> str:
    return app_html()


@mcp.tool(
    app=AppConfig(resource_uri=P2A_UI_URI, visibility=["model", "app"]),
    meta={
        "openai/outputTemplate": P2A_UI_URI,
        "openai/widgetAccessible": True,
        "openai/toolInvocation/invoking": "Compiling prompt into an app",
        "openai/toolInvocation/invoked": "App compiled",
    },
)
async def compile_prompt(prompt: str) -> ToolResult:
    """Compile a natural-language prompt into a reusable, typed app and return its UI."""
    app = _compile_prompt(prompt)
    return _to_tool_result(build_envelope(app))


@mcp.tool(app=AppConfig(visibility=["model", "app"]))
async def find_similar_apps(prompt: str) -> dict:
    """Find already-compiled apps similar to a prompt; reuse one instead of compiling anew."""
    return {"matches": [m.model_dump() for m in find_similar(prompt)]}


@mcp.tool(app=AppConfig(visibility=["model", "app"]))
async def get_app(app_id: str) -> dict:
    """Return the render-ready surface (fields, outputs, staged values) for a compiled app."""
    app = app_store.get_app(app_id)
    if app is None:
        return {"error": f"unknown app_id {app_id}"}
    return _surface(app)


@mcp.tool(app=AppConfig(visibility=["model", "app"]))
async def set_app_input(app_id: str, name: str, value: str | int | float | bool) -> dict:
    """Stage one input value for a compiled app."""
    values = app_store.set_input(app_id, name, value)
    return {"app_id": app_id, "values": values}


@mcp.tool(app=AppConfig(visibility=["model", "app"]))
async def run_app(app_id: str, inputs: dict[str, Any] | None = None) -> dict:
    """Execute the compiled DSPy program for a compiled app and return typed outputs."""
    try:
        return _run(app_id, inputs)
    except KeyError:
        return {"error": f"unknown app_id {app_id}"}


@mcp.tool(app=AppConfig(visibility=["model", "app"]))
async def optimize_inducer() -> dict:
    """Recompile the inducer from collected human corrections."""
    n, message = optimize_from_corrections()
    return {"compiled": n > 0, "num_examples": n, "message": message}


__all__ = ["mcp"]
