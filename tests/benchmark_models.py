#!/usr/bin/env python3
"""
Phase 1: Call LLM models via OpenRouter and save raw i'rab responses.

Sends each of 30 Quranic verses to 10 models with an identical Arabic i'rab
prompt. Responses are saved as individual JSON files for scoring in Phase 2.

Usage:
    python tests/benchmark_models.py --dry-run
    python tests/benchmark_models.py --model gpt-4o-mini --verse 1
    python tests/benchmark_models.py                      # all models x all verses
    python tests/benchmark_models.py --max-cost 10
"""

import json
import os
import sys
import time
import argparse
import requests
from pathlib import Path

MODELS = [
    {"id": "anthropic/claude-sonnet-4", "name": "Claude Sonnet 4", "tier": "Frontier"},
    {"id": "openai/gpt-4o", "name": "GPT-4o", "tier": "Frontier"},
    {"id": "google/gemini-2.5-pro", "name": "Gemini 2.5 Pro", "tier": "Frontier", "max_tokens": 16384},
    {"id": "anthropic/claude-haiku-4.5", "name": "Claude Haiku 4.5", "tier": "Mid-tier"},
    {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "tier": "Mid-tier"},
    {"id": "google/gemini-2.0-flash-001", "name": "Gemini 2.0 Flash", "tier": "Mid-tier"},
    {"id": "meta-llama/llama-4-maverick", "name": "Llama 4 Maverick", "tier": "Open-source"},
    {"id": "qwen/qwen3-235b-a22b", "name": "Qwen 3 235B", "tier": "Open-source"},
    {"id": "deepseek/deepseek-chat-v3-0324", "name": "DeepSeek V3", "tier": "Open-source"},
    {"id": "cohere/command-a", "name": "Command A", "tier": "Open-source"},
]

SYSTEM_PROMPT = (
    "أنت عالم نحو عربي متخصص في إعراب القرآن الكريم. أعرب الآية إعراباً تفصيلياً كاملاً.\n"
    "لكل كلمة بيّن: نوعها، وظيفتها النحوية، وعلامة إعرابها أو بنائها، وعاملها.\n"
    "بيّن الجار والمجرور بماذا يتعلق. بيّن الجمل ومحلها الإعرابي.\n"
    "أجب بالعربية فقط."
)

API_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_TOKENS = 2048
DELAY_BETWEEN_CALLS = 1.5  # seconds

# Project root (one level up from tests/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "tests" / "benchmark_results" / "raw"


def model_slug(model_id: str) -> str:
    """Convert model ID to filesystem-safe slug."""
    return model_id.replace("/", "_")


