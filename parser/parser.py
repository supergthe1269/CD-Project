"""Recursive-Descent Parser for Analytical SQL Subset.

Implements an LL(1) predictive top-down parser directly from the EBNF grammar.
Every grammar production rule has a 1:1 corresponding parsing method.
"""

import re
from typing import List, Optional, Union
from lexer.tokens import Token, TokenType
from .ast_nodes import (
    ASTNode,
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
from .errors import ParserSyntaxError

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Parser:
    def __init__(self, tokens: List[Token], source: str = ""):
        self.tokens = tokens
        self.source = source
        self.pos = 0

    def _current_token(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # return EOF token

    def _peek_token(self, offset: int = 1) -> Token:
        target = self.pos + offset
        if target < len(self.tokens):
            return self.tokens[target]
        return self.tokens[-1]

    def _advance(self) -> Token:
        tok = self._current_token()
        if tok.type != TokenType.EOF:
            self.pos += 1
        return tok

    def _match(self, *expected_types: TokenType) -> bool:
        return self._current_token().type in expected_types

    def _expect(self, expected_type: TokenType, custom_message: Optional[str] = None) -> Token:
        tok = self._current_token()
        if tok.type != expected_type:
            msg = custom_message or f"Expected {expected_type.name}"
            err_code = "ERR_MISSING_FROM" if expected_type == TokenType.FROM else "ERR_UNEXPECTED_TOKEN"
            raise ParserSyntaxError(
                message=msg,
                token=tok,
                expected=expected_type.name,
                error_code=err_code,
                context=self._get_context(tok.line),
            )
        return self._advance()

    def _get_context(self, line_num: int) -> str:
        lines = self.source.splitlines()
        if 1 <= line_num <= len(lines):
            return lines[line_num - 1]
        return ""

    # -------------------------------------------------------------
    # Grammar Production Rules
    # -------------------------------------------------------------

    def parse(self) -> SelectStmtNode:
        """query ::= select_stmt [ ";" ] EOF"""
        stmt = self.parse_select_stmt()
        if self._match(TokenType.SEMICOLON):
            self._advance()
        if not self._match(TokenType.EOF):
            tok = self._current_token()
            raise ParserSyntaxError(
                message=f"Unexpected token '{tok.value}' after query end",
                token=tok,
                expected="EOF",
                error_code="ERR_SYNTAX_TRAILING",
                context=self._get_context(tok.line),
            )
        return stmt

    def parse_select_stmt(self) -> SelectStmtNode:
        """
        select_stmt ::= "SELECT" select_list
                        "FROM" table_ref { join_clause }*
                        [ "WHERE" condition ]
                        [ "GROUP" "BY" column_list ]
                        [ "HAVING" condition ]
                        [ "ORDER" "BY" order_list ]
                        [ "LIMIT" INTEGER ]
        """
        select_tok = self._expect(TokenType.SELECT, "Query must start with 'SELECT'")
        stmt = SelectStmtNode(line=select_tok.line, column=select_tok.column)

        # 1. Projections (select_list)
        stmt.projections = self.parse_select_list()

        # 2. FROM clause
        self._expect(TokenType.FROM, "Expected 'FROM' keyword after SELECT projection list")
        stmt.from_table = self.parse_table_ref()

        # 3. Optional JOIN clauses
        while self._match(TokenType.JOIN, TokenType.INNER, TokenType.LEFT):
            stmt.joins.append(self.parse_join_clause())

        # 4. Optional WHERE clause
        if self._match(TokenType.WHERE):
            self._advance()
            stmt.where = self.parse_condition()

        # 5. Optional GROUP BY clause
        if self._match(TokenType.GROUP):
            self._advance()
            self._expect(TokenType.BY, "Expected 'BY' after 'GROUP'")
            stmt.group_by = self.parse_column_list()

        # 6. Optional HAVING clause
        if self._match(TokenType.HAVING):
            self._advance()
            stmt.having = self.parse_condition()

        # 7. Optional ORDER BY clause
        if self._match(TokenType.ORDER):
            self._advance()
            self._expect(TokenType.BY, "Expected 'BY' after 'ORDER'")
            stmt.order_by = self.parse_order_list()

        # 8. Optional LIMIT clause
        if self._match(TokenType.LIMIT):
            self._advance()
            num_tok = self._expect(TokenType.NUMBER, "Expected integer value after 'LIMIT'")
            if not isinstance(num_tok.value, int):
                raise ParserSyntaxError(
                    message="LIMIT must be an integer",
                    token=num_tok,
                    expected="INTEGER",
                    error_code="ERR_INVALID_LIMIT",
                    context=self._get_context(num_tok.line),
                )
            stmt.limit = num_tok.value

        return stmt

    def parse_select_list(self) -> List[SelectItemNode]:
        """select_list ::= "*" | select_item { "," select_item }*"""
        items: List[SelectItemNode] = []

        if self._match(TokenType.STAR):
            star_tok = self._advance()
            items.append(SelectItemNode(
                expr=StarNode(line=star_tok.line, column=star_tok.column),
                line=star_tok.line,
                column=star_tok.column,
            ))
            return items

        items.append(self.parse_select_item())
        while self._match(TokenType.COMMA):
            self._advance()
            items.append(self.parse_select_item())

        return items

    def parse_select_item(self) -> SelectItemNode:
        """select_item ::= ( agg_expr | column ) [ alias_clause ]"""
        tok = self._current_token()
        item_line = tok.line
        item_col = tok.column

        if self._match(TokenType.COUNT, TokenType.SUM, TokenType.AVG, TokenType.MIN, TokenType.MAX):
            expr: Union[ColumnNode, AggExprNode, StarNode] = self.parse_agg_expr()
        elif self._match(TokenType.IDENTIFIER):
            expr = self.parse_column()
        else:
            raise ParserSyntaxError(
                message=f"Expected column or aggregate expression, found '{tok.value}'",
                token=tok,
                expected="column or aggregate function",
                error_code="ERR_INVALID_SELECT_ITEM",
                context=self._get_context(tok.line),
            )

        alias = self.parse_alias_clause(is_select_item=True)
        return SelectItemNode(expr=expr, alias=alias, line=item_line, column=item_col)

    def parse_agg_expr(self) -> AggExprNode:
        """
        agg_expr ::= "COUNT" "(" ( column | "*" ) ")"
                   | ( "SUM" | "AVG" | "MIN" | "MAX" ) "(" column ")"
        """
        func_tok = self._advance()
        func_name = str(func_tok.value).upper()
        self._expect(TokenType.LPAREN, f"Expected '(' after aggregate function '{func_name}'")

        if self._match(TokenType.STAR):
            star_tok = self._advance()
            if func_name != "COUNT":
                raise ParserSyntaxError(
                    message=f"Aggregate function '{func_name}(*)' is invalid. Only COUNT(*) permits the wildcard.",
                    token=star_tok,
                    expected="column identifier",
                    error_code="ERR_ILLEGAL_AGGREGATE_WILDCARD",
                    context=self._get_context(star_tok.line),
                )
            arg = StarNode(line=star_tok.line, column=star_tok.column)
        elif self._match(TokenType.IDENTIFIER):
            arg = self.parse_column()
        else:
            curr = self._current_token()
            raise ParserSyntaxError(
                message=f"Expected column or '*' inside {func_name}(), found '{curr.value}'",
                token=curr,
                expected="column or *",
                error_code="ERR_AGG_ARGUMENT",
                context=self._get_context(curr.line),
            )

        self._expect(TokenType.RPAREN, f"Expected ')' closing aggregate function '{func_name}'")
        return AggExprNode(func=func_name, argument=arg, line=func_tok.line, column=func_tok.column)

    def parse_table_ref(self) -> TableRefNode:
        """table_ref ::= IDENTIFIER [ alias_clause ]"""
        tbl_tok = self._expect(TokenType.IDENTIFIER, "Expected table name")
        alias = self.parse_alias_clause(is_select_item=False)
        return TableRefNode(name=str(tbl_tok.value), alias=alias, line=tbl_tok.line, column=tbl_tok.column)

    def parse_alias_clause(self, is_select_item: bool = False) -> Optional[str]:
        """alias_clause ::= [ "AS" ] IDENTIFIER"""
        if self._match(TokenType.AS):
            self._advance()
            alias_tok = self._expect(TokenType.IDENTIFIER, "Expected identifier after 'AS'")
            return str(alias_tok.value)

        # Implicit shorthand alias without 'AS'
        if self._match(TokenType.IDENTIFIER):
            if is_select_item:
                # Lookahead: an implicit column alias must be followed by ',' or 'FROM'
                peek = self._peek_token(1)
                if peek.type in (TokenType.COMMA, TokenType.FROM):
                    alias_tok = self._advance()
                    return str(alias_tok.value)
                return None
            else:
                # Table alias in FROM/JOIN: valid if not a keyword starting next clause
                curr = self._current_token()
                if curr.type not in (
                    TokenType.JOIN, TokenType.INNER, TokenType.LEFT, TokenType.ON,
                    TokenType.WHERE, TokenType.GROUP, TokenType.HAVING, TokenType.ORDER,
                    TokenType.LIMIT, TokenType.SEMICOLON, TokenType.EOF,
                ):
                    alias_tok = self._advance()
                    return str(alias_tok.value)

        return None

    def parse_join_clause(self) -> JoinNode:
        """join_clause ::= [ "INNER" | "LEFT" ] "JOIN" table_ref "ON" condition"""
        join_line = self._current_token().line
        join_col = self._current_token().column
        join_type = "INNER"

        if self._match(TokenType.INNER):
            self._advance()
            self._expect(TokenType.JOIN, "Expected 'JOIN' after 'INNER'")
            join_type = "INNER"
        elif self._match(TokenType.LEFT):
            self._advance()
            self._expect(TokenType.JOIN, "Expected 'JOIN' after 'LEFT'")
            join_type = "LEFT"
        elif self._match(TokenType.JOIN):
            self._advance()
            join_type = "INNER"

        table = self.parse_table_ref()
        self._expect(TokenType.ON, f"Expected 'ON' condition for {join_type} JOIN")
        on_cond = self.parse_condition()

        return JoinNode(join_type=join_type, table=table, on_condition=on_cond, line=join_line, column=join_col)

    def parse_condition(self) -> ConditionNode:
        """condition ::= or_expr"""
        return self.parse_or_expr()

    def parse_or_expr(self) -> ConditionNode:
        """or_expr ::= and_expr { "OR" and_expr }*"""
        left = self.parse_and_expr()

        while self._match(TokenType.OR):
            op_tok = self._advance()
            right = self.parse_and_expr()
            left = BinaryConditionNode(
                op="OR",
                left=left,
                right=right,
                line=op_tok.line,
                column=op_tok.column,
            )

        return left

    def parse_and_expr(self) -> ConditionNode:
        """and_expr ::= comparison { "AND" comparison }*"""
        left = self.parse_comparison()

        while self._match(TokenType.AND):
            op_tok = self._advance()
            right = self.parse_comparison()
            left = BinaryConditionNode(
                op="AND",
                left=left,
                right=right,
                line=op_tok.line,
                column=op_tok.column,
            )

        return left

    def parse_comparison(self) -> ConditionNode:
        """comparison ::= operand comp_op operand | "(" condition ")" """
        if self._match(TokenType.LPAREN):
            lparen_tok = self._advance()
            cond = self.parse_condition()
            self._expect(TokenType.RPAREN, "Expected ')' closing parenthesized condition")
            cond.line = lparen_tok.line
            cond.column = lparen_tok.column
            return cond

        left_op = self.parse_operand()
        comp_tok = self._current_token()

        if not self._match(
            TokenType.EQUALS,
            TokenType.NOT_EQUALS,
            TokenType.LESS_THAN,
            TokenType.GREATER_THAN,
            TokenType.LESS_EQUALS,
            TokenType.GREATER_EQUALS,
        ):
            raise ParserSyntaxError(
                message=f"Expected relational comparison operator (=, !=, <, >, <=, >=), found '{comp_tok.value}'",
                token=comp_tok,
                expected="comparison operator",
                error_code="ERR_INVALID_OPERATOR",
                context=self._get_context(comp_tok.line),
            )

        self._advance()
        right_op = self.parse_operand()

        return ComparisonNode(
            op=str(comp_tok.value),
            left=left_op,
            right=right_op,
            line=comp_tok.line,
            column=comp_tok.column,
        )

    def parse_operand(self) -> OperandNode:
        """operand ::= column | literal"""
        tok = self._current_token()
        if self._match(TokenType.COUNT, TokenType.SUM, TokenType.AVG, TokenType.MIN, TokenType.MAX):
            return self.parse_agg_expr()
        elif self._match(TokenType.STRING):
            self._advance()
            val = str(tok.value)
            dt = "DATE" if DATE_PATTERN.match(val) else "VARCHAR"
            return LiteralNode(value=val, data_type=dt, line=tok.line, column=tok.column)
        elif self._match(TokenType.NUMBER):
            self._advance()
            dt = "FLOAT" if isinstance(tok.value, float) else "INT"
            return LiteralNode(value=tok.value, data_type=dt, line=tok.line, column=tok.column)
        elif self._match(TokenType.IDENTIFIER):
            return self.parse_column()
        else:
            raise ParserSyntaxError(
                message=f"Expected column, aggregate function, or literal value, found '{tok.value}'",
                token=tok,
                expected="column, aggregate function, or literal",
                error_code="ERR_INVALID_OPERAND",
                context=self._get_context(tok.line),
            )

    def parse_column_list(self) -> List[ColumnNode]:
        """column_list ::= column { "," column }*"""
        cols = [self.parse_column()]
        while self._match(TokenType.COMMA):
            self._advance()
            cols.append(self.parse_column())
        return cols

    def parse_order_list(self) -> List[OrderItemNode]:
        """order_list ::= order_item { "," order_item }*"""
        items = [self.parse_order_item()]
        while self._match(TokenType.COMMA):
            self._advance()
            items.append(self.parse_order_item())
        return items

    def parse_order_item(self) -> OrderItemNode:
        """order_item ::= column [ "ASC" | "DESC" ]"""
        col = self.parse_column()
        direction = "ASC"
        if self._match(TokenType.ASC):
            self._advance()
            direction = "ASC"
        elif self._match(TokenType.DESC):
            self._advance()
            direction = "DESC"
        return OrderItemNode(column_expr=col, direction=direction, line=col.line, column=col.column)

    def parse_column(self) -> ColumnNode:
        """column ::= [ IDENTIFIER "." ] IDENTIFIER"""
        first = self._expect(TokenType.IDENTIFIER, "Expected column identifier")
        if self._match(TokenType.DOT):
            self._advance()
            second = self._expect(TokenType.IDENTIFIER, "Expected column name after '.'")
            return ColumnNode(
                table_prefix=str(first.value),
                column_name=str(second.value),
                line=first.line,
                column=first.column,
            )
        return ColumnNode(
            table_prefix=None,
            column_name=str(first.value),
            line=first.line,
            column=first.column,
        )
