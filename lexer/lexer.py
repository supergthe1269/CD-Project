"""Hand-written Lexical Analyzer (Tokenizer) for SQL Subset.

Scans the input character-by-character, maintaining precise line and column numbers.
No external generator tools (e.g., Flex, ANTLR, PLY) are used.
"""

from typing import List, Optional
from .tokens import Token, TokenType, KEYWORDS, AGG_FUNCS
from .errors import LexicalError


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.length = len(source)
        self.cursor = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []

    def _peek(self, offset: int = 0) -> Optional[str]:
        pos = self.cursor + offset
        if pos < self.length:
            return self.source[pos]
        return None

    def _advance(self) -> Optional[str]:
        if self.cursor >= self.length:
            return None
        ch = self.source[self.cursor]
        self.cursor += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _get_line_context(self, target_line: int) -> str:
        lines = self.source.splitlines()
        if 1 <= target_line <= len(lines):
            return lines[target_line - 1]
        return ""

    def tokenize(self) -> List[Token]:
        self.tokens = []
        self.cursor = 0
        self.line = 1
        self.column = 1

        while self.cursor < self.length:
            start_line = self.line
            start_col = self.column
            ch = self._peek()

            # 1. Skip Whitespace
            if ch in (" ", "\t", "\r", "\n"):
                self._advance()
                continue

            # 2. Skip Single-line Comments (-- ...)
            if ch == "-" and self._peek(1) == "-":
                self._advance()  # -
                self._advance()  # -
                while self._peek() is not None and self._peek() != "\n":
                    self._advance()
                continue

            # 3. String Literals ('...')
            if ch == "'":
                token = self._read_string(start_line, start_col)
                self.tokens.append(token)
                continue

            # 4. Numeric Literals (e.g., 42, 3.14159)
            if ch.isdigit():
                token = self._read_number(start_line, start_col)
                self.tokens.append(token)
                continue

            # 5. Identifiers and Keywords
            if ch.isalpha() or ch == "_":
                token = self._read_identifier_or_keyword(start_line, start_col)
                self.tokens.append(token)
                continue

            # 6. Two-character Relational Operators
            if ch == "!" and self._peek(1) == "=":
                self._advance()
                self._advance()
                self.tokens.append(Token(TokenType.NOT_EQUALS, "!=", start_line, start_col))
                continue
            if ch == "<" and self._peek(1) == "=":
                self._advance()
                self._advance()
                self.tokens.append(Token(TokenType.LESS_EQUALS, "<=", start_line, start_col))
                continue
            if ch == ">" and self._peek(1) == "=":
                self._advance()
                self._advance()
                self.tokens.append(Token(TokenType.GREATER_EQUALS, ">=", start_line, start_col))
                continue
            if ch == "<" and self._peek(1) == ">":
                self._advance()
                self._advance()
                self.tokens.append(Token(TokenType.NOT_EQUALS, "!=", start_line, start_col))
                continue

            # 7. Single-character Operators and Punctuation
            if ch == "=":
                self._advance()
                self.tokens.append(Token(TokenType.EQUALS, "=", start_line, start_col))
                continue
            if ch == "<":
                self._advance()
                self.tokens.append(Token(TokenType.LESS_THAN, "<", start_line, start_col))
                continue
            if ch == ">":
                self._advance()
                self.tokens.append(Token(TokenType.GREATER_THAN, ">", start_line, start_col))
                continue
            if ch == "(":
                self._advance()
                self.tokens.append(Token(TokenType.LPAREN, "(", start_line, start_col))
                continue
            if ch == ")":
                self._advance()
                self.tokens.append(Token(TokenType.RPAREN, ")", start_line, start_col))
                continue
            if ch == ",":
                self._advance()
                self.tokens.append(Token(TokenType.COMMA, ",", start_line, start_col))
                continue
            if ch == ".":
                self._advance()
                self.tokens.append(Token(TokenType.DOT, ".", start_line, start_col))
                continue
            if ch == "*":
                self._advance()
                self.tokens.append(Token(TokenType.STAR, "*", start_line, start_col))
                continue
            if ch == ";":
                self._advance()
                self.tokens.append(Token(TokenType.SEMICOLON, ";", start_line, start_col))
                continue

            # 8. Unrecognized / Invalid Character
            bad_char = self._advance()
            line_ctx = self._get_line_context(start_line)
            raise LexicalError(
                message=f"Unexpected or invalid character '{bad_char}'",
                line=start_line,
                column=start_col,
                error_code="ERR_INVALID_CHARACTER",
                context=line_ctx,
                char=bad_char,
            )

        # End Of File
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column))
        return self.tokens

    def _read_string(self, start_line: int, start_col: int) -> Token:
        self._advance()  # consume opening quote
        chars = []
        while True:
            ch = self._peek()
            if ch is None or ch == "\n":
                line_ctx = self._get_line_context(start_line)
                raise LexicalError(
                    message="Unterminated string literal",
                    line=start_line,
                    column=start_col,
                    error_code="ERR_UNTERMINATED_STRING",
                    context=line_ctx,
                )
            if ch == "'":
                # Check for escaped single quote ''
                if self._peek(1) == "'":
                    self._advance()
                    self._advance()
                    chars.append("'")
                    continue
                else:
                    self._advance()  # consume closing quote
                    break
            elif ch == "\\":
                # Backslash escape support
                self._advance()
                next_ch = self._peek()
                if next_ch is not None:
                    chars.append(self._advance())
                continue
            else:
                chars.append(self._advance())

        return Token(TokenType.STRING, "".join(chars), start_line, start_col)

    def _read_number(self, start_line: int, start_col: int) -> Token:
        chars = []
        is_float = False

        while self._peek() is not None and self._peek().isdigit():
            chars.append(self._advance())

        if self._peek() == "." and self._peek(1) is not None and self._peek(1).isdigit():
            is_float = True
            chars.append(self._advance())  # .
            while self._peek() is not None and self._peek().isdigit():
                chars.append(self._advance())

        val_str = "".join(chars)
        value = float(val_str) if is_float else int(val_str)
        return Token(TokenType.NUMBER, value, start_line, start_col)

    def _read_identifier_or_keyword(self, start_line: int, start_col: int) -> Token:
        chars = []
        while self._peek() is not None and (self._peek().isalnum() or self._peek() == "_"):
            chars.append(self._advance())

        ident = "".join(chars)
        upper = ident.upper()

        if upper in KEYWORDS:
            return Token(KEYWORDS[upper], upper, start_line, start_col)
        elif upper in AGG_FUNCS:
            return Token(AGG_FUNCS[upper], upper, start_line, start_col)
        else:
            return Token(TokenType.IDENTIFIER, ident, start_line, start_col)
