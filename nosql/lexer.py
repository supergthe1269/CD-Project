"""Hand-crafted Lexical Analyzer (Scanner) for MongoDB MQL queries.

Course: BCSE307P - Compiler Design Lab
"""

from typing import List, Optional
from .tokens import NoSQLToken, NoSQLTokenType
from .errors import NoSQLLexicalError


class NoSQLLexer:
    """Character-by-character scanner for MongoDB MQL syntax."""

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.length = len(source)

    def tokenize(self) -> List[NoSQLToken]:
        tokens: List[NoSQLToken] = []

        while self.pos < self.length:
            self._skip_whitespace_and_comments()
            if self.pos >= self.length:
                break

            ch = self.source[self.pos]
            start_col = self.column
            start_line = self.line

            # Single-character punctuation
            if ch == ".":
                tokens.append(self._make_token(NoSQLTokenType.DOT, "."))
            elif ch == "(":
                tokens.append(self._make_token(NoSQLTokenType.LPAREN, "("))
            elif ch == ")":
                tokens.append(self._make_token(NoSQLTokenType.RPAREN, ")"))
            elif ch == "{":
                tokens.append(self._make_token(NoSQLTokenType.LBRACE, "{"))
            elif ch == "}":
                tokens.append(self._make_token(NoSQLTokenType.RBRACE, "}"))
            elif ch == "[":
                tokens.append(self._make_token(NoSQLTokenType.LBRACKET, "["))
            elif ch == "]":
                tokens.append(self._make_token(NoSQLTokenType.RBRACKET, "]"))
            elif ch == ":":
                tokens.append(self._make_token(NoSQLTokenType.COLON, ":"))
            elif ch == ",":
                tokens.append(self._make_token(NoSQLTokenType.COMMA, ","))

            # Strings
            elif ch in ('"', "'"):
                tokens.append(self._read_string(ch))

            # Numbers (positive, negative, float)
            elif ch.isdigit() or (ch == "-" and self._peek_char().isdigit()):
                tokens.append(self._read_number())

            # Identifiers and $operators
            elif ch.isalpha() or ch in ("_", "$"):
                tokens.append(self._read_identifier())

            else:
                raise NoSQLLexicalError(
                    f"Unexpected character {ch!r} in NoSQL query",
                    line=self.line,
                    column=self.column,
                )

        tokens.append(NoSQLToken(NoSQLTokenType.EOF, None, self.line, self.column))
        return tokens

    def _make_token(self, token_type: NoSQLTokenType, value: str) -> NoSQLToken:
        tok = NoSQLToken(token_type, value, self.line, self.column)
        self._advance()
        return tok

    def _advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _peek_char(self) -> str:
        if self.pos + 1 < self.length:
            return self.source[self.pos + 1]
        return ""

    def _skip_whitespace_and_comments(self) -> None:
        while self.pos < self.length:
            ch = self.source[self.pos]
            if ch in (" ", "\t", "\r", "\n"):
                self._advance()
            # Line comment: //
            elif ch == "/" and self._peek_char() == "/":
                while self.pos < self.length and self.source[self.pos] != "\n":
                    self._advance()
            # Semicolon at end of shell statement
            elif ch == ";":
                self._advance()
            else:
                break

    def _read_string(self, quote_char: str) -> NoSQLToken:
        start_line = self.line
        start_col = self.column
        self._advance()  # Skip opening quote

        chars = []
        while self.pos < self.length:
            ch = self.source[self.pos]
            if ch == quote_char:
                self._advance()  # Skip closing quote
                val = "".join(chars)
                # If string starts with $, treat as operator or identifier depending on context
                return NoSQLToken(NoSQLTokenType.STRING, val, start_line, start_col)
            elif ch == "\\":
                self._advance()
                if self.pos < self.length:
                    escaped = self._advance()
                    if escaped == "n":
                        chars.append("\n")
                    elif escaped == "t":
                        chars.append("\t")
                    else:
                        chars.append(escaped)
            elif ch == "\n":
                raise NoSQLLexicalError("Unterminated string literal", line=start_line, column=start_col)
            else:
                chars.append(self._advance())

        raise NoSQLLexicalError("Unterminated string literal at EOF", line=start_line, column=start_col)

    def _read_number(self) -> NoSQLToken:
        start_line = self.line
        start_col = self.column
        chars = []

        if self.source[self.pos] == "-":
            chars.append(self._advance())

        is_float = False
        while self.pos < self.length:
            ch = self.source[self.pos]
            if ch.isdigit():
                chars.append(self._advance())
            elif ch == "." and not is_float and self._peek_char().isdigit():
                is_float = True
                chars.append(self._advance())
            else:
                break

        num_str = "".join(chars)
        val = float(num_str) if is_float else int(num_str)
        return NoSQLToken(NoSQLTokenType.NUMBER, val, start_line, start_col)

    def _read_identifier(self) -> NoSQLToken:
        start_line = self.line
        start_col = self.column
        chars = []

        while self.pos < self.length:
            ch = self.source[self.pos]
            if ch.isalnum() or ch in ("_", "$"):
                chars.append(self._advance())
            else:
                break

        val = "".join(chars)
        if val == "db":
            return NoSQLToken(NoSQLTokenType.DB, val, start_line, start_col)
        elif val == "true":
            return NoSQLToken(NoSQLTokenType.BOOLEAN, True, start_line, start_col)
        elif val == "false":
            return NoSQLToken(NoSQLTokenType.BOOLEAN, False, start_line, start_col)
        elif val == "null":
            return NoSQLToken(NoSQLTokenType.NULL, None, start_line, start_col)
        elif val.startswith("$"):
            return NoSQLToken(NoSQLTokenType.OPERATOR, val, start_line, start_col)
        else:
            return NoSQLToken(NoSQLTokenType.IDENTIFIER, val, start_line, start_col)
