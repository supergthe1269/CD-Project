"""AST Pretty-Printer / Formatter (Synthesis Phase).

Reconstructs canonical, beautifully indented SQL from the validated AST.
Normalizes keywords to uppercase, lays out clauses on dedicated lines,
and indents projections and conditions by 2 spaces.
"""

from typing import List, Union
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


class SQLFormatter:
    """Formats an AST into canonical SQL text."""

    def __init__(self, indent_size: int = 2):
        self.indent = " " * indent_size

    def format(self, ast: SelectStmtNode) -> str:
        lines: List[str] = []

        # 1. SELECT clause
        lines.append("SELECT")
        for i, item in enumerate(ast.projections):
            item_str = self._format_select_item(item)
            is_last = (i == len(ast.projections) - 1)
            comma = "" if is_last else ","
            lines.append(f"{self.indent}{item_str}{comma}")

        # 2. FROM clause
        from_str = self._format_table_ref(ast.from_table)
        lines.append(f"FROM {from_str}")

        # 3. JOIN clauses
        for join in ast.joins:
            tbl_str = self._format_table_ref(join.table)
            cond_str = self._format_condition(join.on_condition)
            lines.append(f"{join.join_type} JOIN {tbl_str} ON {cond_str}")

        # 4. WHERE clause
        if ast.where:
            cond_str = self._format_condition(ast.where)
            lines.append(f"WHERE {cond_str}")

        # 5. GROUP BY clause
        if ast.group_by:
            cols_str = ", ".join(self._format_column(c) for c in ast.group_by)
            lines.append(f"GROUP BY {cols_str}")

        # 6. HAVING clause
        if ast.having:
            having_str = self._format_condition(ast.having)
            lines.append(f"HAVING {having_str}")

        # 7. ORDER BY clause
        if ast.order_by:
            order_items_str = ", ".join(self._format_order_item(oi) for oi in ast.order_by)
            lines.append(f"ORDER BY {order_items_str}")

        # 8. LIMIT clause
        if ast.limit is not None:
            lines.append(f"LIMIT {ast.limit};")
        else:
            # Terminate last line with semicolon if not present
            lines[-1] += ";"

        return "\n".join(lines)

    def _format_select_item(self, item: SelectItemNode) -> str:
        if isinstance(item.expr, StarNode):
            expr_str = "*"
        elif isinstance(item.expr, AggExprNode):
            expr_str = self._format_agg_expr(item.expr)
        elif isinstance(item.expr, ColumnNode):
            expr_str = self._format_column(item.expr)
        else:
            expr_str = str(item.expr)

        if item.alias:
            return f"{expr_str} AS {item.alias}"
        return expr_str

    def _format_agg_expr(self, agg: AggExprNode) -> str:
        if isinstance(agg.argument, StarNode):
            arg_str = "*"
        elif isinstance(agg.argument, ColumnNode):
            arg_str = self._format_column(agg.argument)
        else:
            arg_str = str(agg.argument)
        return f"{agg.func}({arg_str})"

    def _format_table_ref(self, tbl: TableRefNode) -> str:
        if tbl.alias:
            return f"{tbl.name} {tbl.alias}"
        return tbl.name

    def _format_column(self, col: ColumnNode) -> str:
        return col.qualified_name()

    def _format_operand(self, op: OperandNode) -> str:
        if isinstance(op, ColumnNode):
            return self._format_column(op)
        elif isinstance(op, AggExprNode):
            return self._format_agg_expr(op)
        elif isinstance(op, LiteralNode):
            if op.data_type in ("VARCHAR", "DATE"):
                return f"'{op.value}'"
            return str(op.value)
        return str(op)

    def _format_condition(self, cond: ConditionNode) -> str:
        if isinstance(cond, ComparisonNode):
            left_str = self._format_operand(cond.left)
            right_str = self._format_operand(cond.right)
            return f"{left_str} {cond.op} {right_str}"
        elif isinstance(cond, BinaryConditionNode):
            left_str = self._format_condition(cond.left)
            right_str = self._format_condition(cond.right)

            # Mirror tree parenthesization for precedence clarity
            if isinstance(cond.left, BinaryConditionNode) and cond.left.op != cond.op:
                left_str = f"({left_str})"
            if isinstance(cond.right, BinaryConditionNode) and cond.right.op != cond.op:
                right_str = f"({right_str})"

            return f"{left_str} {cond.op} {right_str}"
        return ""

    def _format_order_item(self, item: OrderItemNode) -> str:
        return f"{self._format_column(item.column_expr)} {item.direction}"
