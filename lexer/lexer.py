# lexer using fail-fast approach - error immeadiately upon failure

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from records.common import DiagnosticRecord, LexicalError
from lexer.tokens import Token, TokenType, KEYWORDS, AGGREGATES, OPERATORS, FLAGGED, PUNCTUATION


# 1-based lexer at token's first character
class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.line = 1
        self.column = 1
        self.pos = 0

    # To look at the kth character from cursor position without consuming any characters. Return character if exist else None
    def peek(self, k: int = 0):
        idx = self.pos + k
        if idx > len(self.source):
            return None
        return self.source[idx]

    # To advance one step forward in the source, consumes the current character. If current char is newline character then incr row and reset column to 1
    def advance(self):
        char = self.source[self.pos]
        self.pos += 1
        if char == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1

        return char

    # To skip whitespaces and comments
    def skip_trivia(self):
        while True:
            char = self.peek()
            if char is None:
                break
            if char in ' \t\r\n':
                self.advance()
            elif char == '-' and self.peek(1) == '-':
                while self.peek() not in (None, '\n'): # keep consuming characters until end of line of new line
                    self.advance()
            else:
                break

    # To read a word and return valid token
    def read_word(self, start_line: int, start_col: int):
        chars = []
        while True:
            c = self.peek()
            if c is not None and (c.isalnum() or c == '_'):
                chars.append(self.advance())
            else:
                break
        word = "".join(chars)
        up_case = word.upper()


        if up_case in AGGREGATES:
            return Token(TokenType.AGG_FUNC, up_case, start_line, start_col)
        if up_case in KEYWORDS:
            return Token(TokenType.KEYWORD, up_case, start_line, start_col)
        if up_case in FLAGGED:
            return Token(TokenType.FLAGGED, up_case, start_line, start_col)

        return Token(TokenType.IDENTIFIER, up_case, start_line, start_col)

    def read_number(self, start_line: int, start_col: int):
        chars = []
        while self.peek() is not None and self.peek().isdigit():
            chars.append(self.advance())

        if self.peek() == '.' and self.peek(1) is not None and self.peek(1).isdigit():
            chars.append(self.advance())
            while self.peek() is not None and self.peek().isdigit():
                chars.append(self.advance())
            return Token(TokenType.FLOAT, "".join(chars), start_line, start_col)

        return Token(TokenType.INTEGER, "".join(chars), start_line, start_col)

    def read_string(self, start_line: int, start_col: int):
        self.advance()
        chars = []
        while True:
            c = self.peek()
            if c is None: 
                raise LexicalError(DiagnosticRecord('ERR_UNTERMINATED_STRING', start_line, start_col, found="EOF"))
            if c == "'":
                self.advance()
                break
            chars.append(self.advance())

        return Token(TokenType.STRING, "".join(chars), start_line, start_col)

    def read_operator(self, start_line: int, start_col: int):
        char = self.advance()
        char_next = self.peek()

        if char == '<':
            if char_next in ('=', '>'):
                return Token(TokenType.OPERATOR, char + self.advance(), start_line, start_col)
            return Token(TokenType.OPERATOR, char, start_line, start_col)
        elif char == '>':
            if char_next == '=':
                return Token(TokenType.OPERATOR, char + self.advance(), start_line, start_col)
            return Token(TokenType.OPERATOR, char, start_line, start_col)
        elif char == '=':
            return Token(TokenType.OPERATOR, char, start_line, start_col)
        elif char == '!':
            if char_next == '=':
                return Token(TokenType.OPERATOR, char + self.advance(), start_line, start_col)
            raise LexicalError(DiagnosticRecord('ERR_ILLEGAL_CHARACTER', start_line, start_col, found=char))
                
    def tokenize(self):
        tokens = []
        while True:
            self.skip_trivia()
            if self.peek() is None:
                break

            L, C = self.line, self.column
            c = self.peek()

            if c.isalnum() or c == '_':
                tokens.append(self.read_word(L, C))
            elif c.isdigit():
                tokens.append(self.read_number(L, C))
            elif c == "'":
                tokens.append(self.read_string(L, C))
            elif c in "<>!=":
                tokens.append(self.read_operator(L, C))
            elif c in PUNCTUATION:
                tokens.append(Token(TokenType.PUNCTUATION, c, L, C))
            else:
                self.advance()
                raise LexicalError(DiagnosticRecord('ERR_ILLEGAL_CHARACTER', L, C, found=c))

        tokens.append(Token(TokenType.EOF, "", self.line, self.column))
        return tokens

def tokenise(source: str) -> list[Token]:
    return Lexer(source).tokenize()

if __name__ == '__init__':
    tokens = tokenise('SELECT c.name FROM customers c WHERE id >= -3.5;')
    print(tokens)
