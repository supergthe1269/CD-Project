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
from typing import Optional, Tuple

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


def print_banner():
    banner = f"""{Colors.CYAN}{Colors.BOLD}
========================================================================
  AI-Augmented SQL Query Validator & Formatter (BCSE307P Compiler Lab)
  Core Principle: "AI Proposes, The Compiler Decides"
  Team: 24BCB0020 (Gaurav Nanhe) | 24BAI0351 (V Surya)
========================================================================{Colors.RESET}"""
    print(banner)


class CompilerPipeline:
    """End-to-end compiler pipeline coordinating all phases."""

    def __init__(self, catalog: Optional[DatabaseCatalog] = None, auto_correct: bool = False, enable_ai: bool = True):
        self.catalog = catalog or create_default_catalog()
        self.auto_correct = auto_correct
        self.enable_ai = enable_ai
        self.nl_translator = NLToSQLTranslator(catalog=self.catalog) if enable_ai else None
        self.ai_explainer = AIErrorExplainer() if enable_ai else None
        self.formatter = SQLFormatter()

    def process_query(self, query: str, verbose: bool = False) -> Tuple[bool, Optional[str], Optional[DiagnosticRecord]]:
        """
        Executes query through the full compiler pipeline:
        Lexer -> Parser -> Semantic Checker -> Formatter.
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
            print(f"{Colors.BOLD}{Colors.CYAN}{formatted_sql}{Colors.RESET}\n")

        return True, formatted_sql, None

    def _handle_failure(self, query: str, diag: DiagnosticRecord):
        print(f"\n{Colors.RED}[✗] Pipeline Failed in Phase: {diag.phase}{Colors.RESET}")
        print(f"{Colors.BOLD}Deterministic Diagnostic Record:{Colors.RESET}")
        print(f"{Colors.DIM}{json.dumps(diag.to_dict(), indent=2)}{Colors.RESET}")

        if self.enable_ai and self.ai_explainer:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}AI Error Mentor Explanation:{Colors.RESET}")
            explanation = self.ai_explainer.explain(diag)
            print(f"{Colors.YELLOW}{explanation}{Colors.RESET}\n")


def run_validation_matrix():
    """Runs the 7 test scenarios from Section 11 of the project report."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}--- Running Evaluation Matrix (7 Scenarios from Report Section 11) ---{Colors.RESET}\n")

    cases = [
        {
            "id": 1,
            "category": "Simple Projection",
            "query": "SELECT * FROM customers;",
            "expected_pass": True,
            "verification": "Wildcard resolution, single-table parsing",
        },
        {
            "id": 2,
            "category": "Boolean Precedence",
            "query": "SELECT name FROM customers WHERE city = 'Delhi' AND signup_date > '2024-01-01'",
            "expected_pass": True,
            "verification": "Parsing of nested AND / OR expressions",
        },
        {
            "id": 3,
            "category": "Join Resolution",
            "query": "SELECT c.name, o.status FROM customers c JOIN orders o ON c.id = o.customer_id",
            "expected_pass": True,
            "verification": "Implicit aliases, foreign key relationship validation",
        },
        {
            "id": 4,
            "category": "Group By Validation",
            "query": "SELECT city, COUNT(*) FROM customers GROUP BY city HAVING COUNT(*) > 5",
            "expected_pass": True,
            "verification": "Aggregate and non-aggregate column tracking",
        },
        {
            "id": 5,
            "category": "Syntax Error Catch",
            "query": "SELECT name customers WHERE id = 1",
            "expected_pass": False,
            "verification": "Missing FROM keyword",
        },
        {
            "id": 6,
            "category": "Semantic Type Mismatch",
            "query": "SELECT name FROM customers WHERE signup_date = 42",
            "expected_pass": False,
            "verification": "Type verification across relational operators (DATE vs INT)",
        },
        {
            "id": 7,
            "category": "Hallucination Detection",
            "query": "SELECT full_name, order_count FROM customers",
            "expected_pass": False,
            "verification": "Plausible LLM hallucination catching",
        },
    ]

    pipeline = CompilerPipeline(enable_ai=True)
    passed_count = 0

    for c in cases:
        print(f"{Colors.BOLD}Scenario #{c['id']}: {c['category']}{Colors.RESET}")
        print(f"  Verification Point: {c['verification']}")
        print(f"  Query: {Colors.DIM}{c['query']}{Colors.RESET}")

        success, output, diag = pipeline.process_query(c["query"], verbose=False)

        if success == c["expected_pass"]:
            print(f"  Result: {Colors.GREEN}[PASS]{Colors.RESET} (Matches expected outcome)\n")
            passed_count += 1
        else:
            print(f"  Result: {Colors.RED}[FAIL]{Colors.RESET} (Unexpected outcome)\n")

    print(f"{Colors.BOLD}Matrix Summary: {passed_count}/{len(cases)} tests verified successfully.{Colors.RESET}\n")


