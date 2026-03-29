#!/usr/bin/env python3
"""
Phase 3: Aggregate benchmark scores into a comparison table.

Reads per-verse score files produced by benchmark_score.py, computes summary
statistics per model, and generates a markdown comparison table.

Usage:
    python tests/benchmark_report.py              # print table to stdout
    python tests/benchmark_report.py --save       # also write comparison.md
    python tests/benchmark_report.py --json       # output summary.json
"""

import json
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCORES_DIR = PROJECT_ROOT / "tests" / "benchmark_results" / "scores"
RAW_DIR = PROJECT_ROOT / "tests" / "benchmark_results" / "raw"
OUT_DIR = PROJECT_ROOT / "tests" / "benchmark_results"

# Our engine's known baseline from the blind test
ENGINE_BASELINE = {
    "name": "I'rab Engine",
    "tier": "Ours",
    "accuracy": 97.6,
    "perfect_verses": 20,
    "total_verses": 30,
    "high_errors": 0,
    "total_items": 434,
    "total_correct": 423.5,
}

# Model display info (name + tier), keyed by slug prefix
MODEL_INFO = {
    "anthropic_claude-sonnet-4": ("Claude Sonnet 4", "Frontier"),
    "openai_gpt-4o": ("GPT-4o", "Frontier"),
    "google_gemini-2.5-pro": ("Gemini 2.5 Pro", "Frontier"),
    "anthropic_claude-haiku-4": ("Claude Haiku 4.5", "Mid-tier"),
    "anthropic_claude-haiku-4.5": ("Claude Haiku 4.5", "Mid-tier"),
    "openai_gpt-4o-mini": ("GPT-4o Mini", "Mid-tier"),
    "google_gemini-2.0-flash": ("Gemini 2.0 Flash", "Mid-tier"),
    "meta-llama_llama-4": ("Llama 4 Maverick", "Open-source"),
    "qwen_qwen-3": ("Qwen 3 235B", "Open-source"),
    "qwen_qwen3": ("Qwen 3 235B", "Open-source"),
    "deepseek_deepseek-chat": ("DeepSeek V3", "Open-source"),
    "cohere_command-a": ("Command A", "Open-source"),
}


def model_display(slug: str) -> tuple[str, str]:
    """Return (display_name, tier) for a model slug directory."""
    # Try longest prefix first to avoid "gpt-4o" matching "gpt-4o-mini"
    for prefix in sorted(MODEL_INFO, key=len, reverse=True):
        if slug.startswith(prefix):
            return MODEL_INFO[prefix]
    # Fallback: use slug
    return slug.replace("_", "/", 1), "Unknown"


def load_scores_for_model(slug: str) -> list[dict]:
    """Load all per-verse score files for a model."""
    model_dir = SCORES_DIR / slug
    if not model_dir.exists():
        return []
    scores = []
    for fpath in sorted(model_dir.glob("verse_*.json")):
        with open(fpath, encoding="utf-8") as f:
            scores.append(json.load(f))
    return scores


def total_tokens_for_model(slug: str) -> int:
    """Sum up total tokens from raw response files."""
    model_dir = RAW_DIR / slug
    if not model_dir.exists():
        return 0
    total = 0
    for fpath in model_dir.glob("verse_*.json"):
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            total += data.get("usage", {}).get("total_tokens", 0)
        except (json.JSONDecodeError, KeyError):
            pass
    return total


def aggregate(scores: list[dict]) -> dict:
    """Compute summary statistics from per-verse scores."""
    if not scores:
        return {"accuracy": 0, "perfect_verses": 0, "total_verses": 0,
                "total_items": 0, "total_correct": 0, "total_errors": 0}

    total_items = sum(s["items_total"] for s in scores)
    total_correct = sum(s["items_correct"] for s in scores)
    perfect = sum(1 for s in scores if s["accuracy_pct"] == 100.0)
    total_errors = sum(len(s.get("errors", [])) for s in scores)
    accuracy = round(total_correct / total_items * 100, 1) if total_items > 0 else 0

    return {
        "accuracy": accuracy,
        "perfect_verses": perfect,
        "total_verses": len(scores),
        "total_items": total_items,
        "total_correct": total_correct,
        "total_errors": total_errors,
    }


