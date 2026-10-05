"""Semantic Analysis Package for SQL Query Validator."""

from .catalog import DatabaseCatalog, TableSchema, ColumnSchema, create_default_catalog
from .symbol_table import SymbolTable
from .fuzzy import levenshtein_distance, find_closest_identifier
from .errors import SemanticError
from .checker import SemanticChecker

__all__ = [
    "DatabaseCatalog",
    "TableSchema",
    "ColumnSchema",
    "create_default_catalog",
    "SymbolTable",
    "levenshtein_distance",
    "find_closest_identifier",
    "SemanticError",
    "SemanticChecker",
]
