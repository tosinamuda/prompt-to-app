import numpy as np
import pytest

from prompt2app import retrieval
from prompt2app.retrieval import _find_lexical, find_similar, similarity, tokenize
from prompt2app.schemas import AppSpec


def test_tokenize_drops_stopwords_and_verbs():
    toks = set(tokenize("Write a polite email to the supplier"))
    assert {"polite", "email", "supplier"} <= toks
    assert toks.isdisjoint({"a", "the", "to", "write"})


def test_similarity_bounds():
    same = "kubernetes deployment replicas"
    assert similarity(same, same) == pytest.approx(1.0)
    assert similarity("kubernetes deployment", "banana smoothie recipe") == 0.0
    partial = similarity("kubernetes deployment staging", "kubernetes deployment production")
    assert 0.0 < partial < 1.0


def _app(app_id, prompt) -> AppSpec:
    return AppSpec(
        app_id=app_id, task_name=app_id, title=app_id, description="", source_prompt=prompt
    )


def test_find_similar_filters_sorts_and_topk(monkeypatch):
    apps = [
        _app("k8s", "kubernetes deployment 3 replicas staging autoscaling cloudwatch"),
        _app("email", "polite supplier email revised quote laptops budget friday"),
    ]
    monkeypatch.setattr(retrieval.app_store, "all_apps", lambda: apps)

    matches = find_similar("kubernetes deployment staging replicas", min_score=0.5)
    assert matches and matches[0].app_id == "k8s"
    assert matches[0].score >= matches[-1].score

    assert find_similar("banana smoothie recipe", min_score=0.6) == []


def test_lexical_fallback_filters_sorts(monkeypatch):
    """The lexical path still works when called directly."""
    apps = [
        _app("k8s", "kubernetes deployment 3 replicas staging autoscaling cloudwatch"),
        _app("email", "polite supplier email revised quote laptops budget friday"),
    ]
    matches = _find_lexical(
        "kubernetes deployment staging replicas", apps, k=3, min_score=0.2
    )
    assert matches and matches[0].app_id == "k8s"


@pytest.mark.integration
def test_semantic_catches_paraphrase(monkeypatch):
    """Semantic retrieval matches prompts that share meaning but few words (real model)."""
    apps = [
        _app("email", "Write a polite email to a supplier asking for a revised quote"),
        _app("k8s", "kubernetes deployment 3 replicas staging autoscaling"),
    ]
    monkeypatch.setattr(retrieval.app_store, "all_apps", lambda: apps)

    matches = find_similar(
        "Send a courteous message to the vendor requesting an updated price",
    )
    assert matches and matches[0].app_id == "email"


def _mock_embed(monkeypatch, vectors: dict[str, list[float]]):
    """Patch retrieval._embed with deterministic vectors keyed by text; reset the cache."""
    retrieval._corpus_cache.clear()
    seen: list[str] = []

    def fake_embed(texts):
        seen.extend(texts)
        return np.array([vectors[t] for t in texts])

    monkeypatch.setattr(retrieval, "_embed", fake_embed)
    return seen


def test_default_threshold_calibrated_above_unrelated():
    # Guards against regressing to the old 0.5, which admitted unrelated prompts (~0.60).
    assert retrieval.SEMANTIC_MIN_SCORE >= 0.6


def test_semantic_threshold_filters_unrelated(monkeypatch):
    _mock_embed(monkeypatch, {
        "QUERY": [1.0, 0.0],
        "close": [0.985, 0.174],   # cosine ≈ 0.985 with QUERY → kept
        "far": [0.0, 1.0],          # cosine 0 → dropped at default threshold
    })
    apps = [_app("c", "close"), _app("f", "far")]
    monkeypatch.setattr(retrieval.app_store, "all_apps", lambda: apps)

    matches = find_similar("QUERY")
    assert [m.app_id for m in matches] == ["c"]


def test_corpus_embeddings_reused_across_queries(monkeypatch):
    seen = _mock_embed(monkeypatch, {
        "q1": [1.0, 0.0], "q2": [1.0, 0.0],
        "supplier quote": [1.0, 0.0], "kubernetes deploy": [0.0, 1.0],
    })
    apps = [_app("email", "supplier quote"), _app("k8s", "kubernetes deploy")]
    monkeypatch.setattr(retrieval.app_store, "all_apps", lambda: apps)

    find_similar("q1", min_score=0.0)
    find_similar("q2", min_score=0.0)

    # Each corpus prompt is embedded once total (cached on the second query); each query once.
    assert seen.count("supplier quote") == 1
    assert seen.count("kubernetes deploy") == 1
    assert seen.count("q1") == 1 and seen.count("q2") == 1
