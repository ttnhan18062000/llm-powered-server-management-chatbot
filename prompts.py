# prompts.py
from langchain.prompts import ChatPromptTemplate

# 1. Prompt to break the request into a high-level textual process
process_analyzer_prompt = ChatPromptTemplate.from_template(
    """You are an expert logistics analyst. Your task is to take a user's request and break it down into a sequence of logical steps required to fulfill it using a database.

Rules:
1.  Label each step as either `[SQL]` for a database operation or `[ANALYZE]` for a reasoning or data processing step.
2.  Be specific and clear. The final step should typically be `[ANALYZE]` to formulate the final answer.
3.  The output MUST be a valid JSON array of strings.

User Request:
{user_request}

General Context:
{general_context}

Database Schema:
{schema_snapshot}

Produce the ordered step-by-step process.
"""
)

# 2. Prompt to generate the structured DAG plan
planner_prompt = ChatPromptTemplate.from_template(
    """You are a STATIC PLANNER. Your job is to convert a user request and a high-level process into a detailed, executable Directed Acyclic Graph (DAG).

Return ONLY a valid JSON object with these fields. All values MUST be strings:
- "version": "1.0"
- "nodes": A JSON STRING (a stringified array) of node objects. Each node must have these string fields:
    {{
      "id": "a unique alphanumeric ID",
      "type": "SQL" or "ANALYZER" or "SQL_RESULT_ANALYZER",
      "label": "a short, human-readable description of the node's purpose",
      "requires": "a comma-separated list of artifact IDs this node needs as input, or empty",
      "produces": "a comma-separated list of artifact IDs this node will generate",
      "input": "detailed instructions or hints for the LLM that will execute this node"
    }}
- "edges": A CSV string of 'source_id>destination_id' pairs (e.g., "n1>n2,n2>n3").

**CRITICAL RULE**: The workflow for handling database queries is now STRICTLY controlled.
1.  A `SQL` node executes a query. It MUST produce a `result_*` artifact (e.g., `result_1`).
2.  Immediately following any `SQL` node that produces a result, you MUST add a `SQL_RESULT_ANALYZER` node.
3.  The `SQL_RESULT_ANALYZER` node MUST `require` the `result_*` artifact from the `SQL` node.
4.  The `SQL_RESULT_ANALYZER` node's job is to interpret the raw data and produce a concise `summary_*` artifact (e.g., `summary_1`).
5.  All subsequent `ANALYZER` or `SQL` nodes that need to know about the query's outcome MUST `require` the `summary_*` artifact, NOT the raw `result_*` artifact.

**Example Flow**:
`SQL Node (produces: result_customers)` -> `SQL_RESULT_ANALYZER Node (requires: result_customers, produces: summary_customers)` -> `ANALYZER Node (requires: summary_customers)`

User Request:
`{user_request}`

High-Level Process:
`{process}`

General Context:
`{general_context}`

Database Schema:
`{schema_snapshot}`

Generate the complete DAG plan following these strict rules.
"""
)

# 3. Prompt for the generic ANALYZER node
analyzer_prompt = ChatPromptTemplate.from_template(
    """You are a GENERIC ANALYZER. Your task is to perform a reasoning step based on the provided context and artifacts. You DO NOT generate SQL.

Your Goal: Fulfill the instructions in `input_hints` and produce the artifacts listed in `produces_csv`.

Inputs:
- node_id: {node_id}
- user_request: {user_request}
- requires_csv: {requires_csv} (Artifacts you can use)
- produces_csv: {produces_csv} (Artifacts you MUST generate)
- input_hints: {input_hints} (Your primary instruction)
- general_context:
`{general_context}`
- context_schema:
{schema_snapshot}
- context_artifacts_json:
{context_artifacts_json} (JSON object of available artifact values)

Task:
- Carefully analyze all inputs.
- Compute the values for the artifacts listed in `produces_csv`.
- Your output MUST be a JSON object with values for every artifact you were asked to produce.

Output Format (a single JSON object):
{{
  "status": "ok" or "fail",
  "outputs": "<a JSON string mapping each produced_artifact_id to its computed value>",
  "notes": "<any notes about your process>"
}}
"""
)

# 4. Prompt for the SQL node
sql_node_prompt = ChatPromptTemplate.from_template(
    """You are an expert SQL generator for SQLite. Your task is to generate a single, syntactically correct SQLite statement to fulfill the given instruction.

CONSTRAINTS:
- **Target Dialect**: SQLite.
- **Operations Allowed**: You can generate SELECT, INSERT, UPDATE, DELETE, or CREATE statements.
- **Single Statement**: Return only ONE valid SQL statement.
- **Pure SQL**: You MUST generate a complete and runnable SQL query string, embedding all necessary values (like names or numbers) directly into the string. Properly quote string literals.
- **No Explanation**: Do not add any commentary or explanation outside of the JSON output.

Inputs:
- node_id: {node_id}
- user_request: {user_request}
- requires_csv: {requires_csv}
- produces_csv: {produces_csv}
- input_hints: {input_hints} (Your primary instruction for what the SQL should accomplish)
- context_schema:
{schema_snapshot}
- context_artifacts_json:
{context_artifacts_json} (Values from previous steps you can use in your query)
- example queries:
{example_queries}

Output Format (a single JSON object):
{{
  "sql": "<the single, complete SQLite statement with all values embedded>",
  "notes": "<a brief note about the generated SQL>"
}}
"""
)


sql_result_analyzer_prompt = ChatPromptTemplate.from_template(
    """You are a Data Analyst. Your task is to interpret the raw result of a SQL query and provide a concise, useful summary for the next step in a larger process.

Context:
- Original User Request: {user_request}
- SQL Query That Was Executed: {sql_query}
- Raw SQL Result (as a JSON object with 'columns' and 'rows'):
{sql_result_json}

Your Goal:
Based on the inputs, generate a clear, natural language summary of the data.
- If there are rows, describe what they represent. Mention the number of rows.
- If there are no rows, explicitly state that "The query returned no results."
- If the result is a single number (e.g., from a COUNT or SUM), state the number and what it means.
- Keep the summary concise and directly relevant to the original user request.

Instruction for this step: {input_hints}

Artifacts to produce: {produces_csv}

Output Format (a single JSON object):
{{
  "status": "ok",
  "outputs": "<JSON string mapping each produced_artifact_id to its summary value>",
  "notes": "Summarized the SQL result."
}}
"""
)
