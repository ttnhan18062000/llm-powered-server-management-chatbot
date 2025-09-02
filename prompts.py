# prompts.py
from langchain.prompts import ChatPromptTemplate

# 1. Prompt to break the request into a high-level textual process
process_analyzer_prompt = ChatPromptTemplate.from_template(
    """You are an expert logistics analyst. Your task is to take a user's request and break it down into a sequence of logical, high-level steps required to fulfill it using a database.

**Rules:**
1.  Label each step with **ONE** of the following tags: `[SQL]`, `[SQL_RESULT_ANALYZER]`, or `[ANALYZE]`.
2.  The flow for querying and interpreting data is now **strict**:
    - A `[SQL]` step is used to execute a database query that retrieves raw data.
    - It **MUST** be immediately followed by a `[SQL_RESULT_ANALYZER]` step.
    - The `[SQL_RESULT_ANALYZER]` step's job is to interpret the raw data from the `[SQL]` step (e.g., "confirm if records were found", "identify the key values from the result").
    - Subsequent `[ANALYZE]` steps then use the *interpretation* from the `[SQL_RESULT_ANALYZER]`, not the raw data.
3.  The final step should typically be `[ANALYZE]` to formulate the final answer for the user.
4.  The output **MUST** be a valid JSON array of strings.

---
**CONTEXT**

General Context:
`{general_context}`

Database Schema:
`{schema_snapshot}`

---
**EXAMPLE**

**Input:**

User Request:
`Generate a system-wide report of all products that are below their reorder level in any warehouse, and for each, suggest the most recent supplier.`

**Output:**
[
  "[SQL] Query the database to find all products where the stock quantity is below a reorder threshold, joining across products, warehouses, and suppliers to gather all necessary details.",
  "[SQL_RESULT_ANALYZER] Review the raw query results. If products were found, confirm the list of under-stock products. If no products were found, note that all inventory levels are sufficient.",
  "[ANALYZE] Format the summarized list of under-stock products into a clear, final report for the user, listing each product, its location, and its most recent supplier."
]

---
**REAL INPUT**

User Request:
{user_request}

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

---
**CONTEXT**

General Context:
`{general_context}`

Database Schema:
`{schema_snapshot}`

---
**EXAMPLE**:

**Input**:

User Request:
`Generate a system-wide report of all products that are below their reorder level in any warehouse, and for each, suggest the most recent supplier.`

High-Level Process:
`[
  "[SQL] Query the database to find all products where the stock quantity is below a reorder threshold, joining across products, warehouses, and suppliers to gather all necessary details.",
  "[SQL_RESULT_ANALYZER] Review the raw query results. If products were found, confirm the list of under-stock products. If no products were found, note that all inventory levels are sufficient.",
  "[ANALYZE] Format the summarized list of under-stock products into a clear, final report for the user, listing each product, its location, and its most recent supplier."
]`

**Output**:
{{
  "version": "1.0",
  "nodes": [
    {{
      "id": "n1",
      "type": "SQL",
      "label": "Retrieve products below reorder level",
      "requires": "",
      "produces": "result_below_reorder",
      "input": "Generate a SQL query to retrieve `product_id`, `product_name`, `warehouse_id`, `warehouse_name`, `current_quantity` (from inventory.quantity), and `reorder_level` (from products.reorder_level) for all products where `inventory.quantity` is less than `products.reorder_level`. Join `products`, `inventory`, and `warehouses` tables."
    }},
    {{
      "id": "n2",
      "type": "SQL_RESULT_ANALYZER",
      "label": "Summarize products below reorder level",
      "requires": "result_below_reorder",
      "produces": "summary_below_reorder",
      "input": "Analyze the `result_below_reorder` to identify unique `product_id`s that are below their reorder level in any warehouse, along with their names, the specific warehouse details (id, name), current quantities, and reorder levels. Focus on extracting key information for subsequent steps, specifically the `product_id`s that need supplier information."
    }},
    {{
      "id": "n3",
      "type": "SQL",
      "label": "Retrieve most recent supplier for products",
      "requires": "summary_below_reorder",
      "produces": "result_recent_suppliers",
      "input": "Generate a SQL query to find the most recent supplier for each `product_id` present in `summary_below_reorder`. Join `purchase_order_items`, `purchase_orders`, and `suppliers`. Determine recency by `purchase_orders.received_date` (if not NULL) otherwise by `purchase_orders.order_date`. For each `product_id`, select the `supplier_name` and the most recent `received_date` or `order_date`. Ensure only one supplier per product_id is returned, corresponding to the most recent purchase order. Filter results to only include `product_id`s that were identified as being below reorder level."
    }},
    {{
      "id": "n4",
      "type": "SQL_RESULT_ANALYZER",
      "label": "Summarize recent suppliers",
      "requires": "result_recent_suppliers",
      "produces": "summary_recent_suppliers",
      "input": "Analyze the `result_recent_suppliers` to extract a clear mapping of `product_id` to its most recent `supplier_name`."
    }},
    {{
      "id": "n5",
      "type": "ANALYZER",
      "label": "Generate system-wide reorder report",
      "requires": "summary_below_reorder,summary_recent_suppliers",
      "produces": "final_report",
      "input": "Combine the information from `summary_below_reorder` and `summary_recent_suppliers`. For each product that is below its reorder level in any warehouse, present the product's name, the warehouse name, the current quantity, the reorder level, and the name of its most recent supplier. Format the output as a readable report, potentially a table or a list."
    }}
  ],
  "edges": [
    [
      "n1",
      "n2"
    ],
    [
      "n2",
      "n3"
    ],
    [
      "n3",
      "n4"
    ],
    [
      "n2",
      "n5"
    ],
    [
      "n4",
      "n5"
    ]
  ]
}}

---
**REAL INPUT**

User Request:
`{user_request}`

High-Level Process:
`{process}`

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
