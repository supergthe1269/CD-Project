"""AI-Augmented SQL Query Validator & Formatter.

Course: BCSE307P - Compiler Design Lab
Team:
  - Gaurav Gopichand Nanhe (24BCB0020)
  - V Surya (24BAI0351)

Unified CLI entry point, interactive REPL, and validation suite runner.
"""

import sys
import os
import argparse
import json
from typing import Optional, Tuple, Dict, Any

# Ensure UTF-8 stdout on all terminals (including Windows cp1252)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from lexer.lexer import Lexer
from lexer.errors import LexicalError, DiagnosticRecord
from parser.parser import Parser
from parser.errors import ParserSyntaxError
from semantic.catalog import DatabaseCatalog, create_default_catalog
from semantic.checker import SemanticChecker
from semantic.errors import SemanticError
from formatter.pretty_printer import SQLFormatter
from codegen.nosql_transpiler import NoSQLTranspiler, MQLResult
from nosql import (
    NoSQLLexer,
    NoSQLParser,
    NoSQLSemanticChecker,
    NoSQLFormatter,
    NoSQLLexicalError,
    NoSQLParserSyntaxError,
    NoSQLSemanticError,
)
from ai.nl_to_sql import NLToSQLTranslator
from ai.error_explainer import AIErrorExplainer


# --- ANSI Color Helpers ---
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


from ai.llm_client import LLMClient


def print_banner(pipeline: Optional["CompilerPipeline"] = None):
    ai_badge = ""
    if pipeline:
        status = pipeline.get_ai_status()
        if status.get("is_live"):
            ai_badge = f"\n  AI Status: {Colors.GREEN}● LIVE ({status['provider']} - {status['model']}){Colors.RESET} [Key: {status['masked_key']}]"
        elif pipeline.enable_ai:
            ai_badge = f"\n  AI Status: {Colors.YELLOW}○ OFFLINE MOCK HEURISTIC (No API key configured){Colors.RESET}"
        else:
            ai_badge = f"\n  AI Status: {Colors.DIM}✕ DISABLED{Colors.RESET}"

    banner = f"""{Colors.CYAN}{Colors.BOLD}
========================================================================
  AI-Augmented SQL Query Validator & Formatter (BCSE307P Compiler Lab)
  Core Principle: "AI Proposes, The Compiler Decides"
  Team: 24BCB0020 (Gaurav Nanhe) | 24BAI0351 (V Surya){ai_badge}
========================================================================{Colors.RESET}"""
    print(banner)


