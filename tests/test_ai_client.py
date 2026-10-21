"""Unit Tests for LLMClient and AI Edge Integrations.

Course: BCSE307P - Compiler Design Lab
Authors:
  - Gaurav Gopichand Nanhe (24BCB0020)
  - V Surya (24BAI0351)
"""

import unittest
from ai.llm_client import LLMClient, MockLLMProvider
from ai.nl_to_sql import NLToSQLTranslator
from ai.error_explainer import AIErrorExplainer
from lexer.errors import DiagnosticRecord


class TestAIClient(unittest.TestCase):

    def test_offline_mock_mode_when_no_keys(self):
        client = LLMClient()
        # Ensure offline mode if no env key
        if not client.gemini_key and not client.openai_key:
            status = client.get_status()
            self.assertFalse(status["is_live"])
            self.assertEqual(status["provider"], "Offline Heuristic Mock")
            self.assertIsNone(status["masked_key"])

    def test_gemini_key_detection(self):
        client = LLMClient(api_key="AIzaSyTestGeminiKey123456789")
        status = client.get_status()
        self.assertTrue(status["is_live"])
        self.assertEqual(status["provider"], "Google Gemini")
        self.assertEqual(status["model"], "gemini-2.5-flash")
        self.assertEqual(status["masked_key"], "AIza...6789")

    def test_openai_key_detection(self):
        client = LLMClient(api_key="sk-testOpenAIKey987654321")
        status = client.get_status()
        self.assertTrue(status["is_live"])
        self.assertEqual(status["provider"], "OpenAI")
        self.assertEqual(status["model"], "gpt-4o-mini")
        self.assertEqual(status["masked_key"], "sk-t...4321")

    def test_dynamic_set_api_key(self):
        client = LLMClient()
        client.set_api_key("AIzaSyNewRuntimeKey999")
        status = client.get_status()
        self.assertEqual(status["provider"], "Google Gemini")
        self.assertTrue(status["is_live"])

    def test_test_connection_no_key(self):
        client = LLMClient()
        client.gemini_key = None
        client.openai_key = None
        ok, msg = client.test_connection()
        self.assertFalse(ok)
        self.assertIn("Offline Mock mode", msg)

    def test_mock_nl_to_sql(self):
        translator = NLToSQLTranslator()
        # Test heuristic translation
        sql = translator.translate("Find all customers living in Delhi")
        self.assertIn("SELECT", sql)
        self.assertIn("customers", sql)
        self.assertIn("Delhi", sql)

    def test_mock_error_explainer(self):
        explainer = AIErrorExplainer()
        diag = DiagnosticRecord(
            phase="SEMANTIC_ANALYSIS",
            error_code="ERR_COLUMN_NOT_FOUND",
            message="Column 'full_name' does not exist in table 'customers'.",
            line=1,
            column=8,
            context="SELECT full_name FROM customers",
            available_columns=["id", "name", "city", "signup_date"],
            suggestion="name",
        )
        explanation = explainer.explain(diag)
        self.assertIn("schema", explanation.lower())
        self.assertIn("column", explanation.lower())


if __name__ == "__main__":
    unittest.main()
