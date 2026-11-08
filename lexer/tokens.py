"""Token types and Token dataclass for SQL Lexical Analysis."""

from enum import Enum, auto
from dataclasses import dataclass
from typing import Any


class TokenType(Enum):
    # Keywords
    SELECT = auto()
    FROM = auto()
    WHERE = auto()
    JOIN = auto()
    INNER = auto()
    LEFT = auto()
    ON = auto()
    GROUP = auto()
    BY = auto()
    HAVING = auto()
    ORDER = auto()
    LIMIT = auto()
    AND = auto()
    OR = auto()
    AS = auto()
    ASC = auto()
    DESC = auto()

    # Aggregate Functions
    COUNT = auto()
    SUM = auto()
    AVG = auto()
    MIN = auto()
    MAX = auto()

    # Identifiers & Literals
    IDENTIFIER = auto()
    NUMBER = auto()
    STRING = auto()

    # Relational Operators
    EQUALS = auto()           # =
    NOT_EQUALS = auto()       # !=
    LESS_THAN = auto()        # <
    GREATER_THAN = auto()     # >
    LESS_EQUALS = auto()      # <=
    GREATER_EQUALS = auto()   # >=

    # Punctuation & Delimiters
    LPAREN = auto()           # (
    RPAREN = auto()           # )
    COMMA = auto()            # ,
    DOT = auto()              # .
    STAR = auto()             # *
    SEMICOLON = auto()        # ;

    # End of Input
    EOF = auto()


# Keyword and Aggregate lookup maps (case-insensitive)
KEYWORDS = {
    "SELECT": TokenType.SELECT,
    "FROM": TokenType.FROM,
    "WHERE": TokenType.WHERE,
    "JOIN": TokenType.JOIN,
    "INNER": TokenType.INNER,
    "LEFT": TokenType.LEFT,
    "ON": TokenType.ON,
    "GROUP": TokenType.GROUP,
    "BY": TokenType.BY,
    "HAVING": TokenType.HAVING,
    "ORDER": TokenType.ORDER,
    "LIMIT": TokenType.LIMIT,
    "AND": TokenType.AND,
    "OR": TokenType.OR,
    "AS": TokenType.AS,
    "ASC": TokenType.ASC,
    "DESC": TokenType.DESC,
}

AGG_FUNCS = {
    "COUNT": TokenType.COUNT,
    "SUM": TokenType.SUM,
    "AVG": TokenType.AVG,
    "MIN": TokenType.MIN,
    "MAX": TokenType.MAX,
}


@dataclass
class Token:
    type: TokenType
    value: Any
    line: int
    column: int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, L{self.line}:C{self.column})"
