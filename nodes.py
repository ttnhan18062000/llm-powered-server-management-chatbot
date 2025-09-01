# nodes.py
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field

from models import GraphState, NodeStatus
from prompts import (
    process_analyzer_prompt,
    planner_prompt,
    analyzer_prompt,
    sql_node_prompt,
)

# --- LLM and Chain Setup ---
# Use a model that supports structured output well

model = init_chat_model("gemini-2.5-flash", model_provider="google_genai")


class ProcessAnalyzerOutput(BaseModel):
    process: List[str]


class PlannerOutput(BaseModel):
    version: str
    nodes: str  # JSON string
    edges: str  # CSV string


class AnalyzerOutput(BaseModel):
    status: str
    outputs: str  # JSON string
    notes: Optional[str] = ""


class SQLNodeOutput(BaseModel):
    sql: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = ""


process_analyzer_chain = process_analyzer_prompt | model.with_structured_output(
    ProcessAnalyzerOutput
)
planner_chain = planner_prompt | model.with_structured_output(PlannerOutput)
analyzer_chain = analyzer_prompt | model.with_structured_output(AnalyzerOutput)
sql_chain = sql_node_prompt | model.with_structured_output(SQLNodeOutput)


# --- Plan Parsing and Navigation Helpers ---
def _csv_to_list(s: str) -> List[str]:
    return [item.strip() for item in s.split(",") if item.strip()] if s else []


def _edges_from_csv(csv: str) -> List[Tuple[str, str]]:
    edges = []
    if not csv:
        return edges
    for part in csv.split(","):
        if ">" in part:
            src, dst = part.split(">", 1)
            edges.append((src.strip(), dst.strip()))
    return edges


def _get_predecessors(plan: Dict[str, Any], node_id: str) -> List[str]:
    return [src for src, dst in plan.get("edges", []) if dst == node_id]


def _are_predecessors_succeeded(state: GraphState, node_id: str) -> bool:
    predecessors = _get_predecessors(state.plan, node_id)
    return all(
        state.node_status.get(p, NodeStatus()).state == "succeeded"
        for p in predecessors
    )


def _are_requirements_met(state: GraphState, node: Dict[str, str]) -> bool:
    required_artifacts = _csv_to_list(node.get("requires", ""))
    return all(r in state.artifacts for r in required_artifacts)


def _get_runnable_nodes(state: GraphState) -> List[Dict[str, str]]:
    if not state.plan:
        return []
    runnable = []
    for node in state.plan.get("nodes", []):
        node_id = node["id"]
        status = state.node_status.get(node_id, NodeStatus())
        if status.state == "pending":
            if _are_predecessors_succeeded(state, node_id) and _are_requirements_met(
                state, node
            ):
                runnable.append(node)
    return runnable


# --- SQLite Executor (Allows Modifications) ---
def _exec_sqlite(sql: str, db_path: str) -> Dict[str, Any]:
    """
    Executes a pure SQL string on a SQLite DB.
    WARNING: This is unsafe for production due to SQL injection risks.
    """
    if not db_path or not os.path.exists(db_path):
        return {"status": "fail", "error": f"Database path not found: {db_path}"}

    t0 = time.time()
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # MODIFIED: Execute SQL directly without parameters
            cursor.execute(sql)

            if sql.strip().upper().startswith("SELECT"):
                columns = [desc[0] for desc in cursor.description or []]
                rows = cursor.fetchall()
                result = {"columns": columns, "rows": rows}
                row_count = len(rows)
            else:
                conn.commit()
                result = None
                row_count = cursor.rowcount

    except Exception as e:
        return {"status": "fail", "error": str(e)}

    elapsed_ms = int((time.time() - t0) * 1000)
    return {
        "status": "ok",
        "result": result,
        "stats": {"elapsed_ms": elapsed_ms, "rows_affected": row_count},
    }


# --- LangGraph Node Functions ---
def process_analyzer(state: GraphState) -> GraphState:
    """Generates the initial high-level process."""
    out = process_analyzer_chain.invoke(
        {
            "user_request": state.user_request,
            "general_context": state.general_context,
            "schema_snapshot": state.schema_snapshot,
        }
    )
    state.process = out.process
    with open("output/process.json", "w") as f:
        json.dump(state.process, f, indent=2)
    return state


