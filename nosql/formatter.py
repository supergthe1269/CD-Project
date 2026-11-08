"""Canonical Pretty-Printer / Formatter for MongoDB MQL queries.

Course: BCSE307P - Compiler Design Lab
"""

import json
from .ast_nodes import NoSQLQueryNode


class NoSQLFormatter:
    """Pretty-prints a validated NoSQLQueryNode AST into standard MongoDB shell syntax."""

    def __init__(self, indent_size: int = 2):
        self.indent_size = indent_size

    def format(self, node: NoSQLQueryNode) -> str:
        if node.method == "find":
            return self._format_find(node)
        else:
            return self._format_aggregate(node)

    def _format_find(self, node: NoSQLQueryNode) -> str:
        parts = [f"db.{node.collection}.find("]

        filt = node.filter_doc or {}
        proj = node.projection_doc

        filt_str = json.dumps(filt, indent=self.indent_size)
        if proj:
            proj_str = json.dumps(proj, indent=self.indent_size)
            ind_filt = self._indent_block(filt_str, self.indent_size)
            ind_proj = self._indent_block(proj_str, self.indent_size)
            parts.append(f"\n{ind_filt},\n{ind_proj}\n)")
        elif filt:
            ind_filt = self._indent_block(filt_str, self.indent_size)
            parts.append(f"\n{ind_filt}\n)")
        else:
            parts.append("{})")

        out = "".join(parts)

        if node.sort_doc:
            out += f".sort({json.dumps(node.sort_doc)})"

        if node.limit_val is not None:
            out += f".limit({node.limit_val})"

        return out + ";"

    def _format_aggregate(self, node: NoSQLQueryNode) -> str:
        pipeline = node.pipeline or []
        pipe_str = json.dumps(pipeline, indent=self.indent_size)
        ind_pipe = self._indent_block(pipe_str, self.indent_size)
        return f"db.{node.collection}.aggregate(\n{ind_pipe}\n);"

    def _indent_block(self, text: str, spaces: int) -> str:
        prefix = " " * spaces
        return "\n".join(prefix + line if line.strip() else line for line in text.split("\n"))
