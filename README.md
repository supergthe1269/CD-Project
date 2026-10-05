# AI-Augmented SQL Query Validator & Formatter

**Course:** BCSE307P — Compiler Design Lab
**Team:**
| Reg. No | Name | Contribution |
|---|---|---|
| 24BCB0020 | Gaurav Gopichand Nanhe | Grammar (EBNF), lexer, recursive-descent parser & AST, code formatter |
| 24BAI0351 | V Surya | Symbol table / catalog, semantic checker, AI prompt design, error-format design |

## Overview

A hand-built compiler pipeline for a SQL subset, with AI used only at the edges — never inside the compiler itself.

A natural-language question can optionally be turned into a candidate SQL query by an LLM. That query, like any other input, is then tokenized, parsed into an AST, and checked against a real schema by a from-scratch compiler. Only a query that passes every check gets formatted and returned. If a query fails, the compiler's structured error is handed to an LLM, which turns it into a short, plain-English explanation — the raw error is always shown too.

**Core idea: AI proposes, the compiler decides.** No stage of validation is ever delegated to the AI, and the compiler works completely on its own if every AI call is disabled.

## Why

LLM-generated SQL frequently looks right and is not: invented column names, broken joins, type mismatches. Asking an AI to double-check its own query doesn't fix this — it just repeats or varies the same mistake. A deterministic compiler, built the way real compilers are built, is what actually catches it.

## Pipeline

```
Natural language
      |
      v
   LLM (candidate SQL) ----------- untrusted input, same as typed SQL
      |
      v
   Lexer            -> token stream (with line/column tracking)
      |
      v
   Parser           -> Abstract Syntax Tree (recursive descent)
      |
      v
   Semantic Checker -> validated against schema/symbol table
      |
   ___|___
  |       |
 pass    fail
  |       |
  v       v
Formatter   AI error explainer (+ the raw structured error, always)
  |
  v
Clean, formatted SQL
```

## Compiler phases

- **Lexer** — hand-written tokenizer; no generator tools (no Flex/ANTLR). Tracks exact line and column for every token.
- **Parser** — recursive-descent, builds an AST directly from the EBNF grammar. Every grammar rule is a function.
- **Semantic checker** — walks the AST against an in-memory schema/symbol table and enforces:
  - table existence
  - column existence (and ambiguity across joins)
  - type compatibility in comparisons
  - join conditions match declared foreign keys
  - non-aggregated SELECT columns appear in GROUP BY
- **Formatter** — reads the validated AST (not the original text) and reprints it: capitalized keywords, one clause per line, indented AND/OR conditions.

## SQL subset

**In scope:** SELECT (incl. `*`, aliases), FROM, INNER/LEFT JOIN with ON, WHERE (`= != < > <= >=`, AND/OR, parentheses), GROUP BY, HAVING, ORDER BY (ASC/DESC), LIMIT, aggregates (COUNT, SUM, AVG, MIN, MAX).

**Out of scope (deliberately):** subqueries, UNION/INTERSECT/EXCEPT, window functions, INSERT/UPDATE/DELETE, DDL.

Full grammar is in the project report.

## AI integration

Two independent, removable integration points:

1. **NL → SQL** — translates a plain-English question into a candidate query, constrained by few-shot examples to the supported grammar. Output is treated as untrusted input to the lexer.
2. **Error explainer** — takes the compiler's structured error (phase, code, message, line, column, context) and produces a short, jargon-free explanation plus a suggested fix. Never replaces the original error, never used to decide validity.

Disabling both leaves a complete, independently working SQL compiler.

## Status

Planning / early implementation — see the project report for the full grammar, AST design, validation rules, test plan, and literature review.

## Repo layout *(placeholder — update once code lands)*

```
/grammar        EBNF and grammar notes
/lexer          tokenizer
/parser         recursive-descent parser, AST node definitions
/semantic       symbol table, validator
/formatter      AST -> SQL pretty-printer
/ai             NL->SQL and error-explainer prompts/integration
/tests          test queries by category (valid, syntax error, semantic error, AI-hallucination case)
/docs           report, diagrams
```