class CompilerPipeline:
    """End-to-end multi-model compiler pipeline coordinating all SQL & NoSQL phases."""

    def __init__(
        self,
        catalog: Optional[DatabaseCatalog] = None,
        auto_correct: bool = False,
        enable_ai: bool = True,
        api_key: Optional[str] = None,
    ):
        self.catalog = catalog or create_default_catalog()
        self.auto_correct = auto_correct
        self.enable_ai = enable_ai
        self.api_key = api_key
        self.llm_client = LLMClient(api_key=api_key) if enable_ai else None
        self.nl_translator = NLToSQLTranslator(client=self.llm_client, catalog=self.catalog) if enable_ai else None
        self.ai_explainer = AIErrorExplainer(client=self.llm_client) if enable_ai else None
        self.formatter = SQLFormatter()
        self.nosql_transpiler = NoSQLTranspiler()
        self.nosql_formatter = NoSQLFormatter()

    def set_api_key(self, api_key: str):
        """Updates API key dynamically at runtime."""
        self.api_key = api_key
        if self.llm_client:
            self.llm_client.set_api_key(api_key)

    def get_ai_status(self) -> Dict[str, Any]:
        """Returns provider, live status, and model name."""
        if not self.enable_ai or not self.llm_client:
            return {"is_live": False, "provider": "Disabled", "model": "none", "masked_key": None}
        return self.llm_client.get_status()

    def test_ai_connection(self) -> Tuple[bool, str]:
        """Runs a live diagnostic ping to the configured LLM API."""
        if not self.enable_ai or not self.llm_client:
            return False, "AI edge is currently disabled."
        return self.llm_client.test_connection()

    def process_query(self, query: str, verbose: bool = False, emit_nosql: bool = True) -> Tuple[bool, Optional[str], Optional[DiagnosticRecord]]:
        """
        Executes SQL query through the full compiler pipeline:
        Lexer -> Parser -> Semantic Checker -> SQL Formatter -> NoSQL Code Generation (Synthesis).
        Returns: (success: bool, formatted_sql_or_output: str, diagnostic: Optional[DiagnosticRecord])
        """
        if verbose:
            print(f"\n{Colors.BOLD}Input Query:{Colors.RESET}\n  {query}\n")

        # ---------------- Phase 1: Lexical Analysis ----------------
        try:
            lexer = Lexer(query)
            tokens = lexer.tokenize()
            if verbose:
                print(f"{Colors.GREEN}[✓] Phase 1: Lexer Succeeded{Colors.RESET} ({len(tokens)} tokens generated)")
                tok_repr = ", ".join(f"[{t.type.name}: {t.value!r}]" for t in tokens[:-1])
                print(f"    {Colors.DIM}{tok_repr}{Colors.RESET}")
        except LexicalError as le:
            diag = le.to_diagnostic()
            self._handle_failure(query, diag)
            return False, None, diag

        # ---------------- Phase 2: Syntax Analysis -----------------
        try:
            parser = Parser(tokens, query)
            ast = parser.parse()
            if verbose:
                print(f"\n{Colors.GREEN}[✓] Phase 2: Parser Succeeded{Colors.RESET} (AST produced)")
                print(f"{Colors.DIM}{ast.format_tree()}{Colors.RESET}")
        except ParserSyntaxError as se:
            diag = se.to_diagnostic()
            self._handle_failure(query, diag)
            return False, None, diag

        # ---------------- Phase 3: Semantic Analysis ---------------
        try:
            checker = SemanticChecker(self.catalog, query, auto_correct=self.auto_correct)
            notices = checker.validate(ast)
            if verbose:
                print(f"\n{Colors.GREEN}[✓] Phase 3: Semantic Validation Succeeded{Colors.RESET}")
                if notices:
                    for n in notices:
                        print(f"    {Colors.YELLOW}[NOTICE] {n}{Colors.RESET}")
        except SemanticError as sme:
            diag = sme.to_diagnostic()
            self._handle_failure(query, diag)
            return False, None, diag

        # ---------------- Phase 4: AST Pretty-Printing -------------
        formatted_sql = self.formatter.format(ast)
        if verbose:
            print(f"\n{Colors.GREEN}[✓] Phase 4: AST Formatter Succeeded (Canonical Output):{Colors.RESET}")
            print(f"{Colors.BOLD}{Colors.CYAN}{formatted_sql}{Colors.RESET}")

        # ---------------- Phase 5: Target Code Generation (NoSQL Synthesis) ----
        if emit_nosql:
            mql_res = self.nosql_transpiler.transpile(ast)
            if verbose:
                print(f"\n{Colors.GREEN}[✓] Phase 5: Target Code Generation (MongoDB MQL Synthesis):{Colors.RESET}")
                print(f"{Colors.BOLD}{Colors.YELLOW}{mql_res.mql_string}{Colors.RESET}")
                print(f"\n{Colors.DIM}PyMongo Driver Target:\n  {mql_res.to_pymongo()}{Colors.RESET}\n")

        return True, formatted_sql, None

    def process_nosql_query(self, query: str, verbose: bool = False) -> Tuple[bool, Optional[str], Optional[DiagnosticRecord]]:
        """
        Executes MongoDB MQL query through the direct NoSQL compiler pipeline:
        NoSQLLexer -> NoSQLParser -> NoSQLSemanticChecker -> NoSQLFormatter.
        Returns: (success: bool, canonical_mql: str, diagnostic: Optional[DiagnosticRecord])
        """
        if verbose:
            print(f"\n{Colors.BOLD}Input NoSQL Query:{Colors.RESET}\n  {query}\n")

        # ---------------- Phase 1: NoSQL Lexer ----------------
        try:
            lexer = NoSQLLexer(query)
            tokens = lexer.tokenize()
            if verbose:
                print(f"{Colors.GREEN}[✓] Phase 1: NoSQL Lexer Succeeded{Colors.RESET} ({len(tokens)} tokens generated)")
        except NoSQLLexicalError as le:
            diag = le.to_diagnostic()
            self._handle_failure(query, diag)
            return False, None, diag

        # ---------------- Phase 2: NoSQL Parser ---------------
        try:
            parser = NoSQLParser(tokens, query)
            ast = parser.parse()
            if verbose:
                print(f"\n{Colors.GREEN}[✓] Phase 2: NoSQL Parser Succeeded{Colors.RESET} (AST produced)")
                print(f"{Colors.DIM}{ast.format_tree()}{Colors.RESET}")
        except NoSQLParserSyntaxError as se:
            diag = se.to_diagnostic()
            self._handle_failure(query, diag)
            return False, None, diag

        # ---------------- Phase 3: NoSQL Semantic Analysis ----
        try:
            checker = NoSQLSemanticChecker(self.catalog, auto_correct=self.auto_correct)
            checker.validate(ast)
            if verbose:
                print(f"\n{Colors.GREEN}[✓] Phase 3: NoSQL Semantic Validation Succeeded (Catalog Verified){Colors.RESET}")
        except NoSQLSemanticError as sme:
            diag = sme.to_diagnostic()
            self._handle_failure(query, diag)
            return False, None, diag

        # ---------------- Phase 4: NoSQL Canonical Formatter --
        formatted_mql = self.nosql_formatter.format(ast)
        if verbose:
            print(f"\n{Colors.GREEN}[✓] Phase 4: NoSQL Formatter Succeeded (Canonical MQL):{Colors.RESET}")
            print(f"{Colors.BOLD}{Colors.YELLOW}{formatted_mql}{Colors.RESET}\n")

        return True, formatted_mql, None

    def _handle_failure(self, query: str, diag: DiagnosticRecord):
        print(f"\n{Colors.RED}[✗] Pipeline Failed in Phase: {diag.phase}{Colors.RESET}")
        print(f"{Colors.BOLD}Deterministic Diagnostic Record:{Colors.RESET}")
        print(f"{Colors.DIM}{json.dumps(diag.to_dict(), indent=2)}{Colors.RESET}")

        if self.enable_ai and self.ai_explainer:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}AI Error Mentor Explanation:{Colors.RESET}")
            explanation = self.ai_explainer.explain(diag)
            print(f"{Colors.YELLOW}{explanation}{Colors.RESET}\n")


