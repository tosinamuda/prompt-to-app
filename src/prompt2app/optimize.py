from __future__ import annotations

import logging
import shutil
from pathlib import Path

import dspy

from prompt2app.claude_lm import make_lm
from prompt2app.evaluation import induction_metric, induction_metric_with_feedback
from prompt2app.induction import SignatureInducer
from prompt2app.schemas import AppSpec
from prompt2app.settings import get_settings
from prompt2app.store import load_corrections

log = logging.getLogger(__name__)

_inducer: SignatureInducer | None = None

_MIN_GEPA = 4
_MIN_BOOTSTRAP = 3


def _state_path() -> Path:
    return get_settings().data_dir / "inducer_state.json"


def _has_claude_cli() -> bool:
    return shutil.which("claude") is not None


def get_inducer() -> SignatureInducer:
    global _inducer
    if _inducer is None:
        _inducer = SignatureInducer()
        path = _state_path()
        if path.exists():
            try:
                _inducer.load(str(path))
                log.info("Loaded optimized inducer from %s", path)
            except Exception:
                log.warning("Failed to load inducer state; starting fresh", exc_info=True)
                _inducer = SignatureInducer()
    return _inducer


def _example(app: AppSpec) -> dspy.Example:
    return dspy.Example(
        raw_prompt=app.source_prompt,
        task_name=app.task_name,
        title=app.title,
        description=app.description,
        input_parameters=[f.model_dump() for f in app.inputs],
        program_outputs=[f.model_dump() for f in app.outputs],
        constraints=app.constraints,
    ).with_inputs("raw_prompt")


def optimize_from_corrections() -> tuple[int, str]:
    """Recompile the inducer from human corrections.

    Strategy (best to simplest):
      1. GEPA (>= 4 corrections + ``claude`` CLI available): rewrites the
         inducer's instructions by reflecting on failures.  Uses ``claude -p``
         (flat-fee subscription) as the reflection LM.
      2. BootstrapFewShot (>= 3 corrections): runs the inducer, keeps demos
         that pass the metric.
      3. LabeledFewShot (any count): attaches corrections as raw demos.

    Persists the optimized state so it survives restarts.
    """
    global _inducer
    corrections = [c for c in load_corrections() if c.source_prompt.strip()]
    if not corrections:
        return 0, "No corrections collected yet — nothing to optimize."

    trainset = [_example(c) for c in corrections]
    n = len(trainset)

    if n >= _MIN_GEPA and _has_claude_cli():
        _inducer, message = _optimize_gepa(trainset)
    elif n >= _MIN_BOOTSTRAP:
        _inducer, message = _optimize_bootstrap(trainset)
    else:
        _inducer, message = _optimize_fewshot(trainset)

    _save_inducer()
    return n, message


def _optimize_gepa(trainset: list) -> tuple[SignatureInducer, str]:
    n = len(trainset)
    split = max(1, n // 4)
    val, train = trainset[:split], trainset[split:]

    reflection_lm = make_lm("claude-cli/sonnet", max_thinking_tokens=4000)

    optimizer = dspy.GEPA(
        metric=induction_metric_with_feedback,
        reflection_lm=reflection_lm,
        auto="light",
        num_threads=1,
        track_stats=True,
    )
    try:
        compiled = optimizer.compile(
            student=SignatureInducer(), trainset=train, valset=val,
        )
        return compiled, (
            f"GEPA-optimized inducer from {n} correction(s) — "
            f"instructions rewritten via Claude reflection."
        )
    except Exception:
        log.warning("GEPA failed; falling back to BootstrapFewShot", exc_info=True)
        return _optimize_bootstrap(trainset)


def _optimize_bootstrap(trainset: list) -> tuple[SignatureInducer, str]:
    n = len(trainset)
    max_demos = min(4, n)
    optimizer = dspy.BootstrapFewShot(
        metric=induction_metric,
        max_bootstrapped_demos=max_demos,
        max_labeled_demos=max_demos,
    )
    try:
        compiled = optimizer.compile(student=SignatureInducer(), trainset=trainset)
        return compiled, (
            f"Bootstrapped inducer from {n} correction(s) — "
            f"kept demos that passed the induction metric."
        )
    except Exception:
        log.warning("BootstrapFewShot failed; falling back to LabeledFewShot", exc_info=True)
        return _optimize_fewshot(trainset)


def _optimize_fewshot(trainset: list) -> tuple[SignatureInducer, str]:
    k = min(8, len(trainset))
    optimizer = dspy.LabeledFewShot(k=k)
    compiled = optimizer.compile(student=SignatureInducer(), trainset=trainset)
    return compiled, f"Attached {k} demo(s) from {len(trainset)} correction(s) (few-shot)."


def _save_inducer() -> None:
    if _inducer is None:
        return
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _inducer.save(str(path))
        log.info("Saved inducer state to %s", path)
    except Exception:
        log.warning("Failed to save inducer state", exc_info=True)
