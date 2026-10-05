"""Lexical analysis error types and diagnostics."""

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any


@dataclass
class DiagnosticRecord:
    phase: str
    error_code: str
    message: str
    line: int
    column: int
    context: str
    available_columns: Optional[list[str]] = None
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Drop None fields for cleaner JSON
        return {k: v for k, v in data.items() if v is not None}


class LexicalError(Exception):
    """Exception raised when an invalid token or character is encountered."""

    def __init__(
        self,
        message: str,
        line: int,
        column: int,
        error_code: str = "ERR_LEXICAL",
        context: str = "",
        char: Optional[str] = None,
    ):
        super().__init__(f"[{error_code}] Line {line}, Col {column}: {message}")
        self.message = message
        self.line = line
        self.column = column
        self.error_code = error_code
        self.context = context
        self.char = char

    def to_diagnostic(self) -> DiagnosticRecord:
        return DiagnosticRecord(
            phase="LEXICAL_ANALYSIS",
            error_code=self.error_code,
            message=self.message,
            line=self.line,
            column=self.column,
            context=self.context,
        )
