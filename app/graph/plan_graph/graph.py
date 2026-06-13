"""
Trip Planning StateGraph — independent graph with:
  collector → [conditional] → budget_validator → [conditional] →
  parallel_runner → aggregator → planner
"""
from __future__ import annotations
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.plan_graph.state import PlanState
from app.graph.plan_graph.nodes.collector import (
    collector_node,
    should_continue_collecting,
)
from app.graph.plan_graph.nodes.budget_validator import (
    budget_validator_node,
    should_proceed_after_validation,
)
from app.graph.plan_graph.nodes.parallel_runner import parallel_runner_node
from app.graph.plan_graph.nodes.aggregator import aggregator_node
from app.graph.plan_graph.nodes.planner import planner_node


def _ask_user_node(state: PlanState) -> PlanState:
    """Passthrough node — the graph interrupts here to return question to caller."""
    return state


def _invalid_budget_node(state: PlanState) -> PlanState:
    """Return the validation error message as the question."""
    validation = state.get("budget_validation", {})
    return {
        **state,
        "collector_question": validation.get("reason", "Invalid budget. Please try again."),
        # Reset budget so collector asks again
        "constraints": {**state.get("constraints", {}), "budget": None, "currency": None},
        "missing_fields": ["budget"],
    }


def build_plan_graph() -> StateGraph:
    """Build and compile the planning graph with memory checkpointing."""
    graph = StateGraph(PlanState)

    graph.add_node("collector",        collector_node)
    graph.add_node("ask_user",         _ask_user_node)
    graph.add_node("validate_budget",  budget_validator_node)
    graph.add_node("invalid_budget",   _invalid_budget_node)
    graph.add_node("parallel_runner",  parallel_runner_node)
    graph.add_node("aggregator",       aggregator_node)
    graph.add_node("planner",          planner_node)

    # Entry point
    graph.set_entry_point("collector")

    # Collector → conditional
    graph.add_conditional_edges(
        "collector",
        should_continue_collecting,
        {
            "ask_user":        "ask_user",
            "validate_budget": "validate_budget",
        },
    )

    # Ask user → interrupt (returns to caller) then resumes at collector
    graph.add_edge("ask_user", END)

    # Budget validator → conditional
    graph.add_conditional_edges(
        "validate_budget",
        should_proceed_after_validation,
        {
            "invalid_budget": "invalid_budget",
            "fetch_data":     "parallel_runner",
        },
    )

    # Invalid budget → ask_user (re-prompt)
    graph.add_edge("invalid_budget", "ask_user")

    # Happy path
    graph.add_edge("parallel_runner", "aggregator")
    graph.add_edge("aggregator",      "planner")
    graph.add_edge("planner",         END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


# Singleton — compiled once at import time
plan_graph = build_plan_graph()