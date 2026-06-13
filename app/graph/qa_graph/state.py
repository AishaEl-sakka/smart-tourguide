"""State for the Q&A agent graph."""
from typing_extensions import TypedDict


class QAState(TypedDict, total=False):
    session_id: str
    messages: list[dict]
    answer: str
    sources: list[str]
    error: str | None