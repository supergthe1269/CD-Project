"""Target Code Generation & Synthesis (SQL AST to MongoDB MQL Transpiler).

Course: BCSE307P - Compiler Design Lab
Part of Review 2 Multi-Model Compiler Extension.
"""

from .nosql_transpiler import NoSQLTranspiler, MQLResult

__all__ = ["NoSQLTranspiler", "MQLResult"]
