"""Abstract Syntax Tree (AST) node definitions for SQL queries.

Strongly-typed dataclasses representing the syntactic structure
produced by the recursive-descent parser.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Union, Any, Dict


@dataclass
class ASTNode:
    """Base class for all Abstract Syntax Tree nodes."""
    line: int = 1
    column: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert node and children to dictionary for JSON serialization."""
        result: Dict[str, Any] = {"node_type": self.__class__.__name__}
        for k, v in self.__dict__.items():
            if k in ("line", "column"):
                continue
            if isinstance(v, ASTNode):
                result[k] = v.to_dict()
            elif isinstance(v, list):
                result[k] = [item.to_dict() if isinstance(item, ASTNode) else item for item in v]
            else:
                result[k] = v
        return result

    def format_tree(self, prefix: str = "", is_tail: bool = True) -> str:
        """Render a readable ASCII tree representation of the AST."""
        connector = "└── " if is_tail else "├── "
        lines = [f"{prefix}{connector}{self._label()}"]
        new_prefix = prefix + ("    " if is_tail else "│   ")
        children = self._children()
        for idx, (label, child) in enumerate(children):
            tail = (idx == len(children) - 1)
            if isinstance(child, ASTNode):
                lines.append(f"{new_prefix}{'└── ' if tail else '├── '}{label}:")
                lines.append(child.format_tree(new_prefix + ("    " if tail else "│   "), is_tail=True))
            elif isinstance(child, list):
                lines.append(f"{new_prefix}{'└── ' if tail else '├── '}{label}: [{len(child)} items]")
                sub_prefix = new_prefix + ("    " if tail else "│   ")
                for sub_idx, sub_item in enumerate(child):
                    sub_tail = (sub_idx == len(child) - 1)
                    if isinstance(sub_item, ASTNode):
                        lines.append(sub_item.format_tree(sub_prefix, is_tail=sub_tail))
                    else:
                        lines.append(f"{sub_prefix}{'└── ' if sub_tail else '├── '}{sub_item}")
            else:
                lines.append(f"{new_prefix}{'└── ' if tail else '├── '}{label}: {child}")
        return "\n".join(lines)

    def _label(self) -> str:
        return self.__class__.__name__

    def _children(self) -> List[tuple[str, Any]]:
        return []


# --- Operands and Expressions ---

@dataclass
class OperandNode(ASTNode):
    """Base class for operands in comparisons (ColumnNode or LiteralNode)."""
    pass


@dataclass
class StarNode(ASTNode):
    """Represents a wildcard '*' in projection or COUNT(*)."""
    def _label(self) -> str:
        return "StarNode(*)"


@dataclass
class ColumnNode(OperandNode):
    """Represents a column identifier, optionally qualified by a table prefix."""
    table_prefix: Optional[str] = None
    column_name: str = ""

    def qualified_name(self) -> str:
        if self.table_prefix:
            return f"{self.table_prefix}.{self.column_name}"
        return self.column_name

    def _label(self) -> str:
        return f"ColumnNode({self.qualified_name()})"


@dataclass
class LiteralNode(OperandNode):
    """Represents a literal constant (String or Number)."""
    value: Union[str, int, float] = ""
    data_type: str = "VARCHAR"  # 'VARCHAR', 'INT', 'FLOAT', 'DATE'

    def _label(self) -> str:
        return f"LiteralNode({self.value!r}, {self.data_type})"


@dataclass
class AggExprNode(OperandNode):
    """Represents an aggregate function call: COUNT, SUM, AVG, MIN, MAX."""
    func: str = ""  # e.g., 'COUNT', 'SUM'
    argument: Union[ColumnNode, StarNode] = field(default_factory=StarNode)

    def _label(self) -> str:
        arg_str = "*" if isinstance(self.argument, StarNode) else self.argument.qualified_name()
        return f"AggExprNode({self.func}({arg_str}))"

    def _children(self) -> List[tuple[str, Any]]:
        return [("argument", self.argument)]


