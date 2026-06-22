from __future__ import annotations

import logging
import warnings
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from prompt2app.api import router as api_router
from prompt2app.compile_service import app_html
from prompt2app.lm import configure_dspy_lm
from prompt2app.settings import get_settings

warnings.filterwarnings("ignore", message=r".*\[EXPERIMENTAL\].*", category=UserWarning)
logging.getLogger("dspy.predict.predict").setLevel(logging.ERROR)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    settings = get_settings()
    configure_dspy_lm(settings)

    # Build the MCP (FastMCP) and A2A (ADK) sub-apps. MCP's http_app carries the
    # lifespan the FastAPI app must adopt.
    from prompt2app.mcp_server import mcp

    mcp_app = mcp.http_app(path="/")

    app = FastAPI(
        title="Prompt2App — Prompt Compiler (MCP Apps + A2A)",
        version="0.2.0",
        lifespan=mcp_app.lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _no_store(request, call_next):
        # The generated-app bundle + shell change during development; never cache them.
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/static/") or path == "/app":
            response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    app.include_router(api_router)
    app.mount("/mcp", mcp_app)

    try:
        from prompt2app.a2a_agent import build_a2a_app

        app.mount("/a2a", build_a2a_app(settings))
        logging.getLogger(__name__).info("A2A agent mounted at /a2a")
    except Exception as exc:  # keep MCP + REST working even if A2A fails to build
        logging.getLogger(__name__).warning("A2A agent not mounted: %s", exc)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "agent": settings.app_name, "model": settings.lm_model}

    @app.api_route("/app", methods=["GET", "HEAD"])
    def generated_app() -> HTMLResponse:
        return HTMLResponse(app_html())

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        return Response(status_code=204)

    return app


app = create_app()
