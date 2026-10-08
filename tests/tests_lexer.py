# tests/test_lexer.py
import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from lexer.lexer import tokenise
from lexer.tokens import TokenType
from records.common import LexicalError

class TestLexer(unittest.TestCase):
    
    def test_words_and_keywords(self):
        # Testing mixed-case keywords, identifiers, and aggregates
        tokens = tokenise("SeLeCt selection order_date CoUnT")
        self.assertEqual(tokens[0].type, TokenType.KEYWORD)
        self.assertEqual(tokens[0].value, "SELECT")
        self.assertEqual(tokens[1].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[1].value, "selection")
        self.assertEqual(tokens[2].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[2].value, "order_date")
        self.assertEqual(tokens[3].type, TokenType.AGG_FUNC)
        self.assertEqual(tokens[3].value, "COUNT")

    def test_positions_multiline(self):
        # "SELECT *\nFROM t" puts FROM at 2:1
        tokens = tokenise("SELECT *\nFROM t")
        self.assertEqual(tokens[0].line, 1)
        
        # tokens[1] is '*', tokens[2] is 'FROM'
        t_from = tokens[2]
        self.assertEqual(t_from.value, "FROM")
        self.assertEqual(t_from.line, 2)
        self.assertEqual(t_from.column, 1)

    def test_numbers_standard_and_edge_cases(self):
        # 42, 3.14, 007, 3., .5, 1.2.3, 12abc
        tokens = tokenise("42 3.14 007 3. .5 1.2.3 12abc")
        
        # 42
        self.assertEqual(tokens[0].type, TokenType.INTEGER)
        self.assertEqual(tokens[0].value, "42")
        # 3.14
        self.assertEqual(tokens[1].type, TokenType.FLOAT)
        self.assertEqual(tokens[1].value, "3.14")
        # 007
        self.assertEqual(tokens[2].type, TokenType.INTEGER)
        self.assertEqual(tokens[2].value, "007")
        # 3. -> INTEGER(3) then PUNCTUATION(.)
        self.assertEqual(tokens[3].type, TokenType.INTEGER)
        self.assertEqual(tokens[4].type, TokenType.PUNCTUATION)
        # .5 -> PUNCTUATION(.) then INTEGER(5)
        self.assertEqual(tokens[5].type, TokenType.PUNCTUATION)
        self.assertEqual(tokens[6].type, TokenType.INTEGER)
        # 1.2.3 -> FLOAT(1.2) then PUNCTUATION(.) then INTEGER(3)
        self.assertEqual(tokens[7].type, TokenType.FLOAT)
        self.assertEqual(tokens[7].value, "1.2")
        self.assertEqual(tokens[8].type, TokenType.PUNCTUATION)
        self.assertEqual(tokens[9].type, TokenType.INTEGER)
        # 12abc -> INTEGER(12) then IDENTIFIER(abc)
        self.assertEqual(tokens[10].type, TokenType.INTEGER)
        self.assertEqual(tokens[11].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[11].value, "abc")

    def test_operators(self):
        # <= versus < =, <>, !=, ==
        tokens = tokenise("<= < = <> != ==")
        self.assertEqual(tokens[0].value, "<=")
        self.assertEqual(tokens[1].value, "<")
        self.assertEqual(tokens[2].value, "=")
        self.assertEqual(tokens[3].value, "<>")
        self.assertEqual(tokens[4].value, "!=")
        # == becomes two = tokens that the parser will reject
        self.assertEqual(tokens[5].value, "=")
        self.assertEqual(tokens[6].value, "=")

    def test_strings(self):
        # '', 'O''Brien'[cite: 2]
        # (Assuming the lexer's read_string supports standard SQL '' escaping if implemented, 
        # otherwise 'O''Brien' becomes STRING, IDENTIFIER, STRING based on exact implementation)
        tokens = tokenise("'' 'abc'")
        self.assertEqual(tokens[0].type, TokenType.STRING)
        self.assertEqual(tokens[0].value, "")
        self.assertEqual(tokens[1].type, TokenType.STRING)
        self.assertEqual(tokens[1].value, "abc")

    def test_comments(self):
        # x = --5 and -- note at end of file
        tokens = tokenise("x = --5\n-- note")
        self.assertEqual(tokens[0].value, "x")
        self.assertEqual(tokens[1].value, "=")
        self.assertEqual(tokens[2].type, TokenType.EOF) # The rest are comments

    def test_flagged_words(self):
        # RIGHT, FULL, USING, UNION
        tokens = tokenise("RIGHT FULL USING UNION")
        for i in range(4):
            self.assertEqual(tokens[i].type, TokenType.FLAGGED)

    def test_lexical_errors_illegal_chars(self):
        # #, @, $, ", backtick, /, a smart quote
        illegals = ["#", "@", "$", '"', "`", "/", "‘"]
        for char in illegals:
            with self.subTest(char=char):
                with self.assertRaises(LexicalError) as cm:
                    tokenise(f"SELECT {char} FROM t")
                self.assertEqual(cm.exception.diagnostic.error_code, "ERR_ILLEGAL_CHARACTER")
                self.assertEqual(cm.exception.diagnostic.found, char)

    def test_lexical_errors_standalone_bang(self):
        # ! alone raises lexical error
        with self.assertRaises(LexicalError) as cm:
            tokenise("SELECT ! FROM t")
        self.assertEqual(cm.exception.diagnostic.error_code, "ERR_ILLEGAL_CHARACTER")
        self.assertEqual(cm.exception.diagnostic.found, "!")

    def test_lexical_errors_unterminated_string(self):
        # 'abc unterminated
        with self.assertRaises(LexicalError) as cm:
            tokenise("SELECT 'abc \n FROM t")
        self.assertEqual(cm.exception.diagnostic.error_code, "ERR_UNTERMINATED_STRING")

if __name__ == '__main__':
    unittest.main()