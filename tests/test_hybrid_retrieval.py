import pytest

from app.retrieval.hybrid import _diverse_select, _rrf_score


def test_rrf_score():
    # Rank 1 in both semantic and keyword: 1 / 61 + 1 / 61 = 2 / 61
    assert pytest.approx(_rrf_score([1, 1], k=60)) == (1.0 / 61) + (1.0 / 61)
    # Rank 1 in semantic, rank 5 in keyword
    assert pytest.approx(_rrf_score([1, 5], k=60)) == (1.0 / 61) + (1.0 / 65)
    # Empty ranks should return 0.0
    assert _rrf_score([], k=60) == 0.0


def test_diverse_select():
    candidates = [
        {"chunk_id": "c1", "filename": "docA.md", "rrf_score": 0.8},
        {"chunk_id": "c2", "filename": "docA.md", "rrf_score": 0.7},
        {"chunk_id": "c3", "filename": "docB.md", "rrf_score": 0.6},
        {"chunk_id": "c4", "filename": "docB.md", "rrf_score": 0.5},
    ]
    # If we select k=2 with high penalty (0.5), it should prefer c1 (docA, 0.8) and then c3 (docB, 0.6) instead of c2 (docA, 0.7 * 0.5 = 0.35)
    selected = _diverse_select(candidates, k=2, penalty=0.5)
    assert len(selected) == 2
    assert selected[0]["chunk_id"] == "c1"
    assert selected[1]["chunk_id"] == "c3"  # docB chunk preferred due to penalty on docA
