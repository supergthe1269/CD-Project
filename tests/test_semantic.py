"""Unit tests for the Semantic Analyzer and Catalog checks."""

import unittest
from lexer.lexer import Lexer
from parser.parser import Parser
from semantic.catalog import create_default_catalog
from semantic.checker import SemanticChecker
from semantic.errors import SemanticError


class TestSemanticChecker(unittest.TestCase):

    def setUp(self):
        self.catalog = create_default_catalog()

    def _validate(self, sql: str, auto_correct: bool = False):
        tokens = Lexer(sql).tokenize()
        ast = Parser(tokens, sql).parse()
        checker = SemanticChecker(self.catalog, sql, auto_correct=auto_correct)
        notices = checker.validate(ast)
        return ast, notices

    def test_table_not_found(self):
        with self.assertRaises(SemanticError) as ctx:
            self._validate("SELECT * FROM non_existent_table")
        self.assertEqual(ctx.exception.error_code, "ERR_TABLE_NOT_FOUND")

    def test_duplicate_alias(self):
        with self.assertRaises(SemanticError) as ctx:
            self._validate("SELECT * FROM customers c JOIN orders c ON customers.id = orders.customer_id")
        self.assertEqual(ctx.exception.error_code, "ERR_DUPLICATE_ALIAS")

    def test_column_ambiguity_in_join(self):
        # 'id' exists in both customers and orders
        with self.assertRaises(SemanticError) as ctx:
            self._validate("SELECT id FROM customers c JOIN orders o ON c.id = o.customer_id")
        self.assertEqual(ctx.exception.error_code, "ERR_AMBIGUOUS_COLUMN")

    def test_qualified_column_resolution(self):
        ast, _ = self._validate("SELECT c.id, o.status FROM customers c JOIN orders o ON c.id = o.customer_id")
        self.assertIsNotNone(ast)

    def test_type_mismatch_date_vs_int(self):
        with self.assertRaises(SemanticError) as ctx:
            self._validate("SELECT name FROM customers WHERE signup_date = 42")
        self.assertEqual(ctx.exception.error_code, "ERR_TYPE_MISMATCH")

    def test_valid_numeric_comparison_promotions(self):
        # quantity (INT) compared with float literal 5.0
        ast, _ = self._validate("SELECT * FROM order_items WHERE quantity > 5.0")
        self.assertIsNotNone(ast)

    def test_invalid_foreign_key_join(self):
        with self.assertRaises(SemanticError) as ctx:
            self._validate("SELECT * FROM customers c JOIN orders o ON c.name = o.status")
        self.assertEqual(ctx.exception.error_code, "ERR_INVALID_JOIN_PREDICATE")

    def test_group_by_missing_column(self):
        # city is not aggregated and not in GROUP BY
        with self.assertRaises(SemanticError) as ctx:
            self._validate("SELECT city, name, COUNT(*) FROM customers GROUP BY city")
        self.assertEqual(ctx.exception.error_code, "ERR_AGGREGATION_SCOPE_MISMATCH")

    def test_fuzzy_auto_correction(self):
        # cust_id -> customer_id in orders
        sql = "SELECT c.name, o.status FROM customers c JOIN orders o ON c.id = o.cust_id"
        ast, notices = self._validate(sql, auto_correct=True)
        self.assertTrue(any("Auto-corrected column 'cust_id' -> 'customer_id'" in n for n in notices))


if __name__ == "__main__":
    unittest.main()
