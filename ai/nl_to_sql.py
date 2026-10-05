"""Natural Language to SQL Candidate Translator (AI Input Edge).

Translates plain-English user questions into candidate SQL queries
grounded in the schema and constrained to the analytical SQL subset.
Treated as completely untrusted input by the compiler.
"""

from typing import Optional
from .llm_client import LLMClient
from semantic.catalog import DatabaseCatalog, create_default_catalog

SYSTEM_PROMPT = """You are a SQL query generator for a Compiler Design Lab project.
Translate the user's plain-English question into a single SQL query matching ONLY this strict subset:
- Keywords: SELECT, FROM, WHERE, JOIN, INNER, LEFT, ON, GROUP BY, HAVING, ORDER BY, LIMIT
- Aggregates: COUNT(*), COUNT(col), SUM(col), AVG(col), MIN(col), MAX(col)
- Comparisons: =, !=, <, >, <=, >=, AND, OR
- Only use tables and columns from this database schema:
  * customers (id INT PK, name VARCHAR, city VARCHAR, signup_date DATE)
  * orders (id INT PK, customer_id INT FK -> customers.id, order_date DATE, status VARCHAR)
  * order_items (order_id INT FK -> orders.id, product_id INT FK -> products.id, quantity INT, price FLOAT)
  * products (id INT PK, name VARCHAR, category VARCHAR, price FLOAT)

Output ONLY the raw SQL query with no markdown formatting, no backticks, and no explanation.
"""


class NLToSQLTranslator:
    def __init__(self, client: Optional[LLMClient] = None, catalog: Optional[DatabaseCatalog] = None):
        self.client = client or LLMClient()
        self.catalog = catalog or create_default_catalog()

    def translate(self, natural_language_query: str) -> str:
        """Translates a natural language query into a candidate SQL query."""
        raw_result = self.client.complete(
            prompt=f"Generate SQL query for: {natural_language_query}",
            system_instruction=SYSTEM_PROMPT,
        )

        if not raw_result:
            # Fallback to local heuristic mock
            return self.client.mock.generate_sql_from_nl(natural_language_query)

        # Clean markdown codeblocks if LLM included them
        cleaned = raw_result.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        return cleaned
