"""
Q&A agent — independent graph.
Tour guide node wraps LLM + tools in a ReAct loop.
"""
from __future__ import annotations
import logging

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition

from app.config import get_llm
from app.prompts.tour_guide import TOUR_GUIDE_SYSTEM_PROMPT
from app.tools.search import web_search
from app.tools.wikidata import wikidata_search
from app.graph.qa_graph.state import QAState

logger = logging.getLogger(__name__)

TOOLS: list[BaseTool] = [web_search, wikidata_search]


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
    """Tour guide LLM node — bound to tools for ReAct."""
    llm = get_llm().bind_tools(TOOLS)
    lc_messages = _build_lc_messages(state)
    try:
        response = llm.invoke(lc_messages)
        # Extract final text answer (if no tool calls)
        answer = response.content if isinstance(response.content, str) else ""
        return {**state, "answer": answer, "_last_ai_message": response}
    except Exception as e:
        logger.error("Tour guide LLM error: %s", e)
        return {**state, "error": str(e), "answer": "I encountered an error. Please try again."}


def format_answer_node(state: QAState) -> QAState:
    """Final formatting — ensures answer is a clean string."""
    answer = state.get("answer", "")
    if not answer:
        answer = "I could not find a good answer. Please rephrase your question."
    return {**state, "answer": answer, "error": None}


def build_qa_graph() -> StateGraph:
    graph = StateGraph(QAState)

    graph.add_node("tour_guide",    tour_guide_node)
    graph.add_node("tools",         ToolNode(TOOLS))
    graph.add_node("format_answer", format_answer_node)

    graph.set_entry_point("tour_guide")

    # ReAct loop: if LLM called a tool, run it, then call LLM again
    graph.add_conditional_edges(
        "tour_guide",
        tools_condition,
        {"tools": "tools", END: "format_answer"},
    )
    graph.add_edge("tools",         "tour_guide")   # loop back
    graph.add_edge("format_answer", END)

    return graph.compile()


qa_graph = build_qa_graph()