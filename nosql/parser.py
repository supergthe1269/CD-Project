"""Predictive Recursive-Descent Parser for MongoDB MQL queries.

Course: BCSE307P - Compiler Design Lab
"""

from typing import Any, Dict, List, Optional, Tuple
from .tokens import NoSQLToken, NoSQLTokenType
from .ast_nodes import NoSQLQueryNode
from .errors import NoSQLParserSyntaxError


class NoSQLParser:
    """Parses MongoDB MQL token streams into strongly-typed NoSQLQueryNode ASTs."""

    def __init__(self, tokens: List[NoSQLToken], raw_query: str = ""):
        self.tokens = tokens
        self.raw_query = raw_query
        self.pos = 0
        self.field_positions: Dict[str, Tuple[int, int]] = {}

    def parse(self) -> NoSQLQueryNode:
        curr = self._current()

        if curr.type == NoSQLTokenType.DB:
            return self._parse_db_invocation()
        elif curr.type == NoSQLTokenType.LBRACE:
            return self._parse_json_invocation()
        else:
            raise NoSQLParserSyntaxError(
                f"Expected 'db.<collection>' or JSON object, found {curr.type.name} ({curr.value!r})",
                line=curr.line,
                column=curr.column,
                expected="db.<collection> or JSON",
                found=str(curr.value),
            )

    def _parse_db_invocation(self) -> NoSQLQueryNode:
        # 1. db
        self._consume(NoSQLTokenType.DB)
        # 2. .
        self._consume(NoSQLTokenType.DOT)

        # 3. <collection>
        col_tok = self._consume(NoSQLTokenType.IDENTIFIER)
        collection = str(col_tok.value)
        col_line = col_tok.line
        col_col = col_tok.column

        # 4. .
        self._consume(NoSQLTokenType.DOT)

        # 5. <method> (find or aggregate)
        method_tok = self._consume(NoSQLTokenType.IDENTIFIER)
        method = str(method_tok.value).lower()
        if method not in ("find", "aggregate"):
            raise NoSQLParserSyntaxError(
                f"Unsupported NoSQL method {method!r}. Supported methods: 'find', 'aggregate'",
                line=method_tok.line,
                column=method_tok.column,
                expected="find or aggregate",
                found=method,
            )

        filter_doc: Optional[Dict[str, Any]] = None
        projection_doc: Optional[Dict[str, Any]] = None
        pipeline: Optional[List[Dict[str, Any]]] = None
        sort_doc: Optional[Dict[str, Any]] = None
        limit_val: Optional[int] = None

        # 6. ( <args> )
        self._consume(NoSQLTokenType.LPAREN)

        if method == "find":
            if self._current().type != NoSQLTokenType.RPAREN:
                filter_doc = self._parse_object()
                if self._match(NoSQLTokenType.COMMA):
                    self._advance()
                    if self._current().type != NoSQLTokenType.RPAREN:
                        projection_doc = self._parse_object()
            else:
                filter_doc = {}
            self._consume(NoSQLTokenType.RPAREN)

            # Chained calls: .sort(...), .limit(...)
            while self._match(NoSQLTokenType.DOT):
                self._advance()
                chain_tok = self._consume(NoSQLTokenType.IDENTIFIER)
                chain_name = str(chain_tok.value).lower()
                self._consume(NoSQLTokenType.LPAREN)
                if chain_name == "sort":
                    sort_doc = self._parse_object()
                elif chain_name == "limit":
                    num_tok = self._consume(NoSQLTokenType.NUMBER)
                    limit_val = int(num_tok.value)
                else:
                    raise NoSQLParserSyntaxError(
                        f"Unsupported chained modifier .{chain_name}(). Supported: .sort(), .limit()",
                        line=chain_tok.line,
                        column=chain_tok.column,
                    )
                self._consume(NoSQLTokenType.RPAREN)

        elif method == "aggregate":
            if self._current().type != NoSQLTokenType.RPAREN:
                pipeline = self._parse_array()
            else:
                pipeline = []
            self._consume(NoSQLTokenType.RPAREN)

        return NoSQLQueryNode(
            collection=collection,
            collection_line=col_line,
            collection_column=col_col,
            method=method,
            filter_doc=filter_doc,
            projection_doc=projection_doc,
            sort_doc=sort_doc,
            limit_val=limit_val,
            pipeline=pipeline,
            field_positions=dict(self.field_positions),
        )

    def _parse_json_invocation(self) -> NoSQLQueryNode:
        """Parses standalone JSON-style query descriptor."""
        doc = self._parse_object()
        collection = doc.get("collection", "customers")
        method = "aggregate" if "pipeline" in doc else "find"
        return NoSQLQueryNode(
            collection=collection,
            collection_line=1,
            collection_column=1,
            method=method,
            filter_doc=doc.get("filter", doc),
            projection_doc=doc.get("projection"),
            sort_doc=doc.get("sort"),
            limit_val=doc.get("limit"),
            pipeline=doc.get("pipeline"),
            field_positions=dict(self.field_positions),
        )

    # -------------------------------------------------------------------------
    # JSON / BSON Value Parsers
    # -------------------------------------------------------------------------

    def _parse_object(self) -> Dict[str, Any]:
        self._consume(NoSQLTokenType.LBRACE)
        obj: Dict[str, Any] = {}

        while not self._match(NoSQLTokenType.RBRACE):
            curr = self._current()
            if curr.type in (NoSQLTokenType.STRING, NoSQLTokenType.IDENTIFIER, NoSQLTokenType.OPERATOR):
                key = str(curr.value)
                self.field_positions[key] = (curr.line, curr.column)
                self._advance()
            else:
                raise NoSQLParserSyntaxError(
                    f"Expected object key, found {curr.type.name} ({curr.value!r})",
                    line=curr.line,
                    column=curr.column,
                    expected="Key (string/identifier)",
                    found=str(curr.value),
                )

            self._consume(NoSQLTokenType.COLON)
            val = self._parse_value()
            obj[key] = val

            if self._match(NoSQLTokenType.COMMA):
                self._advance()
            else:
                break

        self._consume(NoSQLTokenType.RBRACE)
        return obj

    def _parse_array(self) -> List[Any]:
        self._consume(NoSQLTokenType.LBRACKET)
        arr: List[Any] = []

        while not self._match(NoSQLTokenType.RBRACKET):
            val = self._parse_value()
            arr.append(val)

            if self._match(NoSQLTokenType.COMMA):
                self._advance()
            else:
                break

        self._consume(NoSQLTokenType.RBRACKET)
        return arr

    def _parse_value(self) -> Any:
        curr = self._current()
        if curr.type == NoSQLTokenType.LBRACE:
            return self._parse_object()
        elif curr.type == NoSQLTokenType.LBRACKET:
            return self._parse_array()
        elif curr.type in (NoSQLTokenType.STRING, NoSQLTokenType.NUMBER, NoSQLTokenType.BOOLEAN, NoSQLTokenType.NULL):
            self._advance()
            return curr.value
        elif curr.type == NoSQLTokenType.OPERATOR:
            self._advance()
            return str(curr.value)
        elif curr.type == NoSQLTokenType.IDENTIFIER:
            # Unquoted string value
            self._advance()
            return str(curr.value)
        else:
            raise NoSQLParserSyntaxError(
                f"Unexpected token in value expression: {curr.type.name} ({curr.value!r})",
                line=curr.line,
                column=curr.column,
            )

    # -------------------------------------------------------------------------
    # Helper Token Methods
    # -------------------------------------------------------------------------

    def _current(self) -> NoSQLToken:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]

    def _match(self, token_type: NoSQLTokenType) -> bool:
        return self._current().type == token_type

    def _advance(self) -> NoSQLToken:
        tok = self._current()
        if self.pos < len(self.tokens):
            self.pos += 1
        return tok

    def _consume(self, expected_type: NoSQLTokenType) -> NoSQLToken:
        curr = self._current()
        if curr.type != expected_type:
            raise NoSQLParserSyntaxError(
                f"Expected {expected_type.name}, found {curr.type.name} ({curr.value!r})",
                line=curr.line,
                column=curr.column,
                expected=expected_type.name,
                found=str(curr.value),
            )
        return self._advance()