def run_validation_matrix():
    """Runs the 10 evaluation scenarios (7 SQL + 3 NoSQL Review-2 extensions)."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}--- Running Evaluation Matrix (10 Scenarios: SQL & NoSQL Extensions) ---{Colors.RESET}\n")

    cases = [
        {
            "id": 1,
            "category": "Simple Projection",
            "query": "SELECT * FROM customers;",
            "is_nosql": False,
            "expected_pass": True,
            "verification": "Wildcard resolution, single-table parsing",
        },
        {
            "id": 2,
            "category": "Boolean Precedence",
            "query": "SELECT name FROM customers WHERE city = 'Delhi' AND signup_date > '2024-01-01'",
            "is_nosql": False,
            "expected_pass": True,
            "verification": "Parsing of nested AND / OR expressions",
        },
        {
            "id": 3,
            "category": "Join Resolution",
            "query": "SELECT c.name, o.status FROM customers c JOIN orders o ON c.id = o.customer_id",
            "is_nosql": False,
            "expected_pass": True,
            "verification": "Implicit aliases, foreign key relationship validation",
        },
        {
            "id": 4,
            "category": "Group By Validation",
            "query": "SELECT city, COUNT(*) FROM customers GROUP BY city HAVING COUNT(*) > 5",
            "is_nosql": False,
            "expected_pass": True,
            "verification": "Aggregate and non-aggregate column tracking",
        },
        {
            "id": 5,
            "category": "Syntax Error Catch",
            "query": "SELECT name customers WHERE id = 1",
            "is_nosql": False,
            "expected_pass": False,
            "verification": "Missing FROM keyword",
        },
        {
            "id": 6,
            "category": "Semantic Type Mismatch",
            "query": "SELECT name FROM customers WHERE signup_date = 42",
            "is_nosql": False,
            "expected_pass": False,
            "verification": "Type verification across relational operators (DATE vs INT)",
        },
        {
            "id": 7,
            "category": "Hallucination Detection",
            "query": "SELECT full_name, order_count FROM customers",
            "is_nosql": False,
            "expected_pass": False,
            "verification": "Plausible LLM hallucination catching",
        },
        {
            "id": 8,
            "category": "Target Code Synthesis (SQL -> NoSQL MQL)",
            "query": "SELECT name, city FROM customers WHERE city = 'Delhi' ORDER BY name ASC LIMIT 10",
            "is_nosql": False,
            "expected_pass": True,
            "verification": "Target code synthesis to MongoDB find() with projection, sort, and limit",
        },
        {
            "id": 9,
            "category": "Direct NoSQL Query Validation (MQL find)",
            "query": 'db.customers.find({ "city": "Delhi" }, { "name": 1, "city": 1 }).sort({ "name": 1 }).limit(10);',
            "is_nosql": True,
            "expected_pass": True,
            "verification": "Direct MQL parsing, schema attribute validation, and pretty-printing",
        },
        {
            "id": 10,
            "category": "NoSQL Semantic Typo Catching",
            "query": 'db.cusotmers.find({ "signup_date": { "$gtt": "2024-01-01" } });',
            "is_nosql": True,
            "expected_pass": False,
            "verification": "Catching collection typo (cusotmers) and operator typo ($gtt) with fuzzy recovery",
        },
    ]

    pipeline = CompilerPipeline(enable_ai=True)
    passed_count = 0

    for c in cases:
        print(f"{Colors.BOLD}Scenario #{c['id']}: {c['category']}{Colors.RESET}")
        print(f"  Verification Point: {c['verification']}")
        print(f"  Query: {Colors.DIM}{c['query']}{Colors.RESET}")

        if c.get("is_nosql"):
            success, output, diag = pipeline.process_nosql_query(c["query"], verbose=False)
        else:
            success, output, diag = pipeline.process_query(c["query"], verbose=False)

        if success == c["expected_pass"]:
            print(f"  Result: {Colors.GREEN}[PASS]{Colors.RESET} (Matches expected outcome)\n")
            passed_count += 1
        else:
            print(f"  Result: {Colors.RED}[FAIL]{Colors.RESET} (Unexpected outcome)\n")

    print(f"{Colors.BOLD}Matrix Summary: {passed_count}/{len(cases)} tests verified successfully.{Colors.RESET}\n")


def run_demo(api_key: Optional[str] = None):
    """Runs a complete demonstration of the compiler pipeline (SQL + NoSQL)."""
    pipeline = CompilerPipeline(auto_correct=True, enable_ai=True, api_key=api_key)
    print_banner(pipeline)

    print(f"\n{Colors.BOLD}{Colors.HEADER}=== DEMO 1: Valid Complex Analytical Query (SQL -> Formatted SQL + MQL) ==={Colors.RESET}")
    sample_valid = (
        "select c.name, count(*) from customers c join orders o on c.id=o.customer_id "
        "where c.city='Delhi' group by c.name having count(*)>2 order by c.name asc limit 10;"
    )
    pipeline.process_query(sample_valid, verbose=True)

    print(f"\n{Colors.BOLD}{Colors.HEADER}=== DEMO 2: Catching LLM Hallucinations (Non-Existent Schema) ==={Colors.RESET}")
    sample_hallucination = "SELECT full_name, total_revenue FROM customers WHERE city = 'Delhi'"
    pipeline.process_query(sample_hallucination, verbose=True)

    print(f"\n{Colors.BOLD}{Colors.HEADER}=== DEMO 3: AST-Based Fuzzy Auto-Correction ==={Colors.RESET}")
    sample_fuzzy = "SELECT c.name, o.status FROM customers c JOIN orders o ON c.id = o.cust_id"
    pipeline.process_query(sample_fuzzy, verbose=True)

    print(f"\n{Colors.BOLD}{Colors.HEADER}=== DEMO 4: Decoupled AI NL-to-SQL Input Edge ==={Colors.RESET}")
    nl_question = "Find all customers living in Delhi"
    print(f"Natural Language Question: {Colors.CYAN}{nl_question}{Colors.RESET}")
    candidate_sql = pipeline.nl_translator.translate(nl_question)
    print(f"Candidate SQL proposed by AI: {Colors.YELLOW}{candidate_sql}{Colors.RESET}")
    print("Passing candidate SQL to the deterministic compiler gatekeeper...")
    pipeline.process_query(candidate_sql, verbose=True)

    print(f"\n{Colors.BOLD}{Colors.HEADER}=== DEMO 5: Direct NoSQL Validation & Formatting ==={Colors.RESET}")
    nosql_valid = 'db.customers.find({ "city": "Delhi", "signup_date": { "$gt": "2024-01-01" } }, { "name": 1, "city": 1 }).sort({ "name": 1 }).limit(10);'
    pipeline.process_nosql_query(nosql_valid, verbose=True)

    print(f"\n{Colors.BOLD}{Colors.HEADER}=== DEMO 6: NoSQL Typo Catching & AI Error Mentor ==={Colors.RESET}")
    nosql_invalid = 'db.customers.find({ "signup_date": { "$gtt": "2024-01-01" } });'
    pipeline.process_nosql_query(nosql_invalid, verbose=True)


def run_repl(api_key: Optional[str] = None):
    """Interactive command-line loop for testing SQL & NoSQL queries."""
    pipeline = CompilerPipeline(auto_correct=True, enable_ai=True, api_key=api_key)
    print_banner(pipeline)
    print("Commands:")
    print("  - Type any SQL query to validate, parse, format, and synthesize MongoDB MQL.")
    print("  - Type any NoSQL query (starts with 'db.' or '{') to validate and format MQL.")
    print("  - Prefix with 'nl:' to test Natural Language translation.")
    print("  - Type 'key <API_KEY>' to set or update Gemini / OpenAI API key live.")
    print("  - Type 'ai-status' to test and inspect the active AI provider.")
    print("  - Type 'matrix' to run the 10-case evaluation matrix.")
    print("  - Type 'demo' to run the full presentation.")
    print("  - Type 'catalog' to inspect the database schema.")
    print("  - Type 'exit' or 'quit' to close.\n")

    while True:
        try:
            user_input = input(f"{Colors.BOLD}query-compiler > {Colors.RESET}").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("Exiting Query Compiler. Goodbye!")
                break
            if user_input.lower() == "matrix":
                run_validation_matrix()
                continue
            if user_input.lower() == "demo":
                run_demo(api_key=pipeline.api_key)
                continue
            if user_input.lower() == "catalog":
                print(f"\n{Colors.BOLD}Active Database Catalog / Collections:{Colors.RESET}")
                for tbl_name in pipeline.catalog.table_names():
                    tbl = pipeline.catalog.get_table(tbl_name)
                    print(f"  {Colors.CYAN}{tbl.name}{Colors.RESET}:")
                    for col in tbl.columns.values():
                        pk_str = " [PK]" if col.is_primary_key else ""
                        fk_str = f" [FK -> {col.foreign_key_to}]" if col.foreign_key_to else ""
                        print(f"    - {col.name}: {col.data_type}{pk_str}{fk_str}")
                print()
                continue

            if user_input.lower().startswith("key ") or user_input.lower().startswith("apikey "):
                new_key = user_input.split(" ", 1)[1].strip()
                pipeline.set_api_key(new_key)
                st = pipeline.get_ai_status()
                print(f"\nConfigured AI Key: {Colors.CYAN}{st['provider']}{Colors.RESET} [{st['masked_key']}]")
                print("Testing live connectivity...")
                ok, msg = pipeline.test_ai_connection()
                if ok:
                    print(f"{Colors.GREEN}[✓] {msg}{Colors.RESET}\n")
                else:
                    print(f"{Colors.YELLOW}[!] {msg}{Colors.RESET}\n")
                continue

            if user_input.lower() in ("ai-status", "status-ai", "test-ai"):
                st = pipeline.get_ai_status()
                print(f"\n{Colors.BOLD}AI Provider:{Colors.RESET} {st['provider']} ({st['model']})")
                print(f"{Colors.BOLD}Live Active:{Colors.RESET} {st['is_live']}")
                if st['masked_key']:
                    print(f"{Colors.BOLD}Masked Key:{Colors.RESET} {st['masked_key']}")
                print("Testing live connectivity...")
                ok, msg = pipeline.test_ai_connection()
                if ok:
                    print(f"{Colors.GREEN}[✓] {msg}{Colors.RESET}\n")
                else:
                    print(f"{Colors.YELLOW}[!] {msg}{Colors.RESET}\n")
                continue

            if user_input.lower().startswith("nl:"):
                nl_query = user_input[3:].strip()
                st = pipeline.get_ai_status()
                provider_str = f" via {st['provider']}" if st['is_live'] else " (Offline Mock)"
                print(f"Proposing candidate SQL{provider_str} for: '{nl_query}'...")
                candidate = pipeline.nl_translator.translate(nl_query)
                print(f"Candidate Query: {Colors.YELLOW}{candidate}{Colors.RESET}")
                pipeline.process_query(candidate, verbose=True)
            elif user_input.startswith("db.") or user_input.startswith("{") or user_input.lower().startswith("nosql:"):
                nosql_q = user_input[6:].strip() if user_input.lower().startswith("nosql:") else user_input
                pipeline.process_nosql_query(nosql_q, verbose=True)
            else:
                pipeline.process_query(user_input, verbose=True)

        except (KeyboardInterrupt, EOFError):
            print("\nExiting Query Compiler.")
            break


def main():
    parser = argparse.ArgumentParser(description="Multi-Model Query Compiler & Validator (SQL + NoSQL MongoDB)")
    parser.add_argument("--demo", action="store_true", help="Run end-to-end pipeline demonstration")
    parser.add_argument("--matrix", "--test", action="store_true", help="Run the 10 evaluation matrix cases")
    parser.add_argument("--query", "--sql", nargs="+", type=str, help="Process a direct SQL query")
    parser.add_argument("--nosql", nargs="+", type=str, help="Process a direct NoSQL (MongoDB MQL) query")
    parser.add_argument("--nl", type=str, help="Translate and validate a Natural Language question")
    parser.add_argument("--api-key", type=str, help="API Key for Google Gemini (AIza...) or OpenAI (sk-...)")
    parser.add_argument("--test-ai", action="store_true", help="Test connectivity to live AI API and exit")
    parser.add_argument("--ai-status", action="store_true", help="Print active AI provider configuration and exit")
    parser.add_argument("--auto-correct", action="store_true", help="Enable AST-based fuzzy auto-correction")
    parser.add_argument("--no-ai", action="store_true", help="Disable all external AI edge components")

    args = parser.parse_args()

    if args.test_ai:
        pipeline = CompilerPipeline(api_key=args.api_key, enable_ai=not args.no_ai)
        st = pipeline.get_ai_status()
        print(f"\n{Colors.BOLD}AI Provider:{Colors.RESET} {st['provider']} ({st['model']})")
        if st['masked_key']:
            print(f"{Colors.BOLD}Masked Key:{Colors.RESET} {st['masked_key']}")
        print("Testing live connectivity...")
        ok, msg = pipeline.test_ai_connection()
        if ok:
            print(f"{Colors.GREEN}[✓] {msg}{Colors.RESET}\n")
        else:
            print(f"{Colors.YELLOW}[!] {msg}{Colors.RESET}\n")
        return

    if args.ai_status:
        pipeline = CompilerPipeline(api_key=args.api_key, enable_ai=not args.no_ai)
        st = pipeline.get_ai_status()
        print(f"\n{Colors.BOLD}AI Provider:{Colors.RESET} {st['provider']}")
        print(f"{Colors.BOLD}Live Model:{Colors.RESET} {st['model']}")
        print(f"{Colors.BOLD}Live Active:{Colors.RESET} {st['is_live']}")
        if st['masked_key']:
            print(f"{Colors.BOLD}Masked Key:{Colors.RESET} {st['masked_key']}")
        print()
        return

    if args.demo:
        run_demo(api_key=args.api_key)
    elif args.matrix:
        run_validation_matrix()
    elif args.nosql:
        nosql_query = " ".join(args.nosql) if isinstance(args.nosql, list) else args.nosql
        pipeline = CompilerPipeline(auto_correct=args.auto_correct, enable_ai=not args.no_ai, api_key=args.api_key)
        pipeline.process_nosql_query(nosql_query, verbose=True)
    elif args.query:
        sql_query = " ".join(args.query) if isinstance(args.query, list) else args.query
        pipeline = CompilerPipeline(auto_correct=args.auto_correct, enable_ai=not args.no_ai, api_key=args.api_key)
        pipeline.process_query(sql_query, verbose=True)
    elif args.nl:
        pipeline = CompilerPipeline(auto_correct=args.auto_correct, enable_ai=not args.no_ai, api_key=args.api_key)
        candidate = pipeline.nl_translator.translate(args.nl)
        print(f"Candidate SQL: {candidate}")
        pipeline.process_query(candidate, verbose=True)
    else:
        run_repl(api_key=args.api_key)


if __name__ == "__main__":
    main()
