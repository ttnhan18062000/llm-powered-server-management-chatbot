import sqlite3
import sqlparse


def load_and_clean_sql(sql_file: str) -> str:
    """Load SQL file and strip out line comments starting with --"""
    lines = []
    with open(sql_file, "r", encoding="utf-8") as f:
        for line in f:
            # Remove everything after `--`
            stripped = line.split("--", 1)[0].strip()
            if stripped:  # keep only non-empty lines
                lines.append(stripped)
    return "\n".join(lines)


def run_queries(db_path: str, sql_file: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Load cleaned SQL (no comments)
    raw_sql = load_and_clean_sql(sql_file)

    # Split into individual statements
    statements = sqlparse.split(raw_sql)

    for i, stmt in enumerate(statements, start=1):
        stmt = stmt.strip()
        if not stmt:
            continue

        print(f"\n--- Query {i} ---")
        # print(stmt)

        try:
            cursor.execute(stmt)
            rows = cursor.fetchall()

            if rows:
                for row in rows:
                    print(row)
            else:
                print("✅ Query executed successfully (no rows returned).")

        except Exception as e:
            print(f"❌ Error executing query {i}: {e}")

    conn.close()


if __name__ == "__main__":
    run_queries("logistics.db", "query1.sql")
    run_queries("logistics.db", "query2.sql")
    run_queries("logistics.db", "query3.sql")
