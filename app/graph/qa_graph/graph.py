"""
Q&A agent — simplified version without tool calling.
"""
from __future__ import annotations
import logging

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END

from app.config import get_llm
from app.prompts.tour_guide import TOUR_GUIDE_SYSTEM_PROMPT
from app.graph.qa_graph.state import QAState

logger = logging.getLogger(__name__)


def _build_lc_messages(state: QAState) -> list:
    """Convert state messages to LangChain message objects."""
    lc_messages = [SystemMessage(content=TOUR_GUIDE_SYSTEM_PROMPT)]

    for m in state.get("messages", []):
        if m["role"] == "user":
            lc_messages.append(HumanMessage(content=m["content"]))
        elif m["role"] == "assistant":
            lc_messages.append(AIMessage(content=m["content"]))

    return lc_messages


def tour_guide_node(state: QAState) -> QAState:
    """
    Tour guide node without tools.
    """
    llm = get_llm()
    lc_messages = _build_lc_messages(state)

    try:
        response = llm.invoke(lc_messages)

        answer = (
            response.content
            if isinstance(response.content, str)
            else str(response.content)
        )

        return {
            **state,
            "answer": answer,
            "_last_ai_message": response,
        }

    except Exception as e:
        logger.error("Tour guide LLM error: %s", e)

        return {
            **state,
            "error": str(e),
            "answer": f"ERROR: {str(e)}",
        }


def format_answer_node(state: QAState) -> QAState:
    """
    Ensure answer is always a string.
    """
    answer = state.get("answer", "")

    if not answer:
        answer = "I could not find a good answer. Please rephrase your question."

    return {
        **state,
        "answer": answer,
        "error": None,
    }


def build_qa_graph() -> StateGraph:
    graph = StateGraph(QAState)

    graph.add_node("tour_guide", tour_guide_node)
    graph.add_node("format_answer", format_answer_node)

    graph.set_entry_point("tour_guide")

    graph.add_edge("tour_guide", "format_answer")
    graph.add_edge("format_answer", END)

    return graph.compile()


qa_graph = build_qa_graph()