"""Unit tests for the Recursive-Descent Parser."""

import unittest
from lexer.lexer import Lexer
from parser.parser import Parser
from parser.ast_nodes import (
    SelectStmtNode,
    StarNode,
    ColumnNode,
    BinaryConditionNode,
    ComparisonNode,
    AggExprNode,
)
from parser.errors import ParserSyntaxError


class TestParser(unittest.TestCase):

    def _parse(self, sql: str) -> SelectStmtNode:
        tokens = Lexer(sql).tokenize()
        return Parser(tokens, sql).parse()

    def test_parse_simple_star(self):
        ast = self._parse("SELECT * FROM customers;")
        self.assertIsInstance(ast, SelectStmtNode)
        self.assertEqual(len(ast.projections), 1)
        self.assertIsInstance(ast.projections[0].expr, StarNode)
        self.assertEqual(ast.from_table.name, "customers")

    def test_parse_projections_with_aliases(self):
        ast = self._parse("SELECT id AS user_id, name customer_name FROM customers c")
        self.assertEqual(len(ast.projections), 2)
        self.assertEqual(ast.projections[0].alias, "user_id")
        self.assertEqual(ast.projections[1].alias, "customer_name")
        self.assertEqual(ast.from_table.name, "customers")
        self.assertEqual(ast.from_table.alias, "c")

    def test_boolean_precedence_and_over_or(self):
        # A OR B AND C -> A OR (B AND C)
        sql = "SELECT * FROM customers WHERE id = 1 OR city = 'Delhi' AND name = 'Alice'"
        ast = self._parse(sql)
        self.assertIsInstance(ast.where, BinaryConditionNode)
        self.assertEqual(ast.where.op, "OR")
        self.assertIsInstance(ast.where.right, BinaryConditionNode)
        self.assertEqual(ast.where.right.op, "AND")

    def test_parentheses_precedence(self):
        # (A OR B) AND C
        sql = "SELECT * FROM customers WHERE (id = 1 OR city = 'Delhi') AND name = 'Alice'"
        ast = self._parse(sql)
        self.assertIsInstance(ast.where, BinaryConditionNode)
        self.assertEqual(ast.where.op, "AND")
        self.assertIsInstance(ast.where.left, BinaryConditionNode)
        self.assertEqual(ast.where.left.op, "OR")

    def test_join_clauses(self):
        sql = "SELECT c.name, o.status FROM customers c LEFT JOIN orders o ON c.id = o.customer_id"
        ast = self._parse(sql)
        self.assertEqual(len(ast.joins), 1)
        self.assertEqual(ast.joins[0].join_type, "LEFT")
        self.assertEqual(ast.joins[0].table.name, "orders")
        self.assertEqual(ast.joins[0].table.alias, "o")

    def test_aggregates_and_rejection_of_sum_star(self):
        # COUNT(*) is valid
        ast = self._parse("SELECT COUNT(*) FROM customers")
        self.assertIsInstance(ast.projections[0].expr, AggExprNode)
        self.assertEqual(ast.projections[0].expr.func, "COUNT")

        # SUM(*) is rejected at parser stage
        with self.assertRaises(ParserSyntaxError) as ctx:
            self._parse("SELECT SUM(*) FROM products")
        self.assertEqual(ctx.exception.error_code, "ERR_ILLEGAL_AGGREGATE_WILDCARD")

    def test_missing_from_syntax_error(self):
        sql = "SELECT name customers WHERE id = 1"
        with self.assertRaises(ParserSyntaxError) as ctx:
            self._parse(sql)
        self.assertEqual(ctx.exception.error_code, "ERR_MISSING_FROM")
        self.assertEqual(ctx.exception.token.value, "customers")
        self.assertEqual(ctx.exception.line, 1)
        self.assertEqual(ctx.exception.column, 13)


if __name__ == "__main__":
    unittest.main()
