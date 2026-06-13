"""Shared pytest fixtures and configuration."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    """Provide dummy keys so Settings doesn't fail on import."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_dummy_key")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly_test_dummy_key")
    monkeypatch.setenv("OPENTRIPMAP_API_KEY", "test_dummy_key")


@pytest.fixture
def mock_llm():
    """A mock LLM that returns a simple response."""
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content="Test answer about Egypt tourism.")
    llm.bind_tools.return_value = llm
    return llm


@pytest.fixture
def test_client():
    with patch("app.config.get_llm") as mock:
        mock.return_value = MagicMock()
        from app.main import app
        return TestClient(app)