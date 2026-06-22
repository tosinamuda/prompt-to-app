"""REST API: deterministic compile/run path for the web component and host SPA.

The host SPA can drive everything over A2A (LLM tool-calling), but these endpoints
guarantee the generated-UI flow works regardless of model tool-calling support, and
they back the generated app's REST fallback (like mcp-apps-demo's /webmcp surface).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from prompt2app import app_store
from prompt2app.compile_service import (
    build_envelope,
    compile_prompt,
    run,
    save_app_correction,
    surface,
)
from prompt2app.optimize import optimize_from_corrections
from prompt2app.retrieval import find_similar
from prompt2app.schemas import AppSpec

router = APIRouter(prefix="/api", tags=["prompt2app"])


class CompileRequest(BaseModel):
    prompt: str


class RetrieveRequest(BaseModel):
    prompt: str
    min_score: float = 0.5


class RunRequest(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)


class InputRequest(BaseModel):
    name: str
    value: Any


class CorrectionRequest(BaseModel):
    app: AppSpec


@router.post("/retrieve")
def retrieve_endpoint(req: RetrieveRequest) -> dict:
    """Find already-compiled apps similar to a prompt, so the user can reuse one."""
    matches = find_similar(req.prompt, min_score=req.min_score)
    return {"matches": [m.model_dump() for m in matches]}


@router.post("/compile")
def compile_endpoint(req: CompileRequest) -> dict:
    """Prompt -> compiled app. Returns the same structuredContent as the MCP tool."""
    app = compile_prompt(req.prompt)
    return build_envelope(app)["structuredContent"]


@router.get("/apps/{app_id}")
def get_surface(app_id: str) -> dict:
    app = app_store.get_app(app_id)
    if app is None:
        raise HTTPException(404, f"unknown app_id {app_id}")
    return surface(app)


@router.post("/apps/{app_id}/inputs")
def set_input(app_id: str, req: InputRequest) -> dict:
    if app_store.get_app(app_id) is None:
        raise HTTPException(404, f"unknown app_id {app_id}")
    return {"app_id": app_id, "values": app_store.set_input(app_id, req.name, req.value)}


@router.post("/apps/{app_id}/run")
def run_endpoint(app_id: str, req: RunRequest) -> dict:
    try:
        return run(app_id, req.inputs)
    except KeyError as exc:
        raise HTTPException(404, f"unknown app_id {app_id}") from exc


@router.post("/apps/{app_id}/correct")
def correct_endpoint(app_id: str, req: CorrectionRequest) -> dict:
    req.app.app_id = app_id
    save_app_correction(req.app)
    return {"status": "saved", "task_name": req.app.task_name}


@router.post("/optimize")
def optimize_endpoint() -> dict:
    n, message = optimize_from_corrections()
    return {"compiled": n > 0, "num_examples": n, "message": message}