def load_verses(path: str | None = None) -> list[dict]:
    """Load test verses from JSON."""
    if path is None:
        path = PROJECT_ROOT / "data" / "irab_training_30.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def call_openrouter(model_id: str, verse_text: str, api_key: str,
                     max_tokens: int = MAX_TOKENS) -> dict:
    """Call OpenRouter API. Retries on 429/503 with exponential backoff."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"أعرب: {verse_text}"},
        ],
        "max_tokens": max_tokens,
        "temperature": 0,
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = requests.post(API_URL, headers=headers, json=payload, timeout=120)
            if resp.status_code in (429, 503):
                wait = (2 ** attempt) * 5
                print(f"  Rate limited ({resp.status_code}), waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                print(f"  Timeout, retrying ({attempt + 1}/{max_retries})...")
                time.sleep(5)
                continue
            raise

    raise RuntimeError(f"Failed after {max_retries} retries for {model_id}")


def save_result(model_id: str, verse_id: int, result: dict) -> Path:
    """Save raw API response to JSON file."""
    slug = model_slug(model_id)
    dir_path = RAW_DIR / slug
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"verse_{verse_id:02d}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return file_path


def result_exists(model_id: str, verse_id: int) -> bool:
    """Check if a successful result already exists (for resumability)."""
    slug = model_slug(model_id)
    file_path = RAW_DIR / slug / f"verse_{verse_id:02d}.json"
    if not file_path.exists():
        return False
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        # Must have choices with content — not an error stub
        choices = data.get("choices", [])
        return len(choices) > 0 and choices[0].get("message", {}).get("content", "")
    except (json.JSONDecodeError, KeyError):
        return False


def get_model_registry() -> dict:
    """Return {model_id: model_info} for quick lookup."""
    return {m["id"]: m for m in MODELS}


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark LLM i'rab via OpenRouter"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would run without calling APIs")
    parser.add_argument("--model", type=str,
                        help="Run only this model (partial match on ID or name)")
    parser.add_argument("--verse", type=int,
                        help="Run only this verse ID (1-30)")
    parser.add_argument("--max-cost", type=float, default=15.0,
                        help="Stop if estimated cost exceeds this (default $15)")
    parser.add_argument("--data", type=str, default=None,
                        help="Path to test data JSON")
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key and not args.dry_run:
        print("Error: OPENROUTER_API_KEY environment variable not set.")
        sys.exit(1)

    verses = load_verses(args.data)

    # Filter models
    models = MODELS
    if args.model:
        q = args.model.lower()
        models = [m for m in MODELS if q in m["id"].lower() or q in m["name"].lower()]
        if not models:
            print(f"No model matching '{args.model}'. Available:")
            for m in MODELS:
                print(f"  {m['id']}  ({m['name']})")
            sys.exit(1)

    # Filter verses
    if args.verse:
        verses = [v for v in verses if v["id"] == args.verse]
        if not verses:
            print(f"No verse with ID {args.verse}.")
            sys.exit(1)

    # Count work
    total_calls = 0
    skip_count = 0
    for model in models:
        for verse in verses:
            if result_exists(model["id"], verse["id"]):
                skip_count += 1
            else:
                total_calls += 1

    print(f"Models: {len(models)}, Verses: {len(verses)}")
    print(f"API calls needed: {total_calls}  (skipping {skip_count} existing)")
    print(f"Results dir: {RAW_DIR}")

    if args.dry_run:
        print("\n--- DRY RUN ---")
        for model in models:
            pending = [v for v in verses if not result_exists(model["id"], v["id"])]
            done = len(verses) - len(pending)
            print(f"\n{model['name']} [{model['tier']}]  {done}/{len(verses)} done")
            if pending:
                ids = ", ".join(str(v["id"]) for v in pending[:5])
                extra = f" +{len(pending)-5} more" if len(pending) > 5 else ""
                print(f"  Pending: {ids}{extra}")
        return

    if total_calls == 0:
        print("\nAll results already exist. Nothing to do.")
        return

    total_tokens = 0
    calls_made = 0

    for model in models:
        print(f"\n{'='*60}")
        print(f"{model['name']}  ({model['id']})")
        print(f"{'='*60}")

        for verse in verses:
            if result_exists(model["id"], verse["id"]):
                continue

            print(f"  [{verse['id']:2d}/30] {verse['reference']}...", end=" ", flush=True)

            try:
                mtokens = model.get("max_tokens", MAX_TOKENS)
                response = call_openrouter(model["id"], verse["verse"], api_key, mtokens)
                save_result(model["id"], verse["id"], response)

                content = (response.get("choices", [{}])[0]
                           .get("message", {}).get("content", ""))
                preview = content[:60].replace("\n", " ")
                if len(content) > 60:
                    preview += "..."

                usage = response.get("usage", {})
                tokens = usage.get("total_tokens", 0)
                total_tokens += tokens

                print(f"OK  {tokens}tok  {preview}")
                calls_made += 1

            except Exception as e:
                print(f"ERROR: {e}")
                save_result(model["id"], verse["id"], {
                    "error": str(e),
                    "model": model["id"],
                    "verse_id": verse["id"],
                })

            if calls_made < total_calls:
                time.sleep(DELAY_BETWEEN_CALLS)

    print(f"\n{'='*60}")
    print(f"Done. {calls_made} calls, {total_tokens:,} total tokens.")
    print(f"Results: {RAW_DIR}")


if __name__ == "__main__":
    main()
