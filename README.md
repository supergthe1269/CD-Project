# AI-Augmented Multi-Model Query Compiler & Validator (SQL + NoSQL MongoDB)

**Course:** BCSE307P — Compiler Design Lab  
**Team:**
| Reg. No | Name | Contribution |
|---|---|---|
| 24BCB0020 | Gaurav Gopichand Nanhe | Grammar (EBNF), lexer, recursive-descent parser & AST, code formatter, NoSQL transpiler |
| 24BAI0351 | V Surya | Symbol table / catalog, semantic checker, NoSQL validator, AI prompt & error mentor design |

---

## Overview

A hand-built compiler pipeline and transcompiler supporting both **Relational SQL** and **NoSQL (MongoDB Query Language - MQL)**, with AI used strictly at the edges — never inside the compiler itself.

1. **SQL Front-End & Target Code Synthesis (Transpiler):** Tokenizes, parses, and semantically validates SQL queries against a schema catalog, formats canonical SQL, and **compiles the validated AST into executable MongoDB MQL (`find` queries and `aggregate` pipelines)** with PyMongo code generation.
2. **Direct NoSQL Validator:** Accepts raw MongoDB MQL shell syntax or JSON documents (`db.collection.find(...)` / `db.collection.aggregate(...)`), parses them through a dedicated NoSQL lexer & parser into an MQL AST, and performs semantic validation (collection existence, field existence, operator validity with fuzzy typo recovery, and type checks).
3. **AI Mentor Edge:** If validation fails, structured compiler diagnostic records are explained in plain English by the AI mentor without masking raw compiler coordinates.

**Core idea: AI proposes, the compiler decides.**

---

## Architectural Pipeline

```
[SQL Input / NL Query]                        [Direct NoSQL MQL Input]
        |                                                 |
        v                                                 v
  SQL Lexer -> Token stream                     NoSQL Lexer -> Token stream
        |                                                 |
        v                                                 v
  SQL Parser -> SQL AST (Recursive Descent)     NoSQL Parser -> NoSQL AST
        |                                                 |
        v                                                 v
  SQL Semantic Checker (Catalog/FK/Types)       NoSQL Semantic Checker (Collection/Fields/Operators)
        |                                                 |
   _____|_____                                       _____|_____
  |           |                                     |           |
Pass        Fail                                   Pass        Fail
  |           |                                     |           |
  v           v                                     v           v
SQL Formatter AI Error Mentor                 NoSQL Formatter  AI Error Mentor
  |           (+ Raw Diagnostics)                   |          (+ Raw Diagnostics)
  v                                                 v
Target Code Generator (NoSQL Transpiler)     Canonical MQL Shell Output
  |
  +---> MongoDB find() / aggregate()
  +---> PyMongo Python target
```

---

## Compiler Phases

### SQL Compiler & Transpiler
- **Lexer:** Character-by-character scanner with exact line and column tracking.
- **Parser:** Predictive recursive-descent parser building strongly-typed AST nodes (`SelectStmtNode`, `ConditionNode`, etc.).
- **Semantic Checker:** Enforces table/column existence, type compatibility, valid FK join relationships, and GROUP BY consistency.
- **Formatter:** Canonical pretty-printer unparsing AST back to standard capitalized SQL.
- **Target Code Generator (`codegen/nosql_transpiler.py`):** Target code synthesis translating validated SQL AST into:
  - `find()` with filters (`$eq`, `$gt`, `$ne`, etc.), projections, `.sort()`, and `.limit()`.
  - `aggregate()` pipelines with `$group`, `$project`, `$match` (HAVING), and multi-collection `$lookup` / `$unwind` (JOINs).
  - Ready-to-run PyMongo Python snippets.

### Direct NoSQL Compiler (`nosql/`)
- **NoSQL Lexer:** Scans MongoDB shell queries and JSON objects, tracking lines and columns.
- **NoSQL Parser:** Parses `db.<collection>.<method>(...)` and chained modifiers (`.sort()`, `.limit()`).
- **NoSQL Semantic Checker:** Validates:
  - Collection existence in catalog (with Levenshtein distance typo suggestions).
  - MongoDB operator validity (`$gt`, `$match`, `$group`, etc. catching typos like `$gtt`).
  - Document field existence in filters, projections, and aggregations.
  - Value type compatibility.
- **NoSQL Formatter:** Emits clean, 2-space indented MongoDB shell JavaScript syntax.

---

## Status

**Fully Implemented & Verified** — 64/64 automated unit tests passing, all 10 evaluation matrix scenarios verified, complete zero-dependency REST drivers for Google Gemini / OpenAI with automatic offline fallback heuristics, and zero external compiler generator dependencies.

---

## Repo Structure