def generate_table(results: list[dict]) -> str:
    """Generate a markdown comparison table."""
    lines = []
    lines.append("| # | Model | Tier | Accuracy | 100% Verses | Items | Tokens |")
    lines.append("|---|-------|------|----------|-------------|-------|--------|")

    for i, r in enumerate(results, 1):
        name = r["name"]
        tier = r["tier"]
        acc = f'{r["accuracy"]:.1f}%'
        perfect = f'{r["perfect_verses"]}/{r["total_verses"]}'
        items = f'{r.get("total_correct", "?")}/{r.get("total_items", "?")}'
        tokens = f'{r.get("total_tokens", 0):,}' if r.get("total_tokens") else "\u2014"

        # Bold our engine row
        if tier == "Ours":
            lines.append(
                f"| {i} | **{name}** | **{tier}** | **{acc}** | "
                f"**{perfect}** | **{items}** | **{tokens}** |"
            )
        else:
            lines.append(
                f"| {i} | {name} | {tier} | {acc} | {perfect} | {items} | {tokens} |"
            )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate benchmark comparison table")
    parser.add_argument("--save", action="store_true",
                        help="Write comparison.md and summary.json")
    parser.add_argument("--json", action="store_true",
                        help="Print summary as JSON")
    args = parser.parse_args()

    if not SCORES_DIR.exists():
        print("No scores found. Run benchmark_score.py first.")
        return

    # Collect results per model
    results = []

    for model_dir in sorted(SCORES_DIR.iterdir()):
        if not model_dir.is_dir():
            continue
        slug = model_dir.name
        scores = load_scores_for_model(slug)
        if not scores:
            continue

        name, tier = model_display(slug)
        stats = aggregate(scores)
        tokens = total_tokens_for_model(slug)

        results.append({
            "slug": slug,
            "name": name,
            "tier": tier,
            "total_tokens": tokens,
            **stats,
        })

    # Sort by accuracy descending
    results.sort(key=lambda r: r["accuracy"], reverse=True)

    # Insert engine baseline at the top
    engine = {
        **ENGINE_BASELINE,
        "slug": "irab-engine",
        "total_tokens": 0,
        "total_errors": 0,
    }
    results.insert(0, engine)

    # Generate table
    table = generate_table(results)
    print("\n## I'rab Benchmark — LLM Comparison\n")
    print("30 Quranic verses scored against published Shamela references.\n")
    print(table)
    print()

    # Print tier averages
    tier_data = {}
    for r in results:
        if r["tier"] == "Ours":
            continue
        tier_data.setdefault(r["tier"], []).append(r["accuracy"])

    if tier_data:
        print("\n### Tier averages\n")
        for tier in ["Frontier", "Mid-tier", "Open-source"]:
            if tier in tier_data:
                vals = tier_data[tier]
                avg = sum(vals) / len(vals)
                print(f"- **{tier}**: {avg:.1f}% ({len(vals)} models)")

    if args.json or args.save:
        summary = {
            "engine_baseline": ENGINE_BASELINE,
            "models": [r for r in results if r["tier"] != "Ours"],
        }

        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))

        if args.save:
            OUT_DIR.mkdir(parents=True, exist_ok=True)

            # Write markdown
            md_path = OUT_DIR / "comparison.md"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write("# I'rab Benchmark — LLM Comparison\n\n")
                f.write("30 Quranic verses scored word-by-word against published\n")
                f.write("Shamela reference i'rab (3 books, 434 grammatical items).\n\n")
                f.write("Scoring: for each word in the reference, check if the model\n")
                f.write("assigns the same grammatical role within its analysis.\n\n")
                f.write(table)
                f.write("\n\n### Tier averages\n\n")
                for tier in ["Frontier", "Mid-tier", "Open-source"]:
                    if tier in tier_data:
                        vals = tier_data[tier]
                        avg = sum(vals) / len(vals)
                        f.write(f"- **{tier}**: {avg:.1f}% ({len(vals)} models)\n")
                f.write("\n---\n")
                f.write("*Generated by `tests/benchmark_report.py`*\n")
            print(f"\nSaved: {md_path}")

            # Write JSON
            json_path = OUT_DIR / "summary.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            print(f"Saved: {json_path}")


if __name__ == "__main__":
    main()