def run_demo():
    """Runs a complete demonstration of the compiler pipeline."""
    print_banner()
    pipeline = CompilerPipeline(auto_correct=True, enable_ai=True)

    print(f"\n{Colors.BOLD}{Colors.HEADER}=== DEMO 1: Valid Complex Analytical Query ==={Colors.RESET}")
    sample_valid = (
        "select c.name, count(*) from customers c join orders o on c.id=o.customer_id "
        "where c.city='Delhi' group by c.name having count(*)>2 order by c.name asc limit 10;"
    )
    pipeline.process_query(sample_valid, verbose=True)

    print(f"\n{Colors.BOLD}{Colors.HEADER}=== DEMO 2: Catching LLM Hallucinations (Non-Existent Schema) ==={Colors.RESET}")
    sample_hallucination = "SELECT full_name, total_revenue FROM customers WHERE city = 'Delhi'"
    pipeline.process_query(sample_hallucination, verbose=True)

    print(f"\n{Colors.BOLD}{Colors.HEADER}=== DEMO 3: AST-Based Fuzzy Auto-Correction (Novelty Feature) ==={Colors.RESET}")
    sample_fuzzy = "SELECT c.name, o.status FROM customers c JOIN orders o ON c.id = o.cust_id"
    pipeline.process_query(sample_fuzzy, verbose=True)

    print(f"\n{Colors.BOLD}{Colors.HEADER}=== DEMO 4: Decoupled AI NL-to-SQL Input Edge ==={Colors.RESET}")
    nl_question = "Find all customers living in Delhi"
    print(f"Natural Language Question: {Colors.CYAN}{nl_question}{Colors.RESET}")
    candidate_sql = pipeline.nl_translator.translate(nl_question)
    print(f"Candidate SQL proposed by AI: {Colors.YELLOW}{candidate_sql}{Colors.RESET}")
    print(f"Passing candidate SQL to the deterministic compiler gatekeeper...")
    pipeline.process_query(candidate_sql, verbose=True)


def run_repl():
    """Interactive command-line loop for testing queries."""
    print_banner()
    print("Commands:")
    print("  - Type any SQL query to validate, parse, and format it.")
    print("  - Prefix with 'nl:' to test Natural Language to SQL translation.")
    print("  - Type 'matrix' to run the 7-case report validation suite.")
    print("  - Type 'demo' to run the full presentation.")
    print("  - Type 'catalog' to inspect the database schema.")
    print("  - Type 'exit' or 'quit' to close.\n")

    pipeline = CompilerPipeline(auto_correct=True, enable_ai=True)

    while True:
        try:
            user_input = input(f"{Colors.BOLD}sql-validator > {Colors.RESET}").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("Exiting SQL Validator. Goodbye!")
                break
            if user_input.lower() == "matrix":
                run_validation_matrix()
                continue
            if user_input.lower() == "demo":
                run_demo()
                continue
            if user_input.lower() == "catalog":
                print(f"\n{Colors.BOLD}Active Database Catalog:{Colors.RESET}")
                for tbl_name in pipeline.catalog.table_names():
                    tbl = pipeline.catalog.get_table(tbl_name)
                    print(f"  {Colors.CYAN}{tbl.name}{Colors.RESET}:")
                    for col in tbl.columns.values():
                        pk_str = " [PK]" if col.is_primary_key else ""
                        fk_str = f" [FK -> {col.foreign_key_to}]" if col.foreign_key_to else ""
                        print(f"    - {col.name}: {col.data_type}{pk_str}{fk_str}")
                print()
                continue

            if user_input.lower().startswith("nl:"):
                nl_query = user_input[3:].strip()
                print(f"Proposing candidate SQL via AI for: '{nl_query}'...")
                candidate = pipeline.nl_translator.translate(nl_query)
                print(f"Candidate Query: {Colors.YELLOW}{candidate}{Colors.RESET}")
                pipeline.process_query(candidate, verbose=True)
            else:
                pipeline.process_query(user_input, verbose=True)

        except (KeyboardInterrupt, EOFError):
            print("\nExiting SQL Validator.")
            break


def main():
    parser = argparse.ArgumentParser(description="AI-Augmented SQL Query Validator & Formatter")
    parser.add_argument("--demo", action="store_true", help="Run end-to-end pipeline demonstration")
    parser.add_argument("--matrix", "--test", action="store_true", help="Run the 7 report evaluation matrix cases")
    parser.add_argument("--query", "--sql", type=str, help="Process a direct SQL query")
    parser.add_argument("--nl", type=str, help="Translate and validate a Natural Language question")
    parser.add_argument("--auto-correct", action="store_true", help="Enable AST-based fuzzy auto-correction")
    parser.add_argument("--no-ai", action="store_true", help="Disable all external AI edge components")

    args = parser.parse_args()

    if args.demo:
        run_demo()
    elif args.matrix:
        run_validation_matrix()
    elif args.query:
        pipeline = CompilerPipeline(auto_correct=args.auto_correct, enable_ai=not args.no_ai)
        pipeline.process_query(args.query, verbose=True)
    elif args.nl:
        pipeline = CompilerPipeline(auto_correct=args.auto_correct, enable_ai=not args.no_ai)
        candidate = pipeline.nl_translator.translate(args.nl)
        print(f"Candidate SQL: {candidate}")
        pipeline.process_query(candidate, verbose=True)
    else:
        run_repl()


if __name__ == "__main__":
    main()
