#!/usr/bin/env python3
"""
Build a verb transitivity lookup table from Qabas lexicon data.

Scrapes Qabas lemma pages (sina.birzeit.edu/qabas) to extract
transitivity (متعدٍّ/لازم) for all Arabic verb entries.

Output: data/verb_transitivity.json

Data source: Qabas Lexicographic Database (CC-BY-ND-4.0)
  Jarrar, M. and Amayreh, H. (2024). Qabas: An Open-Source Arabic
  Lexicographic Database. LREC-COLING 2024.
  https://sina.birzeit.edu/qabas
"""

import json
import re
import sys
import time
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

# Qabas verb lemma IDs: multiples of 100, range ~2020000100 to ~2021050000
ID_START = 2020000100
ID_END = 2021050000
ID_STEP = 100

# Parallelism (be respectful to the server)
MAX_WORKERS = 5
BATCH_SIZE = 100
BATCH_DELAY = 1.0  # seconds between batches

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "verb_transitivity.json")
CHECKPOINT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", ".scrape_checkpoint.json")

FIELDS_RE = re.compile(
    r'"lemma":"(?P<lemma>[^"]*)"|'
    r'"lemma_ar_strip":"(?P<strip>[^"]*)"|'
    r'"pos_ar":"(?P<pos>[^"]*)"|'
    r'"transitivity_ar":"(?P<trans>[^"]*)"|'
    r'"root_ar":"(?P<root>[^"]*)"|'
    r'"augmentation_ar":"(?P<aug>[^"]*)"|'
    r'"voice_ar":"(?P<voice>[^"]*)"'
)


def fetch_lemma(lemma_id: int) -> dict | None:
    """Fetch a single Qabas lemma page and extract verb fields."""
    url = f"https://sina.birzeit.edu/qabas/lemma/{lemma_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "irab-transitivity-builder/0.1"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None

    fields = {}
    for m in FIELDS_RE.finditer(html):
        for key, val in m.groupdict().items():
            if val is not None:
                fields[key] = val

    if not fields.get("pos") or fields["pos"] != "فعل":
        return None  # Skip non-verbs

    return {
        "id": lemma_id,
        "lemma": fields.get("lemma", ""),
        "lemma_strip": fields.get("strip", ""),
        "root": fields.get("root", ""),
        "transitivity": fields.get("trans", ""),
        "augmentation": fields.get("aug", ""),
        "voice": fields.get("voice", ""),
    }


def load_checkpoint() -> dict:
    """Load progress checkpoint if it exists."""
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH) as f:
            return json.load(f)
    return {"last_id": ID_START - ID_STEP, "verbs": {}}


def save_checkpoint(last_id: int, verbs: dict):
    """Save progress checkpoint."""
    os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump({"last_id": last_id, "verbs": verbs}, f, ensure_ascii=False)


def main():
    checkpoint = load_checkpoint()
    verbs = checkpoint["verbs"]
    start_id = checkpoint["last_id"] + ID_STEP

    total_ids = (ID_END - start_id) // ID_STEP + 1
    if total_ids <= 0:
        print(f"Already complete. {len(verbs)} verbs collected.")
    else:
        print(f"Resuming from ID {start_id}. {len(verbs)} verbs so far. {total_ids} IDs remaining.")

    all_ids = list(range(start_id, ID_END + 1, ID_STEP))
    processed = 0
    batch_start = 0

    while batch_start < len(all_ids):
        batch_ids = all_ids[batch_start:batch_start + BATCH_SIZE]
        batch_start += BATCH_SIZE

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_lemma, lid): lid for lid in batch_ids}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    verbs[str(result["id"])] = result
                processed += 1

        last_id = batch_ids[-1]
        save_checkpoint(last_id, verbs)

        verb_count = len(verbs)
        pct = (processed / total_ids) * 100
        print(f"  [{pct:5.1f}%] ID {last_id}, {verb_count} verbs found", flush=True)

        if batch_start < len(all_ids):
            time.sleep(BATCH_DELAY)

    # Write final output
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    # Build the lookup: stripped lemma -> transitivity
    lookup = {}
    for v in verbs.values():
        key = v["lemma_strip"] or v["lemma"]
        # Some lemmas have "verb | verb + prep" format — take the base
        if "|" in key:
            key = key.split("|")[0].strip()
        # Remove diacritics for the lookup key
        key = re.sub(r"[\u064B-\u065F\u0670]", "", key)
        if key and v["transitivity"]:
            lookup[key] = {
                "transitivity": v["transitivity"],
                "root": v["root"],
            }

    output = {
        "_meta": {
            "source": "Qabas Lexicographic Database",
            "url": "https://sina.birzeit.edu/qabas",
            "license": "CC-BY-ND-4.0",
            "citation": "Jarrar, M. and Amayreh, H. (2024). Qabas: An Open-Source Arabic Lexicographic Database. LREC-COLING 2024.",
            "generated": time.strftime("%Y-%m-%d"),
            "total_verbs": len(lookup),
        },
        "verbs": lookup,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nDone! {len(lookup)} verbs written to {OUTPUT_PATH}")

    # Clean up checkpoint
    if os.path.exists(CHECKPOINT_PATH):
        os.remove(CHECKPOINT_PATH)


if __name__ == "__main__":
    main()
