from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


from app.api.dependencies import get_current_user


@pytest.fixture
def mock_get_current_user():
    """Mock the FastAPI auth dependency via dependency_overrides."""
    user = {
        "id": 1,
        "email": "employee@example.com",
        "role": "employee",
        "department": "general",
    }
    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.clear()


@pytest.fixture
def mock_answer_question():
    """Mock the query RAG answer generator."""
    with patch("app.api.routes_ask.answer_question", new_callable=AsyncMock) as mock:
        mock.return_value = {
            "answer": "Mocked RAG answer.",
            "sources": [],
            "confidence": 0.9,
            "session_id": "test-session",
            "rewritten_query": "mocked query",
            "answerability": "answered",
            "latencies": {"total_ms": 150.0},
            "prompt_version": "v1",
        }
        yield mock


def test_ask_endpoint(mock_get_current_user, mock_answer_question):
    """Test the POST /ask endpoint returns expected mocked response."""
    response = client.post(
        "/ask",
        json={"question": "Test question?", "session_id": "test-session"},
        headers={"Authorization": "Bearer fake-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Mocked RAG answer."
    assert data["confidence"] == 0.9
    mock_answer_question.assert_called_once()
