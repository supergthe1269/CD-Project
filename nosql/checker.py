"""Semantic Checker and Catalog Validator for MongoDB MQL queries.

Course: BCSE307P - Compiler Design Lab
Authors:
  - Gaurav Gopichand Nanhe (24BCB0020)
  - V Surya (24BAI0351)

Enforces:
  1. Collection existence against catalog (with fuzzy typo recovery)
  2. Operator validity ($gt, $match, etc. catching typos like $gtt)
  3. Field existence in filter, projection, sort, and aggregation stages
  4. Type compatibility in filter comparison values
  5. Multi-collection join validity in $lookup stages
"""

from typing import Any, Dict, List, Optional, Set
from semantic.catalog import DatabaseCatalog, TableSchema
from semantic.fuzzy import find_closest_identifier
from .ast_nodes import NoSQLQueryNode
from .errors import NoSQLSemanticError


VALID_QUERY_OPS: Set[str] = {
    "$eq", "$ne", "$gt", "$gte", "$lt", "$lte", "$in", "$nin",
    "$and", "$or", "$not", "$nor", "$exists", "$type", "$regex"
}

VALID_STAGE_OPS: Set[str] = {
    "$match", "$group", "$lookup", "$project", "$sort", "$limit",
    "$skip", "$unwind", "$count", "$addFields", "$replaceRoot"
}

VALID_ACCUMULATORS: Set[str] = {
    "$sum", "$avg", "$min", "$max", "$first", "$last", "$push", "$addToSet"
}

ALL_VALID_OPS: Set[str] = VALID_QUERY_OPS | VALID_STAGE_OPS | VALID_ACCUMULATORS


