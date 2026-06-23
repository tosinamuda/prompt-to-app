"""Induction-quality metrics — the research instrument's measurement layer.

Pure functions comparing an induced AppSpec against a gold abstraction. These back the
eval harness (scripts/eval.py) and are unit-tested offline. They match fields first by
exact normalized name, then by semantic similarity of the name text (via fastembed) to
handle synonymous names like ``paper_content``/``paper_text``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from prompt2app.compiler import build_signature
from prompt2app.induction import slug
from prompt2app.schemas import AppSpec

log = logging.getLogger(__name__)

_SEMANTIC_THRESHOLD = 0.70


def _names(fields: list[dict[str, Any]]) -> set[str]:
    return {slug(f.get("name")) for f in fields if f.get("name")}


def _match_field_names(
    pred_names: set[str], gold_names: set[str],
) -> tuple[set[str], dict[str, str]]:
    """Match predicted field names to gold, exact first then semantic.

    Returns (exact_matches, semantic_map) where semantic_map is pred→gold.
    """
    exact = pred_names & gold_names
    remaining_pred = sorted(pred_names - exact)
    remaining_gold = sorted(gold_names - exact)

    semantic: dict[str, str] = {}
    if remaining_pred and remaining_gold:
        try:
            semantic = _greedy_semantic_match(remaining_pred, remaining_gold)
        except Exception:
            log.debug("Semantic field matching unavailable", exc_info=True)

    return exact, semantic


def _greedy_semantic_match(pred: list[str], gold: list[str]) -> dict[str, str]:
    from prompt2app.retrieval import _cosine, _embed

    pred_text = [p.replace("_", " ") for p in pred]
    gold_text = [g.replace("_", " ") for g in gold]

    all_vecs = _embed(pred_text + gold_text)
    pred_vecs = all_vecs[: len(pred)]
    gold_vecs = all_vecs[len(pred) :]

    pairs = []
    for i, pv in enumerate(pred_vecs):
        for j, gv in enumerate(gold_vecs):
            sim = _cosine(pv, gv)
            if sim >= _SEMANTIC_THRESHOLD:
                pairs.append((sim, i, j))

    pairs.sort(reverse=True)
    used_pred: set[int] = set()
    used_gold: set[int] = set()
    matched: dict[str, str] = {}
    for _sim, i, j in pairs:
        if i not in used_pred and j not in used_gold:
            matched[pred[i]] = gold[j]
            used_pred.add(i)
            used_gold.add(j)

    return matched


@dataclass
class PRF:
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int


def field_prf(pred: list[dict[str, Any]], gold: list[dict[str, Any]]) -> PRF:
    """Precision/recall/F1 over field names (exact + semantic matching)."""
    p, g = _names(pred), _names(gold)
    exact, semantic = _match_field_names(p, g)
    tp = len(exact) + len(semantic)
    fp = len(p) - tp
    fn = len(g) - tp
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return PRF(precision, recall, f1, tp, fp, fn)


def type_accuracy(pred: list[dict[str, Any]], gold: list[dict[str, Any]]) -> float | None:
    """Fraction of correctly-typed fields, over names matched (exact or semantic)."""
    gt = {slug(f["name"]): f.get("type") for f in gold if f.get("name")}
    pt = {slug(f["name"]): f.get("type") for f in pred if f.get("name")}

    exact, semantic = _match_field_names(set(pt), set(gt))

    matched_pairs: list[tuple[str, str]] = [(n, n) for n in exact]
    matched_pairs.extend(semantic.items())

    if not matched_pairs:
        return None
    correct = sum(1 for pred_n, gold_n in matched_pairs if pt[pred_n] == gt[gold_n])
    return correct / len(matched_pairs)


def signature_validity(app: AppSpec) -> bool:
    """Does the induced spec compile into a usable program (>=1 input, >=1 output)?"""
    if not app.inputs or not app.outputs:
        return False
    try:
        build_signature(app)
        return True
    except Exception:
        return False


@dataclass
class ReuseScore:
    """How many follow-up task variants a compiled form can serve without recompiling."""

    binary: float  # fraction of variants whose every required field is present
    graded: float  # mean fraction of each variant's required fields present
    n_variants: int


def reuse_coverage(pred_inputs: list[dict[str, Any]], variants: list[dict[str, Any]]) -> ReuseScore:
    """Does the form's set of input knobs cover what realistic rephrasings need?

    A variant is *fully covered* when every field it requires matches an input in the
    form (exact or semantic name match). ``binary`` is the fraction of fully-covered
    variants; ``graded`` is the mean per-variant fraction of required fields present.
    More input fields tend to raise coverage — the cost side of the granularity trade.
    """
    form_names = _names(pred_inputs)
    covered = 0
    graded_total = 0.0
    counted = 0
    for variant in variants:
        required = {slug(n) for n in variant.get("required_inputs", []) if n}
        if not required:
            continue
        counted += 1
        exact, semantic = _match_field_names(required, form_names)
        matched = exact | set(semantic)
        graded_total += len(matched) / len(required)
        if matched >= required:
            covered += 1
    if not counted:
        return ReuseScore(binary=0.0, graded=0.0, n_variants=0)
    return ReuseScore(binary=covered / counted, graded=graded_total / counted, n_variants=counted)


@dataclass
class CaseScore:
    inputs: PRF
    outputs: PRF
    input_type_accuracy: float | None
    valid: bool


def score_case(app: AppSpec, gold: dict[str, Any]) -> CaseScore:
    return CaseScore(
        inputs=field_prf([f.model_dump() for f in app.inputs], gold.get("inputs", [])),
        outputs=field_prf([f.model_dump() for f in app.outputs], gold.get("outputs", [])),
        input_type_accuracy=type_accuracy(
            [f.model_dump() for f in app.inputs], gold.get("inputs", [])
        ),
        valid=signature_validity(app),
    )


def mean(values: list[float]) -> float:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else 0.0


def _score_induction(example, pred):
    """Shared scoring logic for both metric variants."""
    gold_inputs = getattr(example, "input_parameters", []) or []
    gold_outputs = getattr(example, "program_outputs", []) or []

    pred_inputs = [f.model_dump() for f in pred.inputs]
    pred_outputs = [f.model_dump() for f in pred.outputs]

    in_prf = field_prf(pred_inputs, gold_inputs)
    out_prf = field_prf(pred_outputs, gold_outputs)
    type_acc = type_accuracy(pred_inputs, gold_inputs)
    valid = signature_validity(pred)

    field_score = (in_prf.f1 + out_prf.f1) / 2
    type_score = type_acc if type_acc is not None else 1.0
    validity_penalty = 1.0 if valid else 0.0

    score = 0.5 * field_score + 0.3 * type_score + 0.2 * validity_penalty

    problems: list[str] = []
    gold_in_names = _names(gold_inputs)
    pred_in_names = _names(pred_inputs)
    gold_out_names = _names(gold_outputs)
    pred_out_names = _names(pred_outputs)

    _, sem_in = _match_field_names(pred_in_names, gold_in_names)
    _, sem_out = _match_field_names(pred_out_names, gold_out_names)
    matched_in = (pred_in_names & gold_in_names) | set(sem_in)
    matched_out = (pred_out_names & gold_out_names) | set(sem_out)
    matched_gold_in = (pred_in_names & gold_in_names) | set(sem_in.values())
    matched_gold_out = (pred_out_names & gold_out_names) | set(sem_out.values())

    missing_in = gold_in_names - matched_gold_in
    extra_in = pred_in_names - matched_in
    missing_out = gold_out_names - matched_gold_out
    extra_out = pred_out_names - matched_out

    if missing_in:
        problems.append(f"missing input fields: {', '.join(sorted(missing_in))}")
    if extra_in:
        problems.append(f"extra input fields: {', '.join(sorted(extra_in))}")
    if missing_out:
        problems.append(f"missing output fields: {', '.join(sorted(missing_out))}")
    if extra_out:
        problems.append(f"extra output fields: {', '.join(sorted(extra_out))}")
    if type_acc is not None and type_acc < 1.0:
        gt = {slug(f["name"]): f.get("type") for f in gold_inputs if f.get("name")}
        pt = {slug(f["name"]): f.get("type") for f in pred_inputs if f.get("name")}
        all_pairs = [(n, n) for n in set(gt) & set(pt)]
        all_pairs.extend(sem_in.items())
        for pred_n, gold_n in sorted(all_pairs):
            if pt.get(pred_n) and gt.get(gold_n) and pt[pred_n] != gt[gold_n]:
                problems.append(
                    f"wrong type for '{gold_n}': got '{pt[pred_n]}', expected '{gt[gold_n]}'"
                )
    if not valid:
        problems.append("signature is invalid (cannot compile into a runnable program)")

    return score, field_score, valid, problems


def induction_metric(example, pred, trace=None) -> float | bool:
    """DSPy-compatible metric for BootstrapFewShot optimization."""
    score, field_score, valid, _ = _score_induction(example, pred)
    if trace is not None:
        return field_score >= 0.5 and valid
    return score


def induction_metric_with_feedback(example, pred, trace=None, pred_name=None, pred_trace=None):
    """Feedback-rich metric for GEPA — returns Prediction so GEPA reflects on the text.

    The feedback includes the raw prompt, field-by-field comparison with semantic
    near-misses shown as naming corrections, and type guidance. This gives GEPA's
    reflection LM enough context to write targeted instruction improvements.
    """
    import dspy

    score, _, _, _ = _score_induction(example, pred)

    gold_inputs = getattr(example, "input_parameters", []) or []
    gold_outputs = getattr(example, "program_outputs", []) or []
    pred_inputs = [f.model_dump() for f in pred.inputs]
    pred_outputs = [f.model_dump() for f in pred.outputs]

    feedback = _build_gepa_feedback(
        getattr(example, "raw_prompt", ""),
        pred_inputs, gold_inputs,
        pred_outputs, gold_outputs,
    )
    return dspy.Prediction(score=score, feedback=feedback)


def _build_gepa_feedback(
    raw_prompt: str,
    pred_inputs: list[dict], gold_inputs: list[dict],
    pred_outputs: list[dict], gold_outputs: list[dict],
) -> str:
    header = f'Prompt: "{raw_prompt[:150]}"' if raw_prompt else ""
    issues: list[str] = []

    gt_in = {slug(f["name"]): f.get("type") for f in gold_inputs if f.get("name")}
    pt_in = {slug(f["name"]): f.get("type") for f in pred_inputs if f.get("name")}
    pred_in_names, gold_in_names = set(pt_in), set(gt_in)
    exact_in, sem_in = _match_field_names(pred_in_names, gold_in_names)

    for pred_n, gold_n in sorted(sem_in.items()):
        type_note = ""
        if pt_in.get(pred_n) != gt_in.get(gold_n):
            type_note = f" and type should be '{gt_in[gold_n]}' not '{pt_in[pred_n]}'"
        issues.append(
            f"Naming: predicted '{pred_n}' → should be '{gold_n}'{type_note}."
        )

    for name in sorted(exact_in):
        if pt_in.get(name) != gt_in.get(name):
            issues.append(
                f"Type: '{name}' should be '{gt_in[name]}' not '{pt_in[name]}'."
            )

    matched_pred_in = exact_in | set(sem_in)
    matched_gold_in = exact_in | set(sem_in.values())
    for name in sorted(gold_in_names - matched_gold_in):
        issues.append(f"Missing input '{name}' ({gt_in[name]}).")
    for name in sorted(pred_in_names - matched_pred_in):
        issues.append(f"Spurious input '{name}' — not grounded in the prompt.")

    gt_out = {slug(f["name"]): f.get("type") for f in gold_outputs if f.get("name")}
    pt_out = {slug(f["name"]): f.get("type") for f in pred_outputs if f.get("name")}
    pred_out_names, gold_out_names = set(pt_out), set(gt_out)
    exact_out, sem_out = _match_field_names(pred_out_names, gold_out_names)

    for pred_n, gold_n in sorted(sem_out.items()):
        issues.append(f"Output naming: predicted '{pred_n}' → should be '{gold_n}'.")
    matched_pred_out = exact_out | set(sem_out)
    matched_gold_out = exact_out | set(sem_out.values())
    for name in sorted(gold_out_names - matched_gold_out):
        issues.append(f"Missing output '{name}'.")
    for name in sorted(pred_out_names - matched_pred_out):
        issues.append(f"Spurious output '{name}'.")

    if not issues:
        return "All fields correct — names, types, and counts match the gold annotation."
    parts = [header] + issues if header else issues
    return "\n".join(parts)
