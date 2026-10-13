"""Token definitions for NoSQL (MongoDB MQL) Lexical Analysis.

Course: BCSE307P - Compiler Design Lab
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import Any


class NoSQLTokenType(Enum):
    DB = auto()              # 'db'
    IDENTIFIER = auto()      # collection names, method names, unquoted keys
    OPERATOR = auto()        # $gt, $match, $group, etc.
    STRING = auto()          # 'delhi', "Delhi"
    NUMBER = auto()          # 42, 3.14
    BOOLEAN = auto()         # true, false
    NULL = auto()            # null

    # Punctuation
    DOT = auto()             # .
    LPAREN = auto()          # (
    RPAREN = auto()          # )
    LBRACE = auto()          # {
    RBRACE = auto()          # }
    LBRACKET = auto()        # [
    RBRACKET = auto()        # ]
    COLON = auto()           # :
    COMMA = auto()           # ,
    EOF = auto()


@dataclass
class NoSQLToken:
    type: NoSQLTokenType
    value: Any
    line: int
    column: int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, L{self.line}:C{self.column})"
