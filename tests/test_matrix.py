"""Validation Matrix Test Suite: The 7 Canonical Scenarios from Report Section 11.

Evaluates the compiler pipeline across all seven distinct evaluation categories:
1. Simple Projection
2. Boolean Precedence
3. Join Resolution
4. Group By Validation
5. Syntax Error Catch
6. Semantic Type Mismatch
7. Hallucination Detection
"""

import unittest
from lexer.lexer import Lexer
from parser.parser import Parser
from parser.ast_nodes import BinaryConditionNode, ComparisonNode, SelectStmtNode
from parser.errors import ParserSyntaxError
from semantic.catalog import create_default_catalog
from semantic.checker import SemanticChecker
from semantic.errors import SemanticError
from formatter.pretty_printer import SQLFormatter


class TestValidationMatrix(unittest.TestCase):

    def setUp(self):
        self.catalog = create_default_catalog()

    def test_case_1_simple_projection(self):
        """Case 1: Simple Projection - Wildcard resolution, single-table parsing."""
        query = "SELECT * FROM customers;"
        tokens = Lexer(query).tokenize()
        self.assertTrue(len(tokens) > 0)

        ast = Parser(tokens, query).parse()
        self.assertIsInstance(ast, SelectStmtNode)

        checker = SemanticChecker(self.catalog, query)
        notices = checker.validate(ast)
        self.assertEqual(len(notices), 0)

        formatted = SQLFormatter().format(ast)
        self.assertEqual(formatted, "SELECT\n  *\nFROM customers;")

    def test_case_2_boolean_precedence(self):
        """Case 2: Boolean Precedence - Parsing of nested AND / OR expressions."""
        query = "SELECT name FROM customers WHERE city = 'Delhi' AND signup_date > '2024-01-01'"
        tokens = Lexer(query).tokenize()
        ast = Parser(tokens, query).parse()

        # Verify binary condition tree structure
        self.assertIsInstance(ast.where, BinaryConditionNode)
        self.assertEqual(ast.where.op, "AND")
        self.assertIsInstance(ast.where.left, ComparisonNode)
        self.assertEqual(ast.where.left.op, "=")
        self.assertIsInstance(ast.where.right, ComparisonNode)
        self.assertEqual(ast.where.right.op, ">")

        checker = SemanticChecker(self.catalog, query)
        checker.validate(ast)

    def test_case_3_join_resolution(self):
        """Case 3: Join Resolution - Implicit aliases, foreign key relationship validation."""
        query = "SELECT c.name, o.status FROM customers c JOIN orders o ON c.id = o.customer_id"
        tokens = Lexer(query).tokenize()
        ast = Parser(tokens, query).parse()

        checker = SemanticChecker(self.catalog, query)
        checker.validate(ast)

        formatted = SQLFormatter().format(ast)
        self.assertIn("JOIN orders o ON c.id = o.customer_id", formatted)

    def test_case_4_group_by_validation(self):
        """Case 4: Group By Validation - Aggregate and non-aggregate column tracking."""
        query = "SELECT city, COUNT(*) FROM customers GROUP BY city HAVING COUNT(*) > 5"
        tokens = Lexer(query).tokenize()
        ast = Parser(tokens, query).parse()

        checker = SemanticChecker(self.catalog, query)
        checker.validate(ast)

        self.assertEqual(len(ast.group_by), 1)
        self.assertEqual(ast.group_by[0].column_name, "city")

    def test_case_5_syntax_error_catch(self):
        """Case 5: Syntax Error Catch - Missing FROM keyword."""
        query = "SELECT name customers WHERE id = 1"
        tokens = Lexer(query).tokenize()

        # Lexer succeeds, parser halts at token 'customers' (Line 1, Col 13)
        with self.assertRaises(ParserSyntaxError) as ctx:
            Parser(tokens, query).parse()

        err = ctx.exception
        self.assertEqual(err.error_code, "ERR_MISSING_FROM")
        self.assertEqual(err.token.value, "customers")
        self.assertEqual(err.line, 1)
        self.assertEqual(err.column, 13)

    def test_case_6_semantic_type_mismatch(self):
        """Case 6: Semantic Type Mismatch - Type verification across relational operators."""
        query = "SELECT name FROM customers WHERE signup_date = 42"
        tokens = Lexer(query).tokenize()
        ast = Parser(tokens, query).parse()

        # Parser succeeds, semantic analyzer flags DATE vs INT
        with self.assertRaises(SemanticError) as ctx:
            SemanticChecker(self.catalog, query).validate(ast)

        err = ctx.exception
        self.assertEqual(err.error_code, "ERR_TYPE_MISMATCH")
        self.assertIn("DATE", err.message)
        self.assertIn("INT", err.message)

    def test_case_7_hallucination_detection(self):
        """Case 7: Hallucination Detection - Plausible LLM hallucination catching."""
        query = "SELECT full_name, order_count FROM customers"
        tokens = Lexer(query).tokenize()
        ast = Parser(tokens, query).parse()

        # Parser succeeds, validator rejects nonexistent columns
        with self.assertRaises(SemanticError) as ctx:
            SemanticChecker(self.catalog, query).validate(ast)

        err = ctx.exception
        self.assertEqual(err.error_code, "ERR_COLUMN_NOT_FOUND")
        self.assertIn("full_name", err.message)
        self.assertEqual(err.line, 1)
        self.assertEqual(err.column, 8)


if __name__ == "__main__":
    unittest.main()
