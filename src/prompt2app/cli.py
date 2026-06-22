from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn


def app_dev() -> None:
    run_server(default_reload=True)


def app_start() -> None:
    run_server(default_reload=False)


def run_server(*, default_reload: bool) -> None:
    parser = argparse.ArgumentParser(description="Run the Prompt2App workbench.")
    parser.add_argument("--host", default=os.getenv("APP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=default_reload,
        help="Reload the server when source files change.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(os.getenv("UVICORN_ENV_FILE", ".env")),
    )
    args = parser.parse_args()
    uvicorn.run(
        "prompt2app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=["src"] if args.reload else None,
        env_file=args.env_file if args.env_file.exists() else None,
    )
