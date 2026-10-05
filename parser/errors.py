"""Parser syntax error types and diagnostics."""

from typing import Optional
from lexer.tokens import Token
from lexer.errors import DiagnosticRecord


class ParserSyntaxError(Exception):
    """Exception raised when syntax does not conform to the EBNF grammar."""

    def __init__(
        self,
        message: str,
        token: Optional[Token] = None,
        expected: Optional[str] = None,
        error_code: str = "ERR_SYNTAX",
        context: str = "",
    ):
        line = token.line if token else 1
        col = token.column if token else 1
        found = f"'{token.value}'" if token else "EOF"
        full_msg = f"[{error_code}] Line {line}, Col {col}: {message}"
        if expected:
            full_msg += f" (Expected: {expected}, Found: {found})"
        super().__init__(full_msg)

        self.message = message
        self.token = token
        self.expected = expected
        self.error_code = error_code
        self.line = line
        self.column = col
        self.context = context

    def to_diagnostic(self) -> DiagnosticRecord:
        msg = self.message
        if self.expected:
            found = f"'{self.token.value}'" if self.token else "EOF"
            msg = f"{self.message} (Expected: {self.expected}, Found: {found})"
        return DiagnosticRecord(
            phase="SYNTAX_ANALYSIS",
            error_code=self.error_code,
            message=msg,
            line=self.line,
            column=self.column,
            context=self.context,
        )
