"""Target Code Generator & Synthesis Phase: SQL AST to MongoDB MQL Transpiler.

Course: BCSE307P - Compiler Design Lab
Authors:
  - Gaurav Gopichand Nanhe (24BCB0020)
  - V Surya (24BAI0351)

Translates validated SQL Abstract Syntax Tree (AST) into executable MongoDB
Query Language (MQL) syntax, supporting:
  - Simple projections and wildcard projections
  - WHERE conditions mapped to MongoDB filters ($eq, $ne, $gt, $gte, $lt, $lte, $and, $or)
  - ORDER BY mapped to .sort() or $sort
  - LIMIT mapped to .limit() or $limit
  - Aggregations (GROUP BY, COUNT, SUM, AVG, MIN, MAX, HAVING) mapped to aggregate pipelines
  - Multi-table JOINs mapped to $lookup / $unwind aggregation stages
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
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


@dataclass
class MQLResult:
    """Represents the synthesized MongoDB Query Language (MQL) compilation target."""
    collection: str
    operation: str  # "find" or "aggregate"
    mql_string: str
    filter_doc: Optional[Dict[str, Any]] = None
    projection_doc: Optional[Dict[str, Any]] = None
    sort_doc: Optional[Dict[str, Any]] = None
    limit_val: Optional[int] = None
    pipeline: Optional[List[Dict[str, Any]]] = None

    def __str__(self) -> str:
        return self.mql_string

    def to_pymongo(self) -> str:
        """Returns ready-to-run PyMongo Python snippet."""
        if self.operation == "find":
            filt_str = json.dumps(self.filter_doc or {}, indent=2)
            proj_str = f", {json.dumps(self.projection_doc, indent=2)}" if self.projection_doc else ""
            call = f"client.db.{self.collection}.find({filt_str}{proj_str})"
            if self.sort_doc:
                sort_items = list(self.sort_doc.items())
                call += f".sort({sort_items})"
            if self.limit_val is not None:
                call += f".limit({self.limit_val})"
            return call
        else:
            pipe_str = json.dumps(self.pipeline or [], indent=2)
            return f"client.db.{self.collection}.aggregate({pipe_str})"


class NoSQLTranspiler:
    """Compiler backend that synthesizes MongoDB MQL from a validated SQL AST."""

    def __init__(self, indent_size: int = 2):
        self.indent_size = indent_size

    def transpile(self, ast: SelectStmtNode) -> MQLResult:
        """
        Main entry point for target code generation.
        Decides between find() and aggregate() based on query complexity.
        """
        has_joins = bool(ast.joins)
        has_group_by = bool(ast.group_by)
        has_having = bool(ast.having)
        has_aggregates = any(isinstance(p.expr, AggExprNode) for p in ast.projections)

        if has_joins or has_group_by or has_having or has_aggregates:
            return self._transpile_aggregate(ast)
        else:
            return self._transpile_find(ast)

    # -------------------------------------------------------------------------
    # find() Synthesis
    # -------------------------------------------------------------------------

    def _transpile_find(self, ast: SelectStmtNode) -> MQLResult:
        collection = ast.from_table.name

        # 1. Filter Doc from WHERE
        filter_doc: Dict[str, Any] = {}
        if ast.where:
            filter_doc = self._transpile_condition(ast.where)

        # 2. Projection Doc
        is_star = len(ast.projections) == 1 and isinstance(ast.projections[0].expr, StarNode)
        projection_doc: Optional[Dict[str, Any]] = None
        if not is_star:
            projection_doc = {}
            for item in ast.projections:
                if isinstance(item.expr, ColumnNode):
                    projection_doc[item.expr.column_name] = 1
            projection_doc["_id"] = 0

        # 3. Sort Doc from ORDER BY
        sort_doc: Optional[Dict[str, Any]] = None
        if ast.order_by:
            sort_doc = {}
            for item in ast.order_by:
                col_name = item.column_expr.column_name
                sort_doc[col_name] = 1 if item.direction == "ASC" else -1

        # 4. Limit
        limit_val = ast.limit

        # Format MQL String
        mql_str = self._format_find_mql(collection, filter_doc, projection_doc, sort_doc, limit_val)

        return MQLResult(
            collection=collection,
            operation="find",
            mql_string=mql_str,
            filter_doc=filter_doc,
            projection_doc=projection_doc,
            sort_doc=sort_doc,
            limit_val=limit_val,
        )

    def _format_find_mql(
        self,
        collection: str,
        filter_doc: Dict[str, Any],
        projection_doc: Optional[Dict[str, Any]],
        sort_doc: Optional[Dict[str, Any]],
        limit_val: Optional[int],
    ) -> str:
        parts = [f"db.{collection}.find("]

        filt_json = json.dumps(filter_doc, indent=self.indent_size)
        if projection_doc:
            proj_json = json.dumps(projection_doc, indent=self.indent_size)
            # Indent multi-line JSON arguments nicely
            indented_filt = self._indent_block(filt_json, self.indent_size)
            indented_proj = self._indent_block(proj_json, self.indent_size)
            parts.append(f"\n{indented_filt},\n{indented_proj}\n)")
        else:
            if filter_doc:
                indented_filt = self._indent_block(filt_json, self.indent_size)
                parts.append(f"\n{indented_filt}\n)")
            else:
                parts.append("{})")

        mql = "".join(parts)

        if sort_doc:
            sort_json = json.dumps(sort_doc)
            mql += f".sort({sort_json})"

        if limit_val is not None:
            mql += f".limit({limit_val})"

        return mql

    # -------------------------------------------------------------------------
    # aggregate() Synthesis
    # -------------------------------------------------------------------------

    def _transpile_aggregate(self, ast: SelectStmtNode) -> MQLResult:
        collection = ast.from_table.name
        pipeline: List[Dict[str, Any]] = []

        # Stage 1: $lookup and $unwind for JOINs
        for join in ast.joins:
            local_col, foreign_col = self._extract_join_fields(join, ast.from_table)
            as_name = join.table.effective_name()
            lookup_stage = {
                "$lookup": {
                    "from": join.table.name,
                    "localField": local_col,
                    "foreignField": foreign_col,
                    "as": as_name,
                }
            }
            pipeline.append(lookup_stage)

            if join.join_type == "LEFT":
                pipeline.append({
                    "$unwind": {
                        "path": f"${as_name}",
                        "preserveNullAndEmptyArrays": True,
                    }
                })
            else:
                pipeline.append({"$unwind": f"${as_name}"})

        # Stage 2: $match for WHERE
        if ast.where:
            where_filter = self._transpile_condition(ast.where, table_aliases=self._get_table_alias_map(ast))
            pipeline.append({"$match": where_filter})

        # Stage 3: $group for GROUP BY / Aggregates
        has_group_by = bool(ast.group_by)
        has_aggregates = any(isinstance(p.expr, AggExprNode) for p in ast.projections)

        if has_group_by or has_aggregates:
            group_stage = self._build_group_stage(ast)
            pipeline.append(group_stage)

            # Stage 4: $match for HAVING
            if ast.having:
                having_filter = self._transpile_having_condition(ast.having, ast.projections)
                pipeline.append({"$match": having_filter})

        # Stage 5: $project
        project_stage = self._build_project_stage(ast)
        if project_stage:
            pipeline.append({"$project": project_stage})

        # Stage 6: $sort for ORDER BY
        if ast.order_by:
            sort_doc = {}
            for item in ast.order_by:
                col_name = item.column_expr.column_name
                sort_doc[col_name] = 1 if item.direction == "ASC" else -1
            pipeline.append({"$sort": sort_doc})

        # Stage 7: $limit
        if ast.limit is not None:
            pipeline.append({"$limit": ast.limit})

        pipe_json = json.dumps(pipeline, indent=self.indent_size)
        indented_pipe = self._indent_block(pipe_json, self.indent_size)
        mql_str = f"db.{collection}.aggregate(\n{indented_pipe}\n)"

        return MQLResult(
            collection=collection,
            operation="aggregate",
            mql_string=mql_str,
            pipeline=pipeline,
            limit_val=ast.limit,
        )

    def _build_group_stage(self, ast: SelectStmtNode) -> Dict[str, Any]:
        # Build _id
        if ast.group_by:
            if len(ast.group_by) == 1:
                group_id: Any = f"${ast.group_by[0].column_name}"
            else:
                group_id = {col.column_name: f"${col.column_name}" for col in ast.group_by}
        else:
            group_id = None

        group_doc: Dict[str, Any] = {"_id": group_id}

        # Build Accumulators
        for item in ast.projections:
            if isinstance(item.expr, AggExprNode):
                field_name = item.alias or self._default_agg_alias(item.expr)
                group_doc[field_name] = self._transpile_agg_expr(item.expr)

        return {"$group": group_doc}

    def _build_project_stage(self, ast: SelectStmtNode) -> Optional[Dict[str, Any]]:
        is_star = len(ast.projections) == 1 and isinstance(ast.projections[0].expr, StarNode)
        if is_star and not ast.joins and not ast.group_by:
            return None

        project_doc: Dict[str, Any] = {"_id": 0}
        alias_map = self._get_table_alias_map(ast)

        for item in ast.projections:
            if isinstance(item.expr, StarNode):
                continue
            elif isinstance(item.expr, AggExprNode):
                field_name = item.alias or self._default_agg_alias(item.expr)
                project_doc[field_name] = 1
            elif isinstance(item.expr, ColumnNode):
                out_name = item.alias or item.expr.column_name
                # If grouped, column may come from _id
                if ast.group_by and any(g.column_name == item.expr.column_name for g in ast.group_by):
                    if len(ast.group_by) == 1:
                        project_doc[out_name] = "$_id"
                    else:
                        project_doc[out_name] = f"$_id.{item.expr.column_name}"
                elif item.expr.table_prefix and self._is_joined_table(item.expr.table_prefix, ast):
                    project_doc[out_name] = f"${item.expr.table_prefix}.{item.expr.column_name}"
                else:
                    project_doc[out_name] = f"${item.expr.column_name}"

        return project_doc

    def _default_agg_alias(self, agg: AggExprNode) -> str:
        func = agg.func.lower()
        if isinstance(agg.argument, StarNode):
            return f"{func}_all"
        return f"{func}_{agg.argument.column_name}"

    def _transpile_agg_expr(self, agg: AggExprNode) -> Dict[str, Any]:
        func = agg.func.upper()
        if func == "COUNT":
            return {"$sum": 1}

        arg_col = agg.argument.column_name if isinstance(agg.argument, ColumnNode) else "*"
        field_ref = f"${arg_col}"

        if func == "SUM":
            return {"$sum": field_ref}
        elif func == "AVG":
            return {"$avg": field_ref}
        elif func == "MIN":
            return {"$min": field_ref}
        elif func == "MAX":
            return {"$max": field_ref}
        return {"$sum": 1}

    # -------------------------------------------------------------------------
    # Condition Translation (WHERE / HAVING)
    # -------------------------------------------------------------------------

    def _transpile_condition(
        self,
        node: ConditionNode,
        table_aliases: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        if isinstance(node, ComparisonNode):
            return self._transpile_comparison(node, table_aliases)
        elif isinstance(node, BinaryConditionNode):
            op = node.op.upper()
            if op == "AND":
                # Flatten chained ANDs
                leaves = self._collect_binary_operands(node, "AND")
                sub_filters = [self._transpile_condition(c, table_aliases) for c in leaves]
                # If all sub_filters are single-key simple mappings with disjoint keys and no $ operators:
                merged: Dict[str, Any] = {}
                can_merge = True
                for f in sub_filters:
                    if len(f) == 1:
                        key = next(iter(f.keys()))
                        if key not in merged and not key.startswith("$"):
                            merged[key] = f[key]
                            continue
                    can_merge = False
                    break
                if can_merge and merged:
                    return merged
                return {"$and": sub_filters}
            elif op == "OR":
                leaves = self._collect_binary_operands(node, "OR")
                sub_filters = [self._transpile_condition(c, table_aliases) for c in leaves]
                return {"$or": sub_filters}

        return {}

    def _collect_binary_operands(self, node: ConditionNode, target_op: str) -> List[ConditionNode]:
        result = []
        if isinstance(node, BinaryConditionNode) and node.op.upper() == target_op:
            result.extend(self._collect_binary_operands(node.left, target_op))
            result.extend(self._collect_binary_operands(node.right, target_op))
        else:
            result.append(node)
        return result

    def _transpile_comparison(
        self,
        node: ComparisonNode,
        table_aliases: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        left = node.left
        right = node.right

        # Normalize so ColumnNode is on the left
        if isinstance(right, ColumnNode) and not isinstance(left, ColumnNode):
            left, right = right, left

        if not isinstance(left, ColumnNode):
            return {}

        field_name = self._resolve_column_path(left, table_aliases)
        val = right.value if isinstance(right, LiteralNode) else str(right)

        op = node.op
        if op == "=":
            return {field_name: val}
        elif op == "!=":
            return {field_name: {"$ne": val}}
        elif op == ">":
            return {field_name: {"$gt": val}}
        elif op == ">=":
            return {field_name: {"$gte": val}}
        elif op == "<":
            return {field_name: {"$lt": val}}
        elif op == "<=":
            return {field_name: {"$lte": val}}

        return {field_name: val}

    def _transpile_having_condition(
        self,
        node: ConditionNode,
        projections: List[SelectItemNode],
    ) -> Dict[str, Any]:
        """Translates a HAVING condition, replacing aggregate calls with their alias."""
        if isinstance(node, ComparisonNode):
            target_name = None
            if isinstance(node.left, AggExprNode):
                target_name = self._find_alias_for_agg(node.left, projections)
            elif isinstance(node.left, ColumnNode):
                target_name = node.left.column_name

            if not target_name:
                target_name = "agg_result"

            val = node.right.value if isinstance(node.right, LiteralNode) else 0

            op_map = {
                "=": val,
                "!=": {"$ne": val},
                ">": {"$gt": val},
                ">=": {"$gte": val},
                "<": {"$lt": val},
                "<=": {"$lte": val},
            }
            return {target_name: op_map.get(node.op, val)}

        elif isinstance(node, BinaryConditionNode):
            left_filt = self._transpile_having_condition(node.left, projections)
            right_filt = self._transpile_having_condition(node.right, projections)
            key = "$and" if node.op.upper() == "AND" else "$or"
            return {key: [left_filt, right_filt]}

        return {}

    def _find_alias_for_agg(self, agg: AggExprNode, projections: List[SelectItemNode]) -> str:
        for p in projections:
            if isinstance(p.expr, AggExprNode):
                if p.expr.func.upper() == agg.func.upper():
                    return p.alias or self._default_agg_alias(p.expr)
        return self._default_agg_alias(agg)

    # -------------------------------------------------------------------------
    # Join Helpers
    # -------------------------------------------------------------------------

    def _extract_join_fields(self, join: JoinNode, base_table: TableRefNode) -> tuple[str, str]:
        cond = join.on_condition
        if isinstance(cond, ComparisonNode):
            left = cond.left
            right = cond.right
            if isinstance(left, ColumnNode) and isinstance(right, ColumnNode):
                # Determine which is local and which is foreign
                base_eff = base_table.effective_name()
                join_eff = join.table.effective_name()

                if left.table_prefix in (join.table.name, join_eff):
                    return right.column_name, left.column_name
                else:
                    return left.column_name, right.column_name

        # Fallback to standard convention
        return "id", f"{base_table.name[:-1]}_id"

    def _is_joined_table(self, prefix: str, ast: SelectStmtNode) -> bool:
        prefix_lower = prefix.lower()
        for j in ast.joins:
            if j.table.name.lower() == prefix_lower or (j.table.alias and j.table.alias.lower() == prefix_lower):
                return True
        return False

    def _get_table_alias_map(self, ast: SelectStmtNode) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        if ast.from_table.alias:
            mapping[ast.from_table.alias] = ast.from_table.name
        mapping[ast.from_table.name] = ast.from_table.name

        for j in ast.joins:
            if j.table.alias:
                mapping[j.table.alias] = j.table.name
            mapping[j.table.name] = j.table.name
        return mapping

    def _resolve_column_path(self, col: ColumnNode, aliases: Optional[Dict[str, str]]) -> str:
        if not col.table_prefix:
            return col.column_name
        # If alias refers to a joined table, in MongoDB the joined document is nested under the alias
        return f"{col.table_prefix}.{col.column_name}"

    def _indent_block(self, text: str, spaces: int) -> str:
        prefix = " " * spaces
        return "\n".join(prefix + line if line.strip() else line for line in text.split("\n"))
