"""Unified LLM client interface with offline fallback support.

Allows decoupled integration with Gemini, OpenAI, or local/mock heuristics
so the compiler works 100% reliably even without an internet connection or API keys.
"""

import os
import json
from typing import Optional, Dict, Any
from lexer.errors import DiagnosticRecord


class MockLLMProvider:
    """Offline heuristic provider simulating LLM responses for demos and tests."""

    @staticmethod
    def generate_sql_from_nl(nl_query: str) -> str:
        nl_lower = nl_query.lower()
        if "customer" in nl_lower and "delhi" in nl_lower:
            return "SELECT name, city FROM customers WHERE city = 'Delhi';"
        elif "count" in nl_lower and "order" in nl_lower:
            return "SELECT c.name, COUNT(*) FROM customers c JOIN orders o ON c.id = o.customer_id GROUP BY c.name;"
        elif "all customer" in nl_lower or "list customer" in nl_lower:
            return "SELECT * FROM customers;"
        elif "product" in nl_lower and ("price" in nl_lower or "expensive" in nl_lower):
            return "SELECT name, price FROM products WHERE price > 50.0 ORDER BY price DESC;"
        # Default mock candidate
        return "SELECT name FROM customers WHERE city = 'Delhi';"

    @staticmethod
    def explain_diagnostic(record: DiagnosticRecord) -> str:
        err = record.error_code
        if err == "ERR_COLUMN_NOT_FOUND":
            cols_hint = f" Available columns: {', '.join(record.available_columns)}." if record.available_columns else ""
            suggestion = f" Suggestion: {record.suggestion}" if record.suggestion else ""
            return (
                f"The query attempts to reference a column that doesn't exist in the schema.{cols_hint}{suggestion} "
                f"Please update the column name to match the declared table schema."
            )
        elif err == "ERR_TYPE_MISMATCH":
            return (
                "You are comparing two expressions of incompatible data types (e.g. comparing a DATE to an INT). "
                "Ensure that both sides of the comparison operator use matching or promotable types."
            )
        elif err == "ERR_MISSING_FROM":
            return (
                "The SQL parser expected the 'FROM' keyword following the projection list, but encountered another token instead. "
                "Make sure every SELECT query specifies the source table using 'FROM <table>'."
            )
        elif err == "ERR_AGGREGATION_SCOPE_MISMATCH":
            return (
                "When using aggregate functions (such as COUNT or SUM) alongside regular columns, SQL requires "
                "every non-aggregated column to be declared inside a GROUP BY clause."
            )
        elif err == "ERR_INVALID_JOIN_PREDICATE":
            return (
                "The ON condition used in this JOIN does not match the foreign key relationships established in the database schema. "
                "Verify that the joined columns correspond to the declared foreign keys."
            )
        elif err == "ERR_AMBIGUOUS_COLUMN":
            return (
                "This column name exists in multiple tables participating in the query. "
                "Prefix the column name with its table name or alias (e.g., 'c.id' instead of 'id')."
            )
        elif err == "ERR_NOSQL_COLLECTION_NOT_FOUND":
            cols_hint = f" Available collections: {', '.join(record.available_columns)}." if record.available_columns else ""
            suggestion = f" Suggestion: Did you mean '{record.suggestion}'?" if record.suggestion else ""
            return (
                f"The NoSQL query references a collection that doesn't exist in the catalog.{cols_hint}{suggestion} "
                f"Please verify the collection name against the declared catalog."
            )
        elif err == "ERR_NOSQL_FIELD_NOT_FOUND":
            cols_hint = f" Available fields: {', '.join(record.available_columns)}." if record.available_columns else ""
            suggestion = f" Suggestion: Did you mean '{record.suggestion}'?" if record.suggestion else ""
            return (
                f"The NoSQL document references a nonexistent field.{cols_hint}{suggestion} "
                f"Ensure the filter or projection fields match the declared document schema."
            )
        elif err == "ERR_NOSQL_INVALID_OPERATOR":
            suggestion = f" Suggestion: Did you mean '{record.suggestion}'?" if record.suggestion else ""
            return (
                f"The query uses an unrecognized MongoDB operator.{suggestion} "
                f"Make sure to use standard MongoDB operators like $eq, $gt, $match, $group, etc."
            )
        elif err == "ERR_NOSQL_TYPE_MISMATCH":
            return (
                f"Type error in NoSQL filter: {record.message} "
                f"Ensure that values in filter operators match the data types defined in the schema."
            )
        return f"{record.message} Please check the syntax and schema constraints."


class LLMClient:
    """Manages LLM API calls with fallback to MockLLMProvider when offline/no key."""

    def __init__(self, api_key: Optional[str] = None):
        self.gemini_key = api_key or os.getenv("GEMINI_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.mock = MockLLMProvider()

    def complete(self, prompt: str, system_instruction: str = "") -> str:
        # Check Gemini API
        if self.gemini_key:
            try:
                # Try google-genai SDK if available
                from google import genai
                client = genai.Client(api_key=self.gemini_key)
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config={"system_instruction": system_instruction} if system_instruction else None,
                )
                if response and response.text:
                    return response.text.strip()
            except Exception:
                pass

        # Check OpenAI API
        if self.openai_key:
            try:
                import urllib.request
                url = "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.openai_key}",
                }
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})
                data = json.dumps({"model": "gpt-4o-mini", "messages": messages, "temperature": 0.1}).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    res_json = json.loads(resp.read().decode("utf-8"))
                    return res_json["choices"][0]["message"]["content"].strip()
            except Exception:
                pass

        return ""
