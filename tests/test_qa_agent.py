"""
Tests for the Q&A agent graph.
Runs without real API keys using mocked LLM responses.
"""
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage

from app.graph.qa_graph.graph import build_qa_graph
from app.evaluation.accuracy import evaluate_qa_response, rouge_score


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def qa_graph():
    return build_qa_graph()


@pytest.fixture
def mock_llm_response():
    msg = AIMessage(content="The Great Pyramid of Giza was built for Pharaoh Khufu around 2560 BCE. It stands 138 meters tall and is the only surviving ancient wonder of the world.")
    mock = MagicMock()
    mock.invoke.return_value = msg
    return mock


# ── Unit tests ────────────────────────────────────────────────────────────────

def test_evaluate_qa_good_answer():
    answer = "The Great Pyramid was built for Pharaoh Khufu around 2560 BCE and stands 138 meters tall."
    result = evaluate_qa_response(answer)
    assert result["has_min_content"] is True
    assert result["quality"] == "good"


def test_evaluate_qa_short_answer():
    result = evaluate_qa_response("Yes.")
    assert result["has_min_content"] is False
    assert result["quality"] == "poor"


def test_evaluate_qa_with_reference():
    answer = "Khufu built the Great Pyramid around 2560 BCE."
    reference = "The Great Pyramid was constructed by Pharaoh Khufu circa 2560 BCE."
    result = evaluate_qa_response(answer, reference)
    assert "rouge" in result
    assert result["rouge"]["rouge1_f"] > 0.1


def test_rouge_score_identical():
    text = "The pyramids of Giza are in Egypt."
    scores = rouge_score(text, text)
    assert scores["rouge1_f"] == 1.0
    assert scores["rougeL_f"] == 1.0


def test_rouge_score_different():
    hyp = "Cairo is the capital of Egypt."
    ref = "The Great Pyramid is located in Giza."
    scores = rouge_score(hyp, ref)
    assert scores["rouge1_f"] < 0.5


@patch("app.graph.qa_graph.graph.get_llm")
def test_tour_guide_node_returns_answer(mock_get_llm, mock_llm_response):
    mock_get_llm.return_value = mock_llm_response
    from app.graph.qa_graph.graph import tour_guide_node
    state = {
        "session_id": "test-123",
        "messages": [{"role": "user", "content": "Tell me about the pyramids"}],
    }
    result = tour_guide_node(state)
    assert "answer" in result
    assert len(result["answer"]) > 0


# ── Integration-style test (no real API) ─────────────────────────────────────

def test_state_structure():
    """Verify QAState fields are correct TypedDict keys."""
    from app.graph.qa_graph.state import QAState
    state = QAState(
        session_id="abc",
        messages=[{"role": "user", "content": "hello"}],
        answer="",
        sources=[],
        error=None,
    )
    assert state["session_id"] == "abc"
