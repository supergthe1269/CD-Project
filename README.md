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

**Fully Implemented & Verified** — End-to-end hand-written compiler pipeline with zero external compiler dependencies, 33/33 automated tests passing, all 7 evaluation matrix scenarios verified, and decoupled AI edges with built-in offline fallbacks.

## Repo Structure

```
CD/
├── main.py                    # Unified entry point & interactive REPL / CLI
├── requirements.txt           # Optional dependencies (google-genai, pytest)
├── grammar/
│   ├── sql_grammar.ebnf       # Formal EBNF grammar specification
│   └── README.md              # Precedence rules & grammar design rationale
├── lexer/
│   ├── tokens.py              # TokenType enum and Token dataclass (line/col tracking)
│   ├── lexer.py               # Hand-crafted character-by-character scanner
│   └── errors.py              # LexicalError & DiagnosticRecord
├── parser/
│   ├── ast_nodes.py           # Strongly-typed AST dataclasses (ASCII tree renderer)
│   ├── parser.py              # Recursive-descent LL(1) predictive parser
│   └── errors.py              # ParserSyntaxError
├── semantic/
│   ├── catalog.py             # Relational Database Catalog & schema definitions
│   ├── symbol_table.py        # Table scope, alias tracking, column ambiguity resolution
│   ├── checker.py             # 5 semantic verification checks + auto-correction
│   ├── fuzzy.py               # Levenshtein distance & fuzzy catalog matching
│   └── errors.py              # SemanticError
├── formatter/
│   └── pretty_printer.py      # Canonical AST pretty-printer & unparser
├── ai/
│   ├── llm_client.py          # Unified client (Gemini / OpenAI / Mock offline provider)
│   ├── nl_to_sql.py           # Natural Language -> candidate SQL translator
│   └── error_explainer.py     # DiagnosticRecord -> plain-English mentor
└── tests/
    ├── test_lexer.py          # Tokenization, trivia, line/col tracking tests
    ├── test_parser.py         # Recursive descent, AST construction, precedence tests
    ├── test_semantic.py       # Catalog binding, FK checks, type checks, GROUP BY tests
    ├── test_formatter.py      # Canonical formatting & indentation tests
    └── test_matrix.py         # 7 canonical report evaluation scenarios
```

## Quickstart & Usage

### 1. Run the Full Pipeline Demo
```bash
python main.py --demo
```

### 2. Run the 7 Evaluation Scenarios (Report Section 11)
```bash
python main.py --matrix
```

### 3. Run All Automated Unit Tests
```bash
python -m unittest discover tests
```

### 4. Interactive REPL Mode
```bash
python main.py
```
*Tip: Inside the REPL, type SQL queries, prefix with `nl:` for natural language queries, type `matrix`, `demo`, or `catalog`.*

### 5. Validate a Direct SQL Query
```bash
python main.py --query "SELECT c.name, o.status FROM customers c JOIN orders o ON c.id = o.customer_id"
```

### 6. Natural Language Translation & Validation
```bash
python main.py --nl "Find all customers from Delhi"
```

### 7. AST-Based Fuzzy Auto-Correction
```bash
python main.py --auto-correct --query "SELECT c.name, o.status FROM customers c JOIN orders o ON c.id = o.cust_id"
```
*(Notice: automatically repairs `cust_id` -> `customer_id` via Levenshtein distance $\le 2$).*

