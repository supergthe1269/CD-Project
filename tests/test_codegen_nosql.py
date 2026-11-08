"""Unit Tests for Target Code Generator (SQL AST to MongoDB MQL Transpiler).

Course: BCSE307P - Compiler Design Lab
Authors:
  - Gaurav Gopichand Nanhe (24BCB0020)
  - V Surya (24BAI0351)
"""

import unittest
from lexer.lexer import Lexer
from parser.parser import Parser
from codegen.nosql_transpiler import NoSQLTranspiler, MQLResult


class TestNoSQLTranspiler(unittest.TestCase):

    def _compile(self, sql: str) -> MQLResult:
        tokens = Lexer(sql).tokenize()
        ast = Parser(tokens, sql).parse()
        return NoSQLTranspiler().transpile(ast)

    def test_transpile_simple_wildcard(self):
        sql = "SELECT * FROM customers;"
        res = self._compile(sql)
        self.assertEqual(res.operation, "find")
        self.assertEqual(res.collection, "customers")
        self.assertIn("db.customers.find({})", res.mql_string)

    def test_transpile_projection_and_where(self):
        sql = "SELECT name, city FROM customers WHERE city = 'Delhi';"
        res = self._compile(sql)
        self.assertEqual(res.operation, "find")
        self.assertEqual(res.collection, "customers")
        self.assertEqual(res.filter_doc, {"city": "Delhi"})
        self.assertEqual(res.projection_doc, {"name": 1, "city": 1, "_id": 0})
        self.assertIn('"city": "Delhi"', res.mql_string)
        self.assertIn('"name": 1', res.mql_string)

    def test_transpile_comparison_operators(self):
        # > operator
        sql1 = "SELECT name FROM products WHERE price > 50;"
        res1 = self._compile(sql1)
        self.assertEqual(res1.filter_doc, {"price": {"$gt": 50}})

        # <= operator
        sql2 = "SELECT name FROM products WHERE price <= 100;"
        res2 = self._compile(sql2)
        self.assertEqual(res2.filter_doc, {"price": {"$lte": 100}})

        # != operator
        sql3 = "SELECT name FROM customers WHERE city != 'Delhi';"
        res3 = self._compile(sql3)
        self.assertEqual(res3.filter_doc, {"city": {"$ne": "Delhi"}})

    def test_transpile_compound_and_or(self):
        # Multiple AND merged
        sql_and = "SELECT name FROM customers WHERE city = 'Delhi' AND signup_date > '2024-01-01';"
        res_and = self._compile(sql_and)
        self.assertEqual(res_and.filter_doc, {"city": "Delhi", "signup_date": {"$gt": "2024-01-01"}})

        # OR condition
        sql_or = "SELECT name FROM customers WHERE city = 'Delhi' OR city = 'Mumbai';"
        res_or = self._compile(sql_or)
        self.assertIn("$or", res_or.filter_doc)
        self.assertEqual(len(res_or.filter_doc["$or"]), 2)

    def test_transpile_order_and_limit(self):
        sql = "SELECT name, price FROM products ORDER BY price DESC LIMIT 5;"
        res = self._compile(sql)
        self.assertEqual(res.sort_doc, {"price": -1})
        self.assertEqual(res.limit_val, 5)
        self.assertIn('.sort({"price": -1})', res.mql_string)
        self.assertIn('.limit(5)', res.mql_string)

    def test_transpile_aggregation_group_by(self):
        sql = "SELECT city, COUNT(*) AS customer_count FROM customers GROUP BY city;"
        res = self._compile(sql)
        self.assertEqual(res.operation, "aggregate")
        self.assertIsNotNone(res.pipeline)

        # Check $group stage
        group_stage = next(s["$group"] for s in res.pipeline if "$group" in s)
        self.assertEqual(group_stage["_id"], "$city")
        self.assertEqual(group_stage["customer_count"], {"$sum": 1})

        # Check $project stage
        proj_stage = next(s["$project"] for s in res.pipeline if "$project" in s)
        self.assertEqual(proj_stage["city"], "$_id")
        self.assertEqual(proj_stage["customer_count"], 1)

    def test_transpile_having_clause(self):
        sql = "SELECT city, COUNT(*) AS total FROM customers GROUP BY city HAVING COUNT(*) > 5;"
        res = self._compile(sql)
        self.assertEqual(res.operation, "aggregate")

        # Check post-group $match stage for HAVING
        match_stages = [s["$match"] for s in res.pipeline if "$match" in s]
        self.assertTrue(len(match_stages) >= 1)
        having_match = match_stages[-1]
        self.assertEqual(having_match, {"total": {"$gt": 5}})

    def test_transpile_join_to_lookup(self):
        sql = "SELECT c.name, o.status FROM customers c JOIN orders o ON c.id = o.customer_id;"
        res = self._compile(sql)
        self.assertEqual(res.operation, "aggregate")

        # Check $lookup stage
        lookup_stage = next(s["$lookup"] for s in res.pipeline if "$lookup" in s)
        self.assertEqual(lookup_stage["from"], "orders")
        self.assertEqual(lookup_stage["localField"], "id")
        self.assertEqual(lookup_stage["foreignField"], "customer_id")
        self.assertEqual(lookup_stage["as"], "o")

        # Check $unwind
        unwind_stage = next(s["$unwind"] for s in res.pipeline if "$unwind" in s)
        self.assertEqual(unwind_stage, "$o")

    def test_pymongo_code_generation(self):
        sql = "SELECT name FROM customers WHERE city = 'Delhi' LIMIT 10;"
        res = self._compile(sql)
        pymongo_str = res.to_pymongo()
        self.assertIn("client.db.customers.find", pymongo_str)
        self.assertIn(".limit(10)", pymongo_str)


if __name__ == "__main__":
    unittest.main()