@dataclass
class SelectItemNode(ASTNode):
    """An individual item in the SELECT projection list."""
    expr: Union[ColumnNode, AggExprNode, StarNode] = field(default_factory=StarNode)
    alias: Optional[str] = None

    def _label(self) -> str:
        alias_str = f" AS {self.alias}" if self.alias else ""
        return f"SelectItemNode{alias_str}"

    def _children(self) -> List[tuple[str, Any]]:
        return [("expr", self.expr)]


@dataclass
class TableRefNode(ASTNode):
    """Represents a table reference in FROM or JOIN with an optional alias."""
    name: str = ""
    alias: Optional[str] = None

    def effective_name(self) -> str:
        return self.alias if self.alias else self.name

    def _label(self) -> str:
        alias_str = f" AS {self.alias}" if self.alias else ""
        return f"TableRefNode({self.name}{alias_str})"


# --- Conditions ---

@dataclass
class ConditionNode(ASTNode):
    """Base class for WHERE and HAVING conditions."""
    pass


@dataclass
class ComparisonNode(ConditionNode):
    """Represents a binary comparison between two operands (e.g. city = 'Delhi')."""
    op: str = "="
    left: OperandNode = field(default_factory=OperandNode)
    right: OperandNode = field(default_factory=OperandNode)

    def _label(self) -> str:
        return f"ComparisonNode({self.op})"

    def _children(self) -> List[tuple[str, Any]]:
        return [("left", self.left), ("right", self.right)]


@dataclass
class BinaryConditionNode(ConditionNode):
    """Represents a boolean condition combination (AND, OR)."""
    op: str = "AND"
    left: ConditionNode = field(default_factory=ConditionNode)
    right: ConditionNode = field(default_factory=ConditionNode)

    def _label(self) -> str:
        return f"BinaryConditionNode({self.op})"

    def _children(self) -> List[tuple[str, Any]]:
        return [("left", self.left), ("right", self.right)]


# --- Joins, Orders, and Statement ---

@dataclass
class JoinNode(ASTNode):
    """Represents an INNER JOIN or LEFT JOIN with an ON condition."""
    join_type: str = "INNER"  # 'INNER' or 'LEFT'
    table: TableRefNode = field(default_factory=TableRefNode)
    on_condition: ConditionNode = field(default_factory=ConditionNode)

    def _label(self) -> str:
        return f"JoinNode({self.join_type} JOIN)"

    def _children(self) -> List[tuple[str, Any]]:
        return [("table", self.table), ("on_condition", self.on_condition)]


@dataclass
class OrderItemNode(ASTNode):
    """Represents an item in the ORDER BY list."""
    column_expr: ColumnNode = field(default_factory=ColumnNode)
    direction: str = "ASC"  # 'ASC' or 'DESC'

    def _label(self) -> str:
        return f"OrderItemNode({self.column_expr.qualified_name()} {self.direction})"

    def _children(self) -> List[tuple[str, Any]]:
        return [("column", self.column_expr)]


@dataclass
class SelectStmtNode(ASTNode):
    """Root statement node for a SELECT query."""
    projections: List[SelectItemNode] = field(default_factory=list)
    from_table: TableRefNode = field(default_factory=TableRefNode)
    joins: List[JoinNode] = field(default_factory=list)
    where: Optional[ConditionNode] = None
    group_by: Optional[List[ColumnNode]] = None
    having: Optional[ConditionNode] = None
    order_by: Optional[List[OrderItemNode]] = None
    limit: Optional[int] = None

    def _label(self) -> str:
        return "SelectStmtNode"

    def _children(self) -> List[tuple[str, Any]]:
        items: List[tuple[str, Any]] = [
            ("projections", self.projections),
            ("from_table", self.from_table),
        ]
        if self.joins:
            items.append(("joins", self.joins))
        if self.where:
            items.append(("where", self.where))
        if self.group_by:
            items.append(("group_by", self.group_by))
        if self.having:
            items.append(("having", self.having))
        if self.order_by:
            items.append(("order_by", self.order_by))
        if self.limit is not None:
            items.append(("limit", self.limit))
        return items
