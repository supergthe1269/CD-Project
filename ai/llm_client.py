"""Unified LLM client interface with zero-dependency REST drivers and offline fallback.

Course: BCSE307P - Compiler Design Lab
Authors:
  - Gaurav Gopichand Nanhe (24BCB0020)
  - V Surya (24BAI0351)

Supports:
  1. Google Gemini REST API (gemini-2.5-flash / gemini-1.5-flash) via native urllib (zero dependencies)
  2. OpenAI REST API (gpt-4o-mini) via native urllib
  3. Optional google-genai SDK if installed
  4. Automatic .env file loading
  5. Deterministic MockLLMProvider fallback when offline or no API key is provided
"""

import os
import json
import time
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, Tuple
from lexer.errors import DiagnosticRecord


def _load_env_file():
    """Loads variables from .env file if present, with zero external dependency requirement."""
    try:
        import dotenv
        dotenv.load_dotenv()
        return
    except ImportError:
        pass

    # Simple built-in fallback parser for .env files
    env_paths = [".env", os.path.join(os.path.dirname(__file__), "..", ".env")]
    for path in env_paths:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k and k not in os.environ:
                                os.environ[k] = v
                break
            except Exception:
                pass


# Load .env on module import
_load_env_file()


class MockLLMProvider:
    """Offline heuristic provider simulating LLM responses for demos and offline tests."""

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
    """Manages LLM API calls with zero-dependency REST drivers and automatic offline fallback."""

    def __init__(self, api_key: Optional[str] = None):
        _load_env_file()
        self.gemini_key: Optional[str] = None
        self.openai_key: Optional[str] = None
        self.mock = MockLLMProvider()
        self.last_provider_used: str = "mock"
        self.last_error: Optional[str] = None

        # Key resolution
        if api_key:
            self.set_api_key(api_key)
        else:
            self.gemini_key = os.getenv("GEMINI_API_KEY")
            self.openai_key = os.getenv("OPENAI_API_KEY")

    def set_api_key(self, key: str):
        """Sets API key and automatically assigns to Gemini or OpenAI based on prefix."""
        key = key.strip()
        if key.startswith("sk-"):
            self.openai_key = key
        else:
            # Google AI Studio keys typically begin with AIzaSy...
            self.gemini_key = key

    def get_status(self) -> Dict[str, Any]:
        """Returns structured status of the active LLM provider."""
        if self.gemini_key:
            return {
                "provider": "Google Gemini",
                "is_live": True,
                "model": "gemini-2.5-flash",
                "masked_key": self._mask_key(self.gemini_key),
            }
        elif self.openai_key:
            return {
                "provider": "OpenAI",
                "is_live": True,
                "model": "gpt-4o-mini",
                "masked_key": self._mask_key(self.openai_key),
            }
        else:
            return {
                "provider": "Offline Heuristic Mock",
                "is_live": False,
                "model": "deterministic-mock",
                "masked_key": None,
            }

    def complete(self, prompt: str, system_instruction: str = "") -> str:
        """Dispatches completion request to live API (Gemini / OpenAI) with automatic mock fallback."""
        self.last_error = None

        # 1. Try Google Gemini
        if self.gemini_key:
            res = self._call_gemini(prompt, system_instruction)
            if res:
                self.last_provider_used = "gemini"
                return res

        # 2. Try OpenAI
        if self.openai_key:
            res = self._call_openai(prompt, system_instruction)
            if res:
                self.last_provider_used = "openai"
                return res

        # 3. Fallback to offline mock
        self.last_provider_used = "mock"
        return ""

    def test_connection(self) -> Tuple[bool, str]:
        """Tests connectivity and latency against the active live LLM provider."""
        status = self.get_status()
        if not status["is_live"]:
            return False, "No API key configured. Operating in Offline Mock mode."

        start_time = time.time()
        test_prompt = "Say 'OK' and nothing else."

        try:
            if self.gemini_key:
                resp = self._call_gemini_rest(test_prompt, system_instruction="Be concise.")
                elapsed = time.time() - start_time
                if resp:
                    return True, f"Google Gemini API connected successfully ({resp[:30]!r}, latency: {elapsed:.2f}s)"
                else:
                    return False, f"Google Gemini API failed: {self.last_error or 'Empty response'}"

            elif self.openai_key:
                resp = self._call_openai_rest(test_prompt, system_instruction="Be concise.")
                elapsed = time.time() - start_time
                if resp:
                    return True, f"OpenAI API connected successfully ({resp[:30]!r}, latency: {elapsed:.2f}s)"
                else:
                    return False, f"OpenAI API failed: {self.last_error or 'Empty response'}"

        except Exception as e:
            return False, f"Connection error: {e}"

        return False, "Unknown connection failure."

    # -------------------------------------------------------------------------
    # Internal REST Call Implementations (Zero External Dependencies)
    # -------------------------------------------------------------------------

    def _call_gemini(self, prompt: str, system_instruction: str = "") -> Optional[str]:
        # Priority: Native urllib REST call (works anywhere without pip install)
        return self._call_gemini_rest(prompt, system_instruction)

    def _call_gemini_rest(self, prompt: str, system_instruction: str = "") -> Optional[str]:
        """Native REST request to Gemini models using Python urllib."""
        models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]

        payload_dict: Dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ]
        }
        if system_instruction:
            payload_dict["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        data = json.dumps(payload_dict).encode("utf-8")

        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_key}"
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=12) as response:
                    res_json = json.loads(response.read().decode("utf-8"))
                    candidates = res_json.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
            except urllib.error.HTTPError as he:
                error_body = he.read().decode("utf-8", errors="ignore")
                self.last_error = f"HTTP {he.code}: {he.reason} - {error_body}"
                # If model not found (404), try next model in loop; otherwise break
                if he.code != 404:
                    break
            except Exception as e:
                self.last_error = str(e)
                break

        return None

    def _call_openai(self, prompt: str, system_instruction: str = "") -> Optional[str]:
        return self._call_openai_rest(prompt, system_instruction)

    def _call_openai_rest(self, prompt: str, system_instruction: str = "") -> Optional[str]:
        """Native REST request to OpenAI chat completions using Python urllib."""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_key}",
        }
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        data = json.dumps({
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": 0.1,
        }).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                return res_json["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as he:
            error_body = he.read().decode("utf-8", errors="ignore")
            self.last_error = f"HTTP {he.code}: {he.reason} - {error_body}"
        except Exception as e:
            self.last_error = str(e)

        return None

    def _mask_key(self, key: str) -> str:
        if len(key) <= 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"
