"""AI Error Explainer & Diagnostic Mentor (AI Output Edge).

Translates strongly-typed DiagnosticRecords from the compiler pipeline
into beginner-friendly, plain-English remediation steps while preserving
the raw compiler coordinates.
"""

import json
from typing import Optional
from .llm_client import LLMClient
from lexer.errors import DiagnosticRecord

EXPLAINER_PROMPT = """You are a supportive Compiler Diagnostic Mentor.
You are given a structured compiler diagnostic record representing a lexical, syntax, or semantic error in an SQL query.
Your goal is to explain the problem in clear, plain English without overwhelming compiler jargon, and provide an actionable fix.

Diagnostic Record:
{record_json}

Provide:
1. A 1-2 sentence explanation of why this error occurred.
2. A clear recommended fix or correction.
Keep it direct, professional, and friendly.
"""


class AIErrorExplainer:
    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or LLMClient()

    def explain(self, diagnostic: DiagnosticRecord) -> str:
        record_json = json.dumps(diagnostic.to_dict(), indent=2)
        prompt = EXPLAINER_PROMPT.format(record_json=record_json)

        explanation = self.client.complete(
            prompt=prompt,
            system_instruction="You are an expert compiler pedagogical assistant.",
        )

        if not explanation:
            # Fallback to local heuristic mock
            return self.client.mock.explain_diagnostic(diagnostic)

        return explanation.strip()
