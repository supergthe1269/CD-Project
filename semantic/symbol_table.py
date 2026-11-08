"""Symbol Table and Scope resolution for SQL Semantic Analysis."""

from typing import Dict, List, Optional, Tuple
from .catalog import DatabaseCatalog, TableSchema, ColumnSchema
from .errors import SemanticError
from .fuzzy import find_closest_identifier


class SymbolTable:
    """
    Maintains active table scopes, aliases, and column bindings
    for the current query execution context.
    """

    def __init__(self, catalog: DatabaseCatalog, source: str = ""):
        self.catalog = catalog
        self.source = source
        # Mapping from alias/name to TableSchema
        self.scope_tables: Dict[str, TableSchema] = {}
        # List of distinct base tables in scope
        self.active_base_tables: List[TableSchema] = []

    def _get_context(self, line: int) -> str:
        lines = self.source.splitlines()
        if 1 <= line <= len(lines):
            return lines[line - 1]
        return ""

    def register_table(
        self,
        table_name: str,
        alias: Optional[str] = None,
        line: int = 1,
        column: int = 1,
    ) -> TableSchema:
        """Resolves table against catalog and registers it and its alias in scope."""
        schema = self.catalog.get_table(table_name)
        if not schema:
            closest = find_closest_identifier(table_name, self.catalog.table_names())
            suggestion = f"Did you mean '{closest[0]}'?" if closest else None
            raise SemanticError(
                message=f"Table '{table_name}' does not exist in catalog.",
                error_code="ERR_TABLE_NOT_FOUND",
                line=line,
                column=column,
                context=self._get_context(line),
                suggestion=suggestion,
            )

        if schema not in self.active_base_tables:
            self.active_base_tables.append(schema)

        # Register by table name
        self.scope_tables[table_name.lower()] = schema

        # Register by alias
        if alias:
            alias_lower = alias.lower()
            if alias_lower in self.scope_tables and self.scope_tables[alias_lower] != schema:
                raise SemanticError(
                    message=f"Duplicate table alias '{alias}' in query scope.",
                    error_code="ERR_DUPLICATE_ALIAS",
                    line=line,
                    column=column,
                    context=self._get_context(line),
                )
            self.scope_tables[alias_lower] = schema

        return schema

    def resolve_table_scope(self, prefix_or_name: str) -> Optional[TableSchema]:
        """Resolves an alias or table name in current query scope."""
        return self.scope_tables.get(prefix_or_name.lower())

    def get_all_available_columns(self) -> List[str]:
        """Returns list of all column names across all tables currently in scope."""
        cols: List[str] = []
        for tbl in self.active_base_tables:
            cols.extend(tbl.column_names())
        return list(dict.fromkeys(cols))

    def resolve_column(
        self,
        column_name: str,
        table_prefix: Optional[str] = None,
        line: int = 1,
        column: int = 1,
    ) -> Tuple[TableSchema, ColumnSchema]:
        """
        Resolves a column to its TableSchema and ColumnSchema.
        Detects nonexistent columns, ambiguous columns across JOINs,
        and provides fuzzy auto-correction suggestions.
        """
        # Case 1: Qualified column reference (e.g. c.name or customers.name)
        if table_prefix:
            tbl_schema = self.resolve_table_scope(table_prefix)
            if not tbl_schema:
                raise SemanticError(
                    message=f"Unknown table or alias '{table_prefix}' referenced in column '{table_prefix}.{column_name}'.",
                    error_code="ERR_UNKNOWN_TABLE_ALIAS",
                    line=line,
                    column=column,
                    context=self._get_context(line),
                )

            col_schema = tbl_schema.get_column(column_name)
            if not col_schema:
                available = tbl_schema.column_names()
                closest = find_closest_identifier(column_name, available)
                suggestion = f"Did you mean '{closest[0]}'?" if closest else None
                raise SemanticError(
                    message=f"Column '{column_name}' does not exist in table '{tbl_schema.name}'.",
                    error_code="ERR_COLUMN_NOT_FOUND",
                    line=line,
                    column=column,
                    context=self._get_context(line),
                    available_columns=available,
                    suggestion=suggestion,
                )
            return tbl_schema, col_schema

        # Case 2: Unqualified column reference (e.g. name or id)
        matching_tables: List[Tuple[TableSchema, ColumnSchema]] = []
        for tbl in self.active_base_tables:
            c = tbl.get_column(column_name)
            if c:
                matching_tables.append((tbl, c))

        if len(matching_tables) == 0:
            available = self.get_all_available_columns()
            closest = find_closest_identifier(column_name, available)
            suggestion = f"Did you mean '{closest[0]}'?" if closest else None

            # Context info for single table scope vs multi-table
            if len(self.active_base_tables) == 1:
                table_hint = f" in table '{self.active_base_tables[0].name}'"
            else:
                table_hint = ""

            raise SemanticError(
                message=f"Column '{column_name}' does not exist{table_hint}.",
                error_code="ERR_COLUMN_NOT_FOUND",
                line=line,
                column=column,
                context=self._get_context(line),
                available_columns=available,
                suggestion=suggestion,
            )

        if len(matching_tables) > 1:
            matching_names = [f"'{t.name}.{column_name}'" for t, _ in matching_tables]
            raise SemanticError(
                message=f"Column '{column_name}' is ambiguous; present in multiple tables: {', '.join(matching_names)}. Qualify with a table prefix.",
                error_code="ERR_AMBIGUOUS_COLUMN",
                line=line,
                column=column,
                context=self._get_context(line),
                available_columns=self.get_all_available_columns(),
            )

        return matching_tables[0]
