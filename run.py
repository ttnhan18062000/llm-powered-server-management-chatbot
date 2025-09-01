# run.py
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import argparse
import json
import os
import sqlite3
import sys

from workflow import run_workflow


def setup_database(db_path: str, schema_path: str):
    """Creates and initializes the SQLite database from a schema file."""
    if os.path.exists(db_path):
        os.remove(db_path)
    try:
        with open(schema_path, "r") as f:
            schema = f.read()
        conn = sqlite3.connect(db_path)
        conn.executescript(schema)
        conn.close()
        print(f"Database '{db_path}' created and schema applied.")
    except Exception as e:
        print(f"Error setting up database: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Run a text-to-SQL workflow using LangGraph."
    )
    parser.add_argument("--db", required=True, help="Path to the SQLite database file.")
    parser.add_argument(
        "--schema", required=True, help="Path to the SQL schema file (DDL)."
    )
    parser.add_argument(
        "--request",
        help="The natural language request. Reads from stdin if not provided.",
    )
    args = parser.parse_args()

    # 1. Setup Database
    setup_database(args.db, args.schema)
    os.environ["SQLITE_DB_PATH"] = args.db

    # 2. Load General Context
    with open("descriptions.txt", "r") as f:
        general_context = f.read()

    # 3. Load Schema for LLM Context
    with open(args.schema, "r") as f:
        schema_text = f.read()

    with open("examples.sql", "r") as f:
        example_queries = f.read()

    # 4. Get User Request
    user_request = args.request
    if not user_request:
        print("Please enter your request (press Ctrl+D when done):")
        user_request = sys.stdin.read().strip()

    if not user_request:
        print("Error: No request provided.", file=sys.stderr)
        sys.exit(1)

    print("\n--- Running Workflow ---")
    print(f"Request: {user_request}")

    # 4. Run the Workflow
    final_state = run_workflow(
        user_request, general_context, schema_text, example_queries
    )

    # 5. Print Summary
    print("\n--- Workflow Complete ---")

    if final_state.get("issues"):
        print("\nIssues encountered:")
        for issue in final_state["issues"]:
            print(f"- {issue['reason']}")

    print("\nFinal Artifacts:")
    artifacts = final_state.get("artifacts", {})
    if not artifacts:
        print("(None)")
    for key, value in artifacts.items():
        print(f"\n--- Artifact: {key} ---")
        # Pretty print tables
        if isinstance(value, dict) and "columns" in value and "rows" in value:
            cols = value["columns"]
            rows = value["rows"]
            header = " | ".join(map(str, cols))
            print(header)
            print("-" * len(header))
            for row in rows:
                print(" | ".join(map(str, row)))
        else:
            print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
