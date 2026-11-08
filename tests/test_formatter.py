"""Unit tests for the SQL AST Formatter."""

import unittest
from lexer.lexer import Lexer
from parser.parser import Parser
from formatter.pretty_printer import SQLFormatter


class TestFormatter(unittest.TestCase):

    def _format(self, sql: str) -> str:
        tokens = Lexer(sql).tokenize()
        ast = Parser(tokens, sql).parse()
        return SQLFormatter().format(ast)

    def test_canonical_formatting(self):
        sql = "select c.name, count(*) from customers c join orders o on c.id=o.customer_id where c.city='Delhi' group by c.name having count(*)>2 order by c.name asc limit 10;"
        formatted = self._format(sql)

        expected_lines = [
            "SELECT",
            "  c.name,",
            "  COUNT(*)",
            "FROM customers c",
            "INNER JOIN orders o ON c.id = o.customer_id",
            "WHERE c.city = 'Delhi'",
            "GROUP BY c.name",
            "HAVING COUNT(*) > 2",
            "ORDER BY c.name ASC",
            "LIMIT 10;",
        ]
        self.assertEqual(formatted.splitlines(), expected_lines)

    def test_simple_projection_formatting(self):
        sql = "select * from customers;"
        formatted = self._format(sql)
        expected = "SELECT\n  *\nFROM customers;"
        self.assertEqual(formatted, expected)


if __name__ == "__main__":
    unittest.main()
