"""Semantic analysis error definitions and structured diagnostics."""

from typing import Optional, List, Dict, Any
from lexer.errors import DiagnosticRecord


class SemanticError(Exception):
    """Exception raised when a query fails semantic validation."""

    def __init__(
        self,
        message: str,
        error_code: str = "ERR_SEMANTIC",
        line: int = 1,
        column: int = 1,
        context: str = "",
        available_columns: Optional[List[str]] = None,
        suggestion: Optional[str] = None,
    ):
        super().__init__(f"[{error_code}] Line {line}, Col {column}: {message}")
        self.message = message
        self.error_code = error_code
        self.line = line
        self.column = column
        self.context = context
        self.available_columns = available_columns
        self.suggestion = suggestion

    def to_diagnostic(self) -> DiagnosticRecord:
        return DiagnosticRecord(
            phase="SEMANTIC_ANALYSIS",
            error_code=self.error_code,
            message=self.message,
            line=self.line,
            column=self.column,
            context=self.context,
            available_columns=self.available_columns,
            suggestion=self.suggestion,
        )
