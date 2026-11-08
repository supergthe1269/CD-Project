# SQL Grammar Specification & Design Notes

This directory defines the formal grammar for the **AI-Augmented SQL Query Validator & Formatter** in Extended Backus-Naur Form (EBNF).

## 1. Formal File
- [`sql_grammar.ebnf`](sql_grammar.ebnf)

## 2. Design Justifications

1. **Precedence Layering:**
   By nesting `condition -> or_expr -> and_expr -> comparison`, the grammar naturally guarantees that boolean `AND` binds tighter than `OR` without requiring external operator precedence declarations.
   - Example: `A OR B AND C` is parsed as `A OR (B AND C)`.
   - Parenthesized conditions `( ... )` are supported at the `comparison` level to allow arbitrary grouping.

2. **Deterministic Aggregations:**
   The grammar allows `*` strictly inside `COUNT(*)`. Illegal expressions such as `SUM(*)` or `AVG(*)` are rejected directly at the parsing phase.

3. **Flexible Aliasing:**
   The production `alias_clause ::= [ "AS" ] IDENTIFIER` uniformly allows both formal explicit aliases (`customers AS c`) and idiomatic shorthand aliases (`customers c`).

4. **Multi-Word Clause Tokenization:**
   Multi-word keywords (`GROUP BY`, `ORDER BY`, `INNER JOIN`, `LEFT JOIN`) are handled cleanly by separating individual tokens (`GROUP` + `BY`, `ORDER` + `BY`). This prevents scanner crashes when arbitrary whitespace, newlines, or comments appear between words.

## 3. Scope Boundaries

- **In Scope:** `SELECT`, `FROM`, `INNER/LEFT JOIN ... ON`, `WHERE`, `GROUP BY`, `HAVING`, `ORDER BY`, `LIMIT`, aggregates (`COUNT`, `SUM`, `AVG`, `MIN`, `MAX`), relational comparisons (`=`, `!=`, `<`, `>`, `<=`, `>=`), boolean logic (`AND`, `OR`), column/table aliases.
- **Out of Scope (Deliberate):** Subqueries, set operations (`UNION`, `INTERSECT`), window functions (`OVER`), DML (`INSERT`, `UPDATE`, `DELETE`), DDL (`CREATE`, `DROP`).
