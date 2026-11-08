"""Abstract Syntax Tree (AST) node definitions for NoSQL (MongoDB MQL) queries.

Course: BCSE307P - Compiler Design Lab
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class NoSQLASTNode:
    line: int = 1
    column: int = 1


@dataclass
class NoSQLQueryNode(NoSQLASTNode):
    """Root AST node representing an executable MongoDB MQL operation."""
    collection: str = ""
    collection_line: int = 1
    collection_column: int = 1
    method: str = "find"  # "find" or "aggregate"
    filter_doc: Optional[Dict[str, Any]] = None
    projection_doc: Optional[Dict[str, Any]] = None
    sort_doc: Optional[Dict[str, Any]] = None
    limit_val: Optional[int] = None
    pipeline: Optional[List[Dict[str, Any]]] = None

    # Maps field names / operator keys to (line, column) in source query
    field_positions: Dict[str, Tuple[int, int]] = field(default_factory=dict)

    def format_tree(self) -> str:
        """Render a readable ASCII tree representation of the NoSQL AST."""
        lines = [f"NoSQLQueryNode: db.{self.collection}.{self.method}()"]
        if self.method == "find":
            lines.append(f"  ├── Filter: {self.filter_doc}")
            lines.append(f"  ├── Projection: {self.projection_doc}")
            if self.sort_doc:
                lines.append(f"  ├── Sort: {self.sort_doc}")
            if self.limit_val is not None:
                lines.append(f"  └── Limit: {self.limit_val}")
        else:
            lines.append(f"  └── Pipeline: [{len(self.pipeline or [])} stages]")
            for idx, stage in enumerate(self.pipeline or []):
                stage_name = next(iter(stage.keys())) if stage else "unknown"
                lines.append(f"      ├── Stage {idx + 1} ({stage_name}): {stage}")
        return "\n".join(lines)
