from dataclasses import dataclass

@dataclass
class DiagnosticRecord:
    error_code: str
    line: int
    column: int
    found: str
    expected: str = ""
    context: str = ""

class LexicalError(Exception):
    def __init__(self, diagnostic: DiagnosticRecord):
        self.diagnostic = diagnostic
        super().__init__(f"{diagnostic.error_code} at {diagnostic.line}:{diagnostic.column}")