```
CD/
├── main.py                    # Unified entry point & interactive REPL / CLI
├── requirements.txt           # Optional dependencies (google-genai, pytest)
├── .env.example               # Environment variables template for API keys
├── grammar/
│   ├── sql_grammar.ebnf       # Formal EBNF grammar specification
│   └── README.md              # Precedence rules & grammar design rationale
├── lexer/
│   ├── tokens.py              # TokenType enum and Token dataclass (line/col tracking)
│   ├── lexer.py               # Hand-crafted character-by-character scanner
│   └── errors.py              # LexicalError & DiagnosticRecord
├── parser/
│   ├── ast_nodes.py           # Strongly-typed AST dataclasses (ASCII tree renderer)
│   ├── parser.py              # Recursive-descent predictive parser
│   └── errors.py              # ParserSyntaxError
├── semantic/
│   ├── catalog.py             # Database Catalog & schema definitions
│   ├── symbol_table.py        # Table scope, alias tracking, column resolution
│   ├── checker.py             # 5 semantic verification checks + auto-correction
│   ├── fuzzy.py               # Levenshtein distance & fuzzy catalog matching
│   └── errors.py              # SemanticError
├── formatter/
│   └── pretty_printer.py      # Canonical AST pretty-printer & unparser
├── codegen/
│   ├── __init__.py            # Target code generation package
│   └── nosql_transpiler.py    # SQL AST -> MongoDB MQL & PyMongo Transpiler
├── nosql/
│   ├── __init__.py            # NoSQL compiler package
│   ├── tokens.py              # NoSQL Token types
│   ├── lexer.py               # Character scanner for MongoDB MQL
│   ├── ast_nodes.py           # NoSQL AST definitions
│   ├── parser.py              # Recursive-descent MQL parser
│   ├── checker.py             # Collection, operator, and field semantic validator
│   ├── formatter.py           # Canonical MQL shell pretty-printer
│   └── errors.py              # NoSQL structured errors & diagnostics
├── ai/
│   ├── llm_client.py          # Unified client with native REST drivers (Gemini / OpenAI / Mock)
│   ├── nl_to_sql.py           # Natural Language -> candidate SQL translator
│   └── error_explainer.py     # DiagnosticRecord -> plain-English mentor
└── tests/
    ├── test_lexer.py          # SQL Lexer tests
    ├── test_parser.py         # SQL Parser tests
    ├── test_semantic.py       # Semantic checker tests
    ├── test_formatter.py      # SQL Formatter tests
    ├── test_codegen_nosql.py  # SQL -> MongoDB Transpiler tests (9 tests)
    ├── test_nosql_validator.py# Direct NoSQL validator tests (12 tests)
    ├── test_ai_client.py      # AI client & REST fallback tests (7 tests)
    └── test_matrix.py         # 10 canonical evaluation scenarios
```

---

## AI Integration & API Key Setup

The compiler works **100% offline out-of-the-box** using deterministic heuristic models. If you have a Google Gemini or OpenAI API key, you can activate live generation with **zero external dependencies** (uses Python's native `urllib`):

### Option A: `.env` File (Recommended)
Copy the template and paste your key:
```bash
copy .env.example .env
```
Inside `.env`:
```env
GEMINI_API_KEY=AIzaSyYourGeminiApiKeyHere
```

### Option B: CLI Argument
Pass the key directly on any command:
```bash
python main.py --api-key "AIzaSy..." --nl "Find all customers in Delhi"
```

### Option C: Inside the Interactive REPL
Type `key <API_KEY>` inside the interactive prompt to test and switch keys on the fly:
```
query-compiler > key AIzaSy...
Configured AI Key: Google Gemini [AIza...34X]
Testing live connectivity...
[✓] Google Gemini API connected successfully
```

---

## Quickstart & Usage

### 1. Test AI Connectivity & Status
```bash
# Check active AI configuration
python main.py --ai-status

# Test connectivity to live model
python main.py --test-ai
```

### 2. Run All 64 Automated Unit Tests
```bash
python -m unittest discover tests
```

### 3. Run the 10 Evaluation Matrix Scenarios
```bash
python main.py --matrix
```

### 4. Run the Full Pipeline Demo (SQL + NoSQL)
```bash
python main.py --demo
```

### 5. Interactive REPL Mode (Auto-Detects SQL vs NoSQL)
```bash
python main.py
```
*In the REPL:*
- Type any SQL query to validate, format, and synthesize MongoDB MQL.
- Type any NoSQL query starting with `db.` to validate and format MQL.
- Prefix with `nl:` for natural language queries.
- Type `key <API_KEY>` to set or change your AI key live.
- Type `ai-status` to inspect connectivity.
- Type `matrix`, `demo`, or `catalog`.

### 6. Validate SQL & Synthesize MongoDB MQL
```bash
python main.py --query "SELECT name, city FROM customers WHERE city = 'Delhi' ORDER BY name ASC LIMIT 10"
```

### 7. Validate a Direct NoSQL Query
```bash
python main.py --nosql "db.customers.find({ \"city\": \"Delhi\" }, { \"name\": 1 }).limit(5);"
```

### 8. Natural Language Translation & Validation
```bash
python main.py --nl "Find all customers from Delhi"
```
