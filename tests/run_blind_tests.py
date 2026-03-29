#!/usr/bin/env python3
"""
Blind I'rab Test Runner

Loads verses from data/irab_training_30.json, sends each to the i'rab skill
(via subagent or MCP tool), then compares the output against the reference
answers from published إعراب books.

Usage:
    python tests/run_blind_tests.py                  # Run all 30 tests
    python tests/run_blind_tests.py --verse 1        # Run a single test
    python tests/run_blind_tests.py --range 1-10     # Run a range
    python tests/run_blind_tests.py --pattern كان    # Run verses matching a pattern

The test data is in data/irab_training_30.json with this structure:
{
    "id": 1,
    "verse": "الآية بالتشكيل",
    "reference": "البقرة: 2",
    "source_book": "86",
    "patterns_tested": ["اسمية", "لا النافية للجنس", ...],
    "correct_irab": "الإعراب الكامل من الكتاب المرجعي"
}

Scoring is manual — the script outputs the verse, the reference, and the
agent's answer side by side for human comparison. Automated scoring would
require NLP parsing of the Arabic إعراب text.
"""

import json
import argparse


def load_tests(path: str = "data/irab_training_30.json") -> list[dict]:
    """Load test verses from JSON."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def print_test(test: dict, show_answer: bool = False) -> None:
    """Print a single test case."""
    print(f"\n{'='*70}")
    print(f"TEST {test['id']} — {test['reference']}")
    print(f"Source book: Shamela #{test['source_book']}")
    print(f"Patterns: {', '.join(test['patterns_tested'])}")
    print(f"{'='*70}")
    print(f"\nالآية: {test['verse']}")
    if show_answer:
        print("\n--- الإعراب المرجعي ---")
        print(test['correct_irab'])
    print()


def print_for_blind_test(test: dict) -> None:
    """Print verse only (no reference answer) for blind testing."""
    print(f"\n{'='*70}")
    print(f"TEST {test['id']} — {test['reference']}")
    print(f"{'='*70}")
    print(f"\nأعرب: {test['verse']}")
    print()


def print_for_comparison(test: dict, agent_answer: str) -> None:
    """Print reference and agent answers side by side for scoring."""
    print(f"\n{'='*70}")
    print(f"SCORING — TEST {test['id']} — {test['reference']}")
    print(f"Patterns: {', '.join(test['patterns_tested'])}")
    print(f"{'='*70}")
    print(f"\nالآية: {test['verse']}")
    print("\n--- الإعراب المرجعي (من الكتاب) ---")
    print(test['correct_irab'])
    print("\n--- إعراب المحلل (الذكاء الاصطناعي) ---")
    print(agent_answer)
    print("\n--- التقييم ---")
    print("[ ] مطابق تماماً")
    print("[ ] صحيح مع اختلاف في الصياغة")
    print("[ ] خطأ في: _____________")
    print()


def export_blind_prompts(tests: list[dict], output_path: str = "tests/blind_prompts.txt") -> None:
    """Export verse prompts for blind testing (no answers)."""
    with open(output_path, "w", encoding="utf-8") as f:
        for test in tests:
            f.write(f"=== TEST {test['id']} — {test['reference']} ===\n")
            f.write("أعرب الآية التالية إعراباً تفصيلياً كاملاً:\n")
            f.write(f"{test['verse']}\n\n")
    print(f"Exported {len(tests)} blind prompts to {output_path}")


def export_answer_key(tests: list[dict], output_path: str = "tests/answer_key.txt") -> None:
    """Export reference answers for scoring."""
    with open(output_path, "w", encoding="utf-8") as f:
        for test in tests:
            f.write(f"=== TEST {test['id']} — {test['reference']} ===\n")
            f.write(f"Patterns: {', '.join(test['patterns_tested'])}\n")
            f.write(f"Source: Shamela #{test['source_book']}\n\n")
            f.write(f"الآية: {test['verse']}\n\n")
            f.write(f"الإعراب المرجعي:\n{test['correct_irab']}\n\n")
            f.write(f"{'─'*60}\n\n")
    print(f"Exported {len(tests)} answer keys to {output_path}")


def summary_stats(tests: list[dict]) -> None:
    """Print summary statistics about the test set."""
    books = {}
    patterns = {}
    for t in tests:
        books[t['source_book']] = books.get(t['source_book'], 0) + 1
        for p in t['patterns_tested']:
            patterns[p] = patterns.get(p, 0) + 1

    print(f"\n{'='*50}")
    print("TEST SET SUMMARY")
    print(f"{'='*50}")
    print(f"Total verses: {len(tests)}")
    print("\nBy source book:")
    for book, count in sorted(books.items()):
        print(f"  Shamela #{book}: {count} verses")
    print(f"\nGrammar patterns ({len(patterns)} unique):")
    for pattern, count in sorted(patterns.items(), key=lambda x: -x[1]):
        print(f"  {pattern}: {count} verses")


def main():
    parser = argparse.ArgumentParser(description="Blind I'rab Test Runner")
    parser.add_argument("--verse", type=int, help="Run a single verse by ID (1-30)")
    parser.add_argument("--range", type=str, help="Run a range of verses (e.g., 1-10)")
    parser.add_argument("--pattern", type=str, help="Run verses matching a grammar pattern")
    parser.add_argument("--show-answers", action="store_true", help="Show reference answers")
    parser.add_argument("--blind", action="store_true", help="Print verses only (no answers)")
    parser.add_argument("--export-prompts", action="store_true", help="Export blind test prompts to file")
    parser.add_argument("--export-keys", action="store_true", help="Export answer keys to file")
    parser.add_argument("--stats", action="store_true", help="Print test set statistics")
    parser.add_argument("--data", type=str, default="data/irab_training_30.json", help="Path to test data JSON")
    args = parser.parse_args()

    tests = load_tests(args.data)

    if args.stats:
        summary_stats(tests)
        return

    if args.export_prompts:
        export_blind_prompts(tests)
        return

    if args.export_keys:
        export_answer_key(tests)
        return

    # Filter tests
    selected = tests
    if args.verse:
        selected = [t for t in tests if t['id'] == args.verse]
    elif args.range:
        start, end = map(int, args.range.split('-'))
        selected = [t for t in tests if start <= t['id'] <= end]
    elif args.pattern:
        selected = [t for t in tests if any(args.pattern in p for p in t['patterns_tested'])]

    if not selected:
        print("No matching tests found.")
        return

    print(f"Running {len(selected)} test(s)...\n")

    for test in selected:
        if args.blind:
            print_for_blind_test(test)
        else:
            print_test(test, show_answer=args.show_answers)


if __name__ == "__main__":
    main()
