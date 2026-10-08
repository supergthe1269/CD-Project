from enum import Enum, auto
from dataclasses import dataclass

class TokenType(Enum):
    KEYWORD = auto()
    AGG_FUNC = auto()
    IDENTIFIER = auto()
    INTEGER = auto()
    FLOAT = auto()
    STRING = auto()
    OPERATOR = auto()
    PUNCTUATION = auto()
    FLAGGED = auto()
    EOF = auto()

@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int

KEYWORDS = {"SELECT", "DISTINCT", "FROM", "WHERE", "GROUP", "BY", "HAVING", 
            "ORDER", "LIMIT", "JOIN", "INNER", "LEFT", "OUTER", "NATURAL", 
            "CROSS", "ON", "AND", "OR", "NOT", "IN", "LIKE", "BETWEEN", 
            "IS", "NULL", "AS", "ASC", "DESC"}
AGGREGATES = {"COUNT", "SUM", "AVG", "MIN", "MAX"}
FLAGGED = {"RIGHT", "FULL", "UNION", "INTERSECT", "EXCEPT", "USING"}
OPERATORS = {"=", "!=", "<>", "<", ">", "<=", ">="}
PUNCTUATION = {"(", ")", ",", ".", "*", ";", "-"}