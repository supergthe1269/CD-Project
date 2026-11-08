"""Semantic Checker enforcing relational schema consistency, scoping, and typing.

Implements the 5 formal semantic verification checks defined in Section 8 of the report:
1. Table Resolution
2. Column Resolution & Ambiguity Checking
3. Join Foreign-Key Compatibility
4. Type Compatibility in Relational Comparisons
5. GROUP BY / Aggregation Consistency
"""

from typing import List, Optional, Tuple, Dict, Any, Union
from parser.ast_nodes import (
    SelectStmtNode,
    SelectItemNode,
    TableRefNode,
    JoinNode,
    AggExprNode,
    BinaryConditionNode,
    ComparisonNode,
    ColumnNode,
    LiteralNode,
    OperandNode,
    ConditionNode,
    OrderItemNode,
    StarNode,
)
from .catalog import DatabaseCatalog, TableSchema, ColumnSchema
from .symbol_table import SymbolTable
from .errors import SemanticError
from .fuzzy import find_closest_identifier


class SemanticChecker:
    def __init__(
        self,
        catalog: DatabaseCatalog,
        source: str = "",
        auto_correct: bool = False,
    ):
        self.catalog = catalog
        self.source = source
        self.auto_correct = auto_correct
        self.symbol_table = SymbolTable(catalog, source)
        self.corrections: List[str] = []

    def _get_context(self, line: int) -> str:
        lines = self.source.splitlines()
        if 1 <= line <= len(lines):
            return lines[line - 1]
        return ""

    def validate(self, ast: SelectStmtNode) -> List[str]:
        """
        Runs all 5 semantic checks across the AST.
        Returns a list of notices / auto-corrections if any were applied.
        Raises SemanticError on validation failure.
        """
        self.corrections = []
        self.symbol_table = SymbolTable(self.catalog, self.source)

        # -------------------------------------------------------------
        # Check 1: Table Resolution
        # -------------------------------------------------------------
        # 1a. FROM table
        self._validate_and_register_table(ast.from_table)

        # 1b. JOIN tables
        for join in ast.joins:
            self._validate_and_register_table(join.table)

        # -------------------------------------------------------------
        # Check 2: Column Resolution & Ambiguity (traverses AST expressions)
        # -------------------------------------------------------------
        # 2a. Projections
        for item in ast.projections:
            if isinstance(item.expr, ColumnNode):
                self._resolve_column_node(item.expr)
            elif isinstance(item.expr, AggExprNode):
                if isinstance(item.expr.argument, ColumnNode):
                    self._resolve_column_node(item.expr.argument)

        # 2b. WHERE condition
        if ast.where:
            self._validate_condition(ast.where)

        # 2c. JOIN ON conditions & Check 3: Join Foreign-Key Compatibility
        for join in ast.joins:
            self._validate_join(join, ast.from_table)

        # 2d. GROUP BY columns
        if ast.group_by:
            for col in ast.group_by:
                self._resolve_column_node(col)

        # 2e. HAVING condition
        if ast.having:
            self._validate_condition(ast.having)

        # 2f. ORDER BY columns
        if ast.order_by:
            for order_item in ast.order_by:
                self._resolve_column_node(order_item.column_expr)

        # -------------------------------------------------------------
        # Check 4: Type Compatibility is enforced recursively within _validate_condition()
        # -------------------------------------------------------------

        # -------------------------------------------------------------
        # Check 5: GROUP BY / Aggregation Consistency
        # -------------------------------------------------------------
        self._check_aggregation_consistency(ast)

        return self.corrections

    # -----------------------------------------------------------------
    # Check 1 Helpers
    # -----------------------------------------------------------------
    def _validate_and_register_table(self, table_ref: TableRefNode) -> None:
        try:
            self.symbol_table.register_table(
                table_name=table_ref.name,
                alias=table_ref.alias,
                line=table_ref.line,
                column=table_ref.column,
            )
        except SemanticError as err:
            if self.auto_correct:
                closest = find_closest_identifier(table_ref.name, self.catalog.table_names())
                if closest:
                    old_name = table_ref.name
                    table_ref.name = closest[0]
                    self.corrections.append(f"Auto-corrected table '{old_name}' -> '{closest[0]}'")
                    self.symbol_table.register_table(
                        table_name=table_ref.name,
                        alias=table_ref.alias,
                        line=table_ref.line,
                        column=table_ref.column,
                    )
                    return
            raise err

    # -----------------------------------------------------------------
    # Check 2 Helpers
    # -----------------------------------------------------------------
    def _resolve_column_node(self, col_node: ColumnNode) -> Tuple[TableSchema, ColumnSchema]:
        try:
            return self.symbol_table.resolve_column(
                column_name=col_node.column_name,
                table_prefix=col_node.table_prefix,
                line=col_node.line,
                column=col_node.column,
            )
        except SemanticError as err:
            if self.auto_correct and err.error_code == "ERR_COLUMN_NOT_FOUND":
                available = err.available_columns or self.symbol_table.get_all_available_columns()
                closest = find_closest_identifier(col_node.column_name, available)
                if closest:
                    old_col = col_node.column_name
                    col_node.column_name = closest[0]
                    self.corrections.append(f"Auto-corrected column '{old_col}' -> '{closest[0]}'")
                    return self.symbol_table.resolve_column(
                        column_name=col_node.column_name,
                        table_prefix=col_node.table_prefix,
                        line=col_node.line,
                        column=col_node.column,
                    )
            raise err

    # -----------------------------------------------------------------
    # Check 3 Helpers: Join Relationship Verification
    # -----------------------------------------------------------------
    def _validate_join(self, join: JoinNode, base_table_ref: TableRefNode) -> None:
        # Validate the ON condition syntax & columns
        self._validate_condition(join.on_condition)

        # Inspect if ON condition binds declared foreign keys between joined tables
        join_tbl_name = join.table.name
        base_tbl_name = base_table_ref.name

        # If on_condition is a simple ComparisonNode(=)
        if isinstance(join.on_condition, ComparisonNode) and join.on_condition.op == "=":
            left = join.on_condition.left
            right = join.on_condition.right
            if isinstance(left, ColumnNode) and isinstance(right, ColumnNode):
                tbl_left, col_left = self._resolve_column_node(left)
                tbl_right, col_right = self._resolve_column_node(right)

                # Ensure condition references columns from the two joined tables
                valid_fks = self.catalog.get_foreign_keys_between(tbl_left.name, tbl_right.name)
                if valid_fks:
                    condition_pair = (col_left.name.lower(), col_right.name.lower())
                    reverse_pair = (col_right.name.lower(), col_left.name.lower())
                    valid_pairs = [(a.lower(), b.lower()) for a, b in valid_fks]

                    if condition_pair not in valid_pairs and reverse_pair not in valid_pairs:
                        expected_pairs = [f"{a} = {b}" for a, b in valid_fks]
                        raise SemanticError(
                            message=(
                                f"Join predicate '{left.qualified_name()} = {right.qualified_name()}' "
                                f"violates declared foreign key relationships between '{tbl_left.name}' and '{tbl_right.name}'. "
                                f"Expected FK condition: {', '.join(expected_pairs)}."
                            ),
                            error_code="ERR_INVALID_JOIN_PREDICATE",
                            line=join.on_condition.line,
                            column=join.on_condition.column,
                            context=self._get_context(join.on_condition.line),
                        )

    # -----------------------------------------------------------------
    # Check 4 Helpers: Condition validation & Type Compatibility
    # -----------------------------------------------------------------
    def _validate_condition(self, condition: ConditionNode) -> None:
        if isinstance(condition, BinaryConditionNode):
            self._validate_condition(condition.left)
            self._validate_condition(condition.right)
        elif isinstance(condition, ComparisonNode):
            type_left = self._get_operand_type(condition.left)
            type_right = self._get_operand_type(condition.right)

            if not self._are_types_compatible(type_left, type_right):
                raise SemanticError(
                    message=(
                        f"Type mismatch in comparison operator '{condition.op}': "
                        f"Left operand is {type_left}, but right operand is {type_right}."
                    ),
                    error_code="ERR_TYPE_MISMATCH",
                    line=condition.line,
                    column=condition.column,
                    context=self._get_context(condition.line),
                )

    def _get_operand_type(self, operand: OperandNode) -> str:
        if isinstance(operand, LiteralNode):
            return operand.data_type.upper()
        elif isinstance(operand, ColumnNode):
            _, col_schema = self._resolve_column_node(operand)
            return col_schema.data_type.upper()
        elif isinstance(operand, AggExprNode):
            if operand.func == "COUNT":
                return "INT"
            elif operand.func == "AVG":
                return "FLOAT"
            elif isinstance(operand.argument, ColumnNode):
                _, col_schema = self._resolve_column_node(operand.argument)
                return col_schema.data_type.upper()
            return "FLOAT"
        return "UNKNOWN"

    def _are_types_compatible(self, t1: str, t2: str) -> bool:
        t1 = t1.upper()
        t2 = t2.upper()

        if t1 == t2:
            return True

        # Numeric promotion: INT and FLOAT are mutually compatible
        if t1 in ("INT", "FLOAT") and t2 in ("INT", "FLOAT"):
            return True

        # In ANSI SQL, DATE cannot be directly compared to numeric INT/FLOAT
        if t1 == "DATE" and t2 in ("INT", "FLOAT"):
            return False
        if t2 == "DATE" and t1 in ("INT", "FLOAT"):
            return False

        # DATE can be compared to DATE literals or standard date string formats
        if t1 == "DATE" and t2 in ("VARCHAR", "DATE"):
            return True
        if t2 == "DATE" and t1 in ("VARCHAR", "DATE"):
            return True

        return False

    # -----------------------------------------------------------------
    # Check 5 Helpers: GROUP BY / Aggregation Consistency
    # -----------------------------------------------------------------
    def _check_aggregation_consistency(self, ast: SelectStmtNode) -> None:
        has_aggregates = any(isinstance(p.expr, AggExprNode) for p in ast.projections)
        non_agg_cols: List[ColumnNode] = []

        for p in ast.projections:
            if isinstance(p.expr, ColumnNode):
                non_agg_cols.append(p.expr)
            elif isinstance(p.expr, StarNode):
                if has_aggregates or ast.group_by:
                    raise SemanticError(
                        message="Wildcard '*' cannot be combined with aggregate functions or GROUP BY.",
                        error_code="ERR_AGGREGATION_SCOPE_MISMATCH",
                        line=p.line,
                        column=p.column,
                        context=self._get_context(p.line),
                    )

        # Case 1: GROUP BY is present
        if ast.group_by is not None:
            # Build set of group by column names (normalized)
            group_by_cols = {col.column_name.lower() for col in ast.group_by}

            # Check that every non-aggregated projection appears in GROUP BY
            for col in non_agg_cols:
                if col.column_name.lower() not in group_by_cols:
                    raise SemanticError(
                        message=(
                            f"Non-aggregated column '{col.qualified_name()}' must appear in the GROUP BY clause."
                        ),
                        error_code="ERR_AGGREGATION_SCOPE_MISMATCH",
                        line=col.line,
                        column=col.column,
                        context=self._get_context(col.line),
                    )

        # Case 2: GROUP BY is NOT present, but aggregate functions are used
        elif has_aggregates and non_agg_cols:
            bad_cols = [c.qualified_name() for c in non_agg_cols]
            raise SemanticError(
                message=(
                    f"SELECT list contains aggregate functions together with non-aggregated column(s) "
                    f"[{', '.join(bad_cols)}], but no GROUP BY clause was specified."
                ),
                error_code="ERR_AGGREGATION_SCOPE_MISMATCH",
                line=non_agg_cols[0].line,
                column=non_agg_cols[0].column,
                context=self._get_context(non_agg_cols[0].line),
            )