class NoSQLSemanticChecker:
    """Walks NoSQL AST and verifies constraints against the database catalog."""

    def __init__(self, catalog: DatabaseCatalog, auto_correct: bool = False):
        self.catalog = catalog
        self.auto_correct = auto_correct
        self.notices: List[str] = []

    def validate(self, node: NoSQLQueryNode) -> List[str]:
        self.notices.clear()

        # 1. Collection Existence
        table_meta = self._validate_collection(node)

        # 2. Method-specific validation
        if node.method == "find":
            if node.filter_doc:
                self._validate_filter(node.filter_doc, table_meta, node)
            if node.projection_doc:
                self._validate_projection(node.projection_doc, table_meta, node)
            if node.sort_doc:
                self._validate_sort(node.sort_doc, table_meta, node)
        elif node.method == "aggregate":
            if node.pipeline:
                self._validate_pipeline(node.pipeline, table_meta, node)

        return list(self.notices)

    # -------------------------------------------------------------------------
    # 1. Collection Validation
    # -------------------------------------------------------------------------

    def _validate_collection(self, node: NoSQLQueryNode) -> TableSchema:
        col_name = node.collection
        table_meta = self.catalog.get_table(col_name)

        if not table_meta:
            candidates = self.catalog.table_names()
            closest = find_closest_identifier(col_name, candidates, max_distance=3)
            suggestion = closest[0] if closest else None

            line, col = node.collection_line, node.collection_column
            raise NoSQLSemanticError(
                f"Collection '{col_name}' does not exist in database catalog.",
                line=line,
                column=col,
                error_code="ERR_NOSQL_COLLECTION_NOT_FOUND",
                available_columns=candidates,
                suggestion=suggestion,
            )

        return table_meta

    # -------------------------------------------------------------------------
    # 2. Operator & Filter Validation
    # -------------------------------------------------------------------------

    def _validate_filter(self, filter_doc: Dict[str, Any], table: TableSchema, node: NoSQLQueryNode) -> None:
        for key, val in filter_doc.items():
            line, col = node.field_positions.get(key, (node.line, node.column))

            # Case A: Operator at root (e.g., $and, $or, $nor)
            if key.startswith("$"):
                self._check_operator(key, VALID_QUERY_OPS, line, col)
                if isinstance(val, list):
                    for sub_doc in val:
                        if isinstance(sub_doc, dict):
                            self._validate_filter(sub_doc, table, node)
                continue

            # Case B: Field name
            col_meta = table.get_column(key)
            if not col_meta and key != "_id":
                candidates = table.column_names()
                closest = find_closest_identifier(key, candidates, max_distance=3)
                suggestion = closest[0] if closest else None
                raise NoSQLSemanticError(
                    f"Field '{key}' does not exist on collection '{table.name}'.",
                    line=line,
                    column=col,
                    error_code="ERR_NOSQL_FIELD_NOT_FOUND",
                    available_columns=candidates,
                    suggestion=suggestion,
                )

            # Validate operator or value inside field
            if isinstance(val, dict):
                for op_key, op_val in val.items():
                    op_line, op_col = node.field_positions.get(op_key, (line, col))
                    if op_key.startswith("$"):
                        self._check_operator(op_key, VALID_QUERY_OPS, op_line, op_col)
                    # Check type compatibility
                    if col_meta:
                        self._check_value_type(col_meta.data_type, op_val, key, op_line, op_col)
            elif col_meta:
                self._check_value_type(col_meta.data_type, val, key, line, col)

    def _check_operator(self, op: str, allowed: Set[str], line: int, col: int) -> None:
        if op not in allowed and op not in ALL_VALID_OPS:
            closest = find_closest_identifier(op, list(allowed | ALL_VALID_OPS), max_distance=3)
            suggestion = closest[0] if closest else None
            raise NoSQLSemanticError(
                f"Invalid or unknown MongoDB operator '{op}'.",
                line=line,
                column=col,
                error_code="ERR_NOSQL_INVALID_OPERATOR",
                suggestion=suggestion,
            )

    def _check_value_type(self, declared_type: str, val: Any, field_name: str, line: int, col: int) -> None:
        if val is None:
            return

        if declared_type in ("INT", "FLOAT"):
            if isinstance(val, bool):
                raise NoSQLSemanticError(
                    f"Type mismatch on field '{field_name}': expected numeric {declared_type}, found boolean.",
                    line=line,
                    column=col,
                    error_code="ERR_NOSQL_TYPE_MISMATCH",
                )
            if isinstance(val, str):
                try:
                    float(val)
                except ValueError:
                    raise NoSQLSemanticError(
                        f"Type mismatch on field '{field_name}': expected numeric {declared_type}, found non-numeric string '{val}'.",
                        line=line,
                        column=col,
                        error_code="ERR_NOSQL_TYPE_MISMATCH",
                    )
        elif declared_type == "DATE":
            if isinstance(val, (int, float, bool)):
                raise NoSQLSemanticError(
                    f"Type mismatch on field '{field_name}': expected DATE string, found {type(val).__name__}.",
                    line=line,
                    column=col,
                    error_code="ERR_NOSQL_TYPE_MISMATCH",
                )

    # -------------------------------------------------------------------------
    # 3. Projection & Sort Validation
    # -------------------------------------------------------------------------

    def _validate_projection(self, proj_doc: Dict[str, Any], table: TableSchema, node: NoSQLQueryNode) -> None:
        for key in proj_doc.keys():
            if key == "_id":
                continue
            line, col = node.field_positions.get(key, (node.line, node.column))
            if not table.get_column(key):
                candidates = table.column_names()
                closest = find_closest_identifier(key, candidates, max_distance=3)
                suggestion = closest[0] if closest else None
                raise NoSQLSemanticError(
                    f"Projection field '{key}' does not exist on collection '{table.name}'.",
                    line=line,
                    column=col,
                    error_code="ERR_NOSQL_FIELD_NOT_FOUND",
                    available_columns=candidates,
                    suggestion=suggestion,
                )

    def _validate_sort(self, sort_doc: Dict[str, Any], table: TableSchema, node: NoSQLQueryNode) -> None:
        for key in sort_doc.keys():
            line, col = node.field_positions.get(key, (node.line, node.column))
            if not table.get_column(key) and key != "_id":
                candidates = table.column_names()
                closest = find_closest_identifier(key, candidates, max_distance=3)
                suggestion = closest[0] if closest else None
                raise NoSQLSemanticError(
                    f"Sort field '{key}' does not exist on collection '{table.name}'.",
                    line=line,
                    column=col,
                    error_code="ERR_NOSQL_FIELD_NOT_FOUND",
                    available_columns=candidates,
                    suggestion=suggestion,
                )

    # -------------------------------------------------------------------------
    # 4. Aggregation Pipeline Validation
    # -------------------------------------------------------------------------

    def _validate_pipeline(self, pipeline: List[Dict[str, Any]], table: TableSchema, node: NoSQLQueryNode) -> None:
        for stage in pipeline:
            if not isinstance(stage, dict):
                continue
            for stage_name, stage_body in stage.items():
                line, col = node.field_positions.get(stage_name, (node.line, node.column))
                self._check_operator(stage_name, VALID_STAGE_OPS, line, col)

                if stage_name == "$match" and isinstance(stage_body, dict):
                    self._validate_filter(stage_body, table, node)

                elif stage_name == "$lookup" and isinstance(stage_body, dict):
                    from_col = stage_body.get("from")
                    if from_col and not self.catalog.has_table(str(from_col)):
                        closest = find_closest_identifier(str(from_col), self.catalog.table_names(), max_distance=3)
                        raise NoSQLSemanticError(
                            f"Target collection '{from_col}' in $lookup does not exist in catalog.",
                            line=line,
                            column=col,
                            error_code="ERR_NOSQL_COLLECTION_NOT_FOUND",
                            suggestion=closest[0] if closest else None,
                        )

                elif stage_name == "$group" and isinstance(stage_body, dict):
                    # Check accumulators inside $group
                    for acc_field, acc_expr in stage_body.items():
                        if isinstance(acc_expr, dict):
                            for acc_op in acc_expr.keys():
                                op_line, op_col = node.field_positions.get(acc_op, (line, col))
                                self._check_operator(acc_op, VALID_ACCUMULATORS, op_line, op_col)
