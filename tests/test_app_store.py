from prompt2app import app_store
from prompt2app.schemas import AppSpec, InducedField


def _reset(monkeypatch, tmp_path):
    monkeypatch.setattr(app_store, "_apps", {})
    monkeypatch.setattr(app_store, "_inputs", {})
    monkeypatch.setattr(app_store, "_loaded", True)  # skip disk load
    monkeypatch.setattr(app_store, "_apps_path", lambda: tmp_path / "apps.jsonl")


def _spec(name="t") -> AppSpec:
    return AppSpec(
        app_id="",
        task_name=name,
        title="T",
        description="d",
        inputs=[InducedField(name="x", type="string", value="v")],
        outputs=[InducedField(name="y", type="text")],
    )


def test_put_get_all_roundtrip(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path)
    app = app_store.put_app(_spec())
    assert app.app_id  # auto-assigned
    assert app_store.get_app(app.app_id) is app
    assert len(app_store.all_apps()) == 1
    assert app_store.staged_inputs(app.app_id)["x"] == "v"  # seeded from field value
    assert (tmp_path / "apps.jsonl").exists()


def test_set_input_updates_staged(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path)
    app = app_store.put_app(_spec())
    vals = app_store.set_input(app.app_id, "x", "new")
    assert vals["x"] == "new"
    assert app_store.staged_inputs(app.app_id)["x"] == "new"
