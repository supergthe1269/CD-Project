"""Error types and diagnostics for NoSQL Compiler Pipeline.

Course: BCSE307P - Compiler Design Lab
"""

from typing import Optional, List
from lexer.errors import DiagnosticRecord


class NoSQLLexicalError(Exception):
    def __init__(self, message: str, line: int, column: int, error_code: str = "ERR_NOSQL_LEXICAL"):
        super().__init__(f"[{error_code}] Line {line}, Col {column}: {message}")
        self.message = message
        self.line = line
        self.column = column
        self.error_code = error_code

    def to_diagnostic(self) -> DiagnosticRecord:
        return DiagnosticRecord(
            phase="NOSQL_LEXICAL_ANALYSIS",
            error_code=self.error_code,
            message=self.message,
            line=self.line,
            column=self.column,
            context="",
        )


class NoSQLParserSyntaxError(Exception):
    def __init__(
        self,
        message: str,
        line: int,
        column: int,
        expected: Optional[str] = None,
        found: Optional[str] = None,
        error_code: str = "ERR_NOSQL_SYNTAX",
    ):
        super().__init__(f"[{error_code}] Line {line}, Col {column}: {message}")
        self.message = message
        self.line = line
        self.column = column
        self.expected = expected
        self.found = found
        self.error_code = error_code

    def to_diagnostic(self) -> DiagnosticRecord:
        return DiagnosticRecord(
            phase="NOSQL_SYNTAX_ANALYSIS",
            error_code=self.error_code,
            message=self.message,
            line=self.line,
            column=self.column,
            context=f"Expected: {self.expected}, Found: {self.found}" if self.expected else "",
        )


class NoSQLSemanticError(Exception):
    def __init__(
        self,
        message: str,
        line: int = 1,
        column: int = 1,
        error_code: str = "ERR_NOSQL_SEMANTIC",
        available_columns: Optional[List[str]] = None,
        suggestion: Optional[str] = None,
    ):
        super().__init__(f"[{error_code}] Line {line}, Col {column}: {message}")
        self.message = message
        self.line = line
        self.column = column
        self.error_code = error_code
        self.available_columns = available_columns
        self.suggestion = suggestion

    def to_diagnostic(self) -> DiagnosticRecord:
        return DiagnosticRecord(
            phase="NOSQL_SEMANTIC_ANALYSIS",
            error_code=self.error_code,
            message=self.message,
            line=self.line,
            column=self.column,
            context="",
            available_columns=self.available_columns,
            suggestion=self.suggestion,
        )
