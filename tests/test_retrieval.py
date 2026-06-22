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


def test_semantic_catches_paraphrase(monkeypatch):
    """Semantic retrieval matches prompts that share meaning but few words."""
    apps = [
        _app("email", "Write a polite email to a supplier asking for a revised quote"),
        _app("k8s", "kubernetes deployment 3 replicas staging autoscaling"),
    ]
    monkeypatch.setattr(retrieval.app_store, "all_apps", lambda: apps)

    matches = find_similar(
        "Send a courteous message to the vendor requesting an updated price",
        min_score=0.3,
    )
    assert matches and matches[0].app_id == "email"