def planner(state: GraphState) -> GraphState:
    """Generates the structured DAG plan."""
    out = planner_chain.invoke(
        {
            "user_request": state.user_request,
            "process": "\n".join(state.process),
            "general_context": state.general_context,
            "schema_snapshot": state.schema_snapshot,
        }
    )
    try:
        nodes = json.loads(out.nodes)
    except json.JSONDecodeError as e:
        raise ValueError(f"Planner returned invalid JSON for nodes: {e}")

    state.plan = {
        "version": out.version,
        "nodes": nodes,
        "edges": _edges_from_csv(out.edges),
    }
    for node in nodes:
        state.node_status[node["id"]] = NodeStatus()
    with open("output/plan.json", "w") as f:
        json.dump(state.plan, f, indent=2)
    return state


def select_node(state: GraphState) -> GraphState:
    """Selects the next runnable node."""
    runnable_nodes = _get_runnable_nodes(state)
    state.current_node_id = runnable_nodes[0]["id"] if runnable_nodes else None
    return state


def run_node(state: GraphState) -> GraphState:
    """Executes the currently selected node."""
    node_id = state.current_node_id
    if not node_id:
        return state

    node = next(n for n in state.plan["nodes"] if n["id"] == node_id)
    status = state.node_status[node_id]
    status.state = "running"
    status.attempts += 1
    state.total_attempts += 1

    # Prepare context for the node
    required_artifacts = {
        r: state.artifacts.get(r) for r in _csv_to_list(node.get("requires", ""))
    }

    payload = {
        "node_id": node_id,
        "user_request": state.user_request,
        "requires_csv": node.get("requires", ""),
        "produces_csv": node.get("produces", ""),
        "input_hints": node.get("input", ""),
        "general_context": state.general_context,
        "schema_snapshot": state.schema_snapshot,
        "context_artifacts_json": json.dumps(required_artifacts, indent=2),
    }

    if node["type"].upper() == "ANALYZER":
        out = analyzer_chain.invoke(payload)
        try:
            artifacts_to_add = json.loads(out.outputs)
        except json.JSONDecodeError:
            artifacts_to_add = {}

        state.last_output = {
            "status": out.status,
            "artifacts": artifacts_to_add,
            "notes": out.notes,
        }
        if out.status == "ok":
            status.state = "succeeded"
        else:
            status.state = "failed"
            status.last_error = f"Analyzer failed with status: {out.status}"

    elif node["type"].upper() == "SQL":
        db_path = os.getenv("SQLITE_DB_PATH")
        payload.update({"example_queries": state.example_queries})
        out = sql_chain.invoke(payload)

        state.executed_queries.append(out.sql)

        exec_result = _exec_sqlite(out.sql, db_path)

        artifacts_to_add = {}
        produces = _csv_to_list(node.get("produces", ""))
        sql_artifact_key = next(
            (p for p in produces if p.lower().startswith("sql")), None
        )
        result_artifact_key = next(
            (p for p in produces if p.lower().startswith("result")), None
        )

        if sql_artifact_key:
            artifacts_to_add[sql_artifact_key] = out.sql
        if (
            result_artifact_key
            and exec_result["status"] == "ok"
            and exec_result.get("result")
        ):
            artifacts_to_add[result_artifact_key] = exec_result["result"]

        state.last_output = {
            "status": exec_result["status"],
            "artifacts": artifacts_to_add,
            "notes": out.notes,
            "stats": exec_result.get("stats", {}),
            "error": exec_result.get("error"),
        }
        if exec_result["status"] == "ok":
            status.state = "succeeded"
        else:
            status.state = "failed"
            status.last_error = exec_result.get("error", "SQL execution failed")

    else:
        status.state = "failed"
        status.last_error = f"Unknown node type: {node['type']}"
        state.last_output = {
            "status": "fail",
            "error": status.last_error,
            "artifacts": {},
        }

    return state


def resolve_data(state: GraphState) -> GraphState:
    """Updates the main artifact blackboard with the output of the last node."""
    node_id = state.current_node_id
    if not node_id:
        return state

    status = state.node_status[node_id]
    if status.state == "succeeded" and state.last_output:
        new_artifacts = state.last_output.get("artifacts", {})
        if isinstance(new_artifacts, dict):
            state.artifacts.update(new_artifacts)
    return state


def should_continue(state: GraphState) -> str:
    """Determines if the graph should continue or end."""
    if state.total_attempts >= 20:  # Safety break
        state.issues.append({"reason": "max_attempts_exceeded"})
        return "end"

    runnable_nodes = _get_runnable_nodes(state)
    if not runnable_nodes:
        # Check if all nodes succeeded
        all_succeeded = all(s.state == "succeeded" for s in state.node_status.values())
        if not all_succeeded:
            state.issues.append({"reason": "execution_stalled_due_to_failures"})
        return "end"

    return "continue"
