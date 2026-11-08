"""Unit tests for the hand-written Lexer."""

import unittest
from lexer.tokens import TokenType
from lexer.lexer import Lexer
from lexer.errors import LexicalError


class TestLexer(unittest.TestCase):

    def test_basic_tokenization(self):
        query = "SELECT id, name FROM customers;"
        tokens = Lexer(query).tokenize()

        expected_types = [
            TokenType.SELECT,
            TokenType.IDENTIFIER,
            TokenType.COMMA,
            TokenType.IDENTIFIER,
            TokenType.FROM,
            TokenType.IDENTIFIER,
            TokenType.SEMICOLON,
            TokenType.EOF,
        ]
        self.assertEqual([t.type for t in tokens], expected_types)
        self.assertEqual(tokens[0].value, "SELECT")
        self.assertEqual(tokens[1].value, "id")
        self.assertEqual(tokens[3].value, "name")
        self.assertEqual(tokens[5].value, "customers")

    def test_line_and_column_tracking(self):
        query = "SELECT\n  name\nFROM customers"
        tokens = Lexer(query).tokenize()

        self.assertEqual(tokens[0].line, 1)
        self.assertEqual(tokens[0].column, 1)

        self.assertEqual(tokens[1].line, 2)
        self.assertEqual(tokens[1].column, 3)

        self.assertEqual(tokens[2].line, 3)
        self.assertEqual(tokens[2].column, 1)

    def test_case_insensitivity(self):
        query = "select Name From Customers where Id = 10"
        tokens = Lexer(query).tokenize()
        self.assertEqual(tokens[0].type, TokenType.SELECT)
        self.assertEqual(tokens[2].type, TokenType.FROM)
        self.assertEqual(tokens[4].type, TokenType.WHERE)

    def test_operators(self):
        query = "= != < > <= >="
        tokens = Lexer(query).tokenize()
        expected = [
            TokenType.EQUALS,
            TokenType.NOT_EQUALS,
            TokenType.LESS_THAN,
            TokenType.GREATER_THAN,
            TokenType.LESS_EQUALS,
            TokenType.GREATER_EQUALS,
            TokenType.EOF,
        ]
        self.assertEqual([t.type for t in tokens], expected)

    def test_strings_and_numbers(self):
        query = "'Delhi' 42 3.14159"
        tokens = Lexer(query).tokenize()
        self.assertEqual(tokens[0].type, TokenType.STRING)
        self.assertEqual(tokens[0].value, "Delhi")
        self.assertEqual(tokens[1].type, TokenType.NUMBER)
        self.assertEqual(tokens[1].value, 42)
        self.assertEqual(tokens[2].type, TokenType.NUMBER)
        self.assertEqual(tokens[2].value, 3.14159)

    def test_single_line_comments(self):
        query = "SELECT -- this is a comment\nname FROM customers"
        tokens = Lexer(query).tokenize()
        types = [t.type for t in tokens]
        self.assertEqual(types, [TokenType.SELECT, TokenType.IDENTIFIER, TokenType.FROM, TokenType.IDENTIFIER, TokenType.EOF])

    def test_invalid_character_error(self):
        query = "SELECT # FROM customers"
        with self.assertRaises(LexicalError) as ctx:
            Lexer(query).tokenize()
        self.assertEqual(ctx.exception.error_code, "ERR_INVALID_CHARACTER")
        self.assertEqual(ctx.exception.line, 1)
        self.assertEqual(ctx.exception.column, 8)

    def test_unterminated_string_error(self):
        query = "SELECT 'Delhi FROM customers"
        with self.assertRaises(LexicalError) as ctx:
            Lexer(query).tokenize()
        self.assertEqual(ctx.exception.error_code, "ERR_UNTERMINATED_STRING")


if __name__ == "__main__":
    unittest.main()
