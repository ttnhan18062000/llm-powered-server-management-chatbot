# workflow.py
from langgraph.graph import StateGraph, END
from pydantic.json import pydantic_encoder
import json
import os
from pathlib import Path

from models import GraphState
from nodes import (
    process_analyzer,
    planner,
    select_node,
    run_node,
    resolve_data,
    should_continue,
)


def build_graph():
    """Builds the langgraph workflow."""
    workflow = StateGraph(GraphState)

    # Add nodes
    workflow.add_node("process_analyzer", process_analyzer)
    workflow.add_node("planner", planner)
    workflow.add_node("select_node", select_node)
    workflow.add_node("run_node", run_node)
    workflow.add_node("resolve_data", resolve_data)

    # Define edges
    workflow.set_entry_point("process_analyzer")
    workflow.add_edge("process_analyzer", "planner")
    workflow.add_edge("planner", "select_node")
    workflow.add_edge("select_node", "run_node")
    workflow.add_edge("run_node", "resolve_data")

    # Conditional edge to loop or end
    workflow.add_conditional_edges(
        "resolve_data",
        should_continue,
        {"continue": "select_node", "end": END},
    )

    return workflow.compile()


def run_workflow(
    user_request: str,
    general_context: str,
    schema_snapshot: str,
    example_queries: str,
    id=None,
):
    """Initializes and runs the workflow, returning the final state."""
    if id:
        output_dir = Path(f"output/test/{id}")
    else:
        output_dir = Path(f"output/tmp")
    os.makedirs(output_dir, exist_ok=True)

    graph = build_graph()
    initial_state = GraphState(
        output_dir=output_dir,
        user_request=user_request,
        general_context=general_context,
        schema_snapshot=schema_snapshot,
        example_queries=example_queries,
    )

    # The output is an iterator, consume it to get the final state
    final_state = None
    for output in graph.stream(initial_state):
        final_state = output

    # The final state is the value of the last key in the output
    final_state_value = list(final_state.values())[-1]

    # Save the final state for debugging
    final_output_path = output_dir / "final_state.json"
    with final_output_path.open("w", encoding="utf-8") as f:
        json.dump(final_state_value, f, indent=2, default=pydantic_encoder)

    return final_state_value
