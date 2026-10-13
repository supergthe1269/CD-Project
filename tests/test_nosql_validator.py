"""Unit Tests for Direct NoSQL (MongoDB MQL) Lexer, Parser, Semantic Checker, and Formatter.

Course: BCSE307P - Compiler Design Lab
Authors:
  - Gaurav Gopichand Nanhe (24BCB0020)
  - V Surya (24BAI0351)
"""

import unittest
from semantic.catalog import create_default_catalog
from nosql.lexer import NoSQLLexer
from nosql.parser import NoSQLParser
from nosql.checker import NoSQLSemanticChecker
from nosql.formatter import NoSQLFormatter
from nosql.errors import NoSQLSemanticError, NoSQLParserSyntaxError


class TestNoSQLValidator(unittest.TestCase):

    def setUp(self):
        self.catalog = create_default_catalog()

    def _parse_and_validate(self, query: str):
        tokens = NoSQLLexer(query).tokenize()
        ast = NoSQLParser(tokens, query).parse()
        notices = NoSQLSemanticChecker(self.catalog).validate(ast)
        return ast, notices

    def test_valid_find_simple(self):
        q = 'db.customers.find({ "city": "Delhi" });'
        ast, notices = self._parse_and_validate(q)
        self.assertEqual(ast.collection, "customers")
        self.assertEqual(ast.method, "find")
        self.assertEqual(ast.filter_doc, {"city": "Delhi"})

    def test_valid_find_with_projection_sort_limit(self):
        q = 'db.customers.find({ "city": "Delhi" }, { "name": 1, "city": 1 }).sort({ "name": 1 }).limit(10);'
        ast, notices = self._parse_and_validate(q)
        self.assertEqual(ast.filter_doc, {"city": "Delhi"})
        self.assertEqual(ast.projection_doc, {"name": 1, "city": 1})
        self.assertEqual(ast.sort_doc, {"name": 1})
        self.assertEqual(ast.limit_val, 10)

        # Check formatter
        formatted = NoSQLFormatter().format(ast)
        self.assertIn("db.customers.find(", formatted)
        self.assertIn('.sort({"name": 1})', formatted)
        self.assertIn(".limit(10);", formatted)

    def test_valid_find_with_operators(self):
        q = 'db.customers.find({ "signup_date": { "$gt": "2024-01-01" } });'
        ast, _ = self._parse_and_validate(q)
        self.assertEqual(ast.filter_doc, {"signup_date": {"$gt": "2024-01-01"}})

    def test_valid_aggregate_pipeline(self):
        q = 'db.customers.aggregate([ { "$match": { "city": "Delhi" } }, { "$group": { "_id": "$city", "total": { "$sum": 1 } } } ]);'
        ast, _ = self._parse_and_validate(q)
        self.assertEqual(ast.method, "aggregate")
        self.assertEqual(len(ast.pipeline), 2)
        self.assertIn("$match", ast.pipeline[0])
        self.assertIn("$group", ast.pipeline[1])

    def test_error_collection_not_found_with_fuzzy_recovery(self):
        q = 'db.cusotmers.find({ "city": "Delhi" });'
        with self.assertRaises(NoSQLSemanticError) as ctx:
            self._parse_and_validate(q)
        err = ctx.exception
        self.assertEqual(err.error_code, "ERR_NOSQL_COLLECTION_NOT_FOUND")
        self.assertEqual(err.suggestion, "customers")

    def test_error_field_not_found_with_fuzzy_recovery(self):
        q = 'db.customers.find({ "nam": "Alice" });'
        with self.assertRaises(NoSQLSemanticError) as ctx:
            self._parse_and_validate(q)
        err = ctx.exception
        self.assertEqual(err.error_code, "ERR_NOSQL_FIELD_NOT_FOUND")
        self.assertEqual(err.suggestion, "name")

    def test_error_field_not_found_hallucination(self):
        q = 'db.customers.find({ "full_name": "Alice" });'
        with self.assertRaises(NoSQLSemanticError) as ctx:
            self._parse_and_validate(q)
        err = ctx.exception
        self.assertEqual(err.error_code, "ERR_NOSQL_FIELD_NOT_FOUND")
        self.assertIsNone(err.suggestion)

    def test_error_projection_field_not_found(self):
        q = 'db.customers.find({}, { "cit": 1 });'
        with self.assertRaises(NoSQLSemanticError) as ctx:
            self._parse_and_validate(q)
        err = ctx.exception
        self.assertEqual(err.error_code, "ERR_NOSQL_FIELD_NOT_FOUND")
        self.assertEqual(err.suggestion, "city")

    def test_error_operator_typo_with_fuzzy_recovery(self):
        q = 'db.customers.find({ "signup_date": { "$gtt": "2024-01-01" } });'
        with self.assertRaises(NoSQLSemanticError) as ctx:
            self._parse_and_validate(q)
        err = ctx.exception
        self.assertEqual(err.error_code, "ERR_NOSQL_INVALID_OPERATOR")
        self.assertIn(err.suggestion, ["$gt", "$gte"])

    def test_error_pipeline_stage_typo(self):
        q = 'db.customers.aggregate([ { "$matchh": { "city": "Delhi" } } ]);'
        with self.assertRaises(NoSQLSemanticError) as ctx:
            self._parse_and_validate(q)
        err = ctx.exception
        self.assertEqual(err.error_code, "ERR_NOSQL_INVALID_OPERATOR")
        self.assertEqual(err.suggestion, "$match")

    def test_error_type_mismatch(self):
        q = 'db.customers.find({ "id": "not_an_int" });'
        with self.assertRaises(NoSQLSemanticError) as ctx:
            self._parse_and_validate(q)
        err = ctx.exception
        self.assertEqual(err.error_code, "ERR_NOSQL_TYPE_MISMATCH")

    def test_error_syntax_unsupported_method(self):
        q = 'db.customers.insert({ "name": "Bob" });'
        with self.assertRaises(NoSQLParserSyntaxError) as ctx:
            tokens = NoSQLLexer(q).tokenize()
            NoSQLParser(tokens, q).parse()
        err = ctx.exception
        self.assertEqual(err.error_code, "ERR_NOSQL_SYNTAX")


if __name__ == "__main__":
    unittest.main()
