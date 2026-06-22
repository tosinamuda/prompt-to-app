"""In-memory registry of compiled apps + staged inputs, backed by data/apps.jsonl.

Avoids a database dependency (mcp-apps-demo uses Postgres; we keep it in-process).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from prompt2app.schemas import AppSpec
from prompt2app.settings import get_settings

_apps: dict[str, AppSpec] = {}
_inputs: dict[str, dict[str, Any]] = {}
_loaded = False


def _apps_path():
    d = get_settings().data_dir
    d.mkdir(parents=True, exist_ok=True)
    return d / "apps.jsonl"


def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    path = _apps_path()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                app = AppSpec.model_validate(json.loads(line))
            except Exception:
                continue
            if app.app_id:
                _apps[app.app_id] = app
    _loaded = True


def new_app_id() -> str:
    return uuid.uuid4().hex[:12]


def put_app(app: AppSpec) -> AppSpec:
    _ensure_loaded()
    if not app.app_id:
        app.app_id = new_app_id()
    _apps[app.app_id] = app
    _inputs.setdefault(app.app_id, {f.name: (f.value or "") for f in app.inputs})
    with _apps_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(app.model_dump(), ensure_ascii=False) + "\n")
    return app


def get_app(app_id: str) -> AppSpec | None:
    _ensure_loaded()
    return _apps.get(app_id)


def all_apps() -> list[AppSpec]:
    _ensure_loaded()
    return list(_apps.values())


def staged_inputs(app_id: str) -> dict[str, Any]:
    _ensure_loaded()
    return dict(_inputs.get(app_id, {}))


def set_input(app_id: str, name: str, value: Any) -> dict[str, Any]:
    _ensure_loaded()
    current = _inputs.setdefault(app_id, {})
    current[name] = value
    return dict(current)
