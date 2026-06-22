from __future__ import annotations

import json
from pathlib import Path

from prompt2app.schemas import AppSpec
from prompt2app.settings import get_settings


def _data_dir() -> Path:
    d = get_settings().data_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def _apps_path() -> Path:
    return _data_dir() / "apps.jsonl"


def _corrections_path() -> Path:
    return _data_dir() / "corrections.jsonl"


def save_app(app: AppSpec) -> None:
    _append(_apps_path(), app.model_dump())


def save_correction(app: AppSpec) -> None:
    """Persist a human-corrected spec as a training example for the inducer."""
    _append(_corrections_path(), app.model_dump())


def load_corrections() -> list[AppSpec]:
    return [AppSpec.model_validate(row) for row in _read(_corrections_path())]


def _append(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows
