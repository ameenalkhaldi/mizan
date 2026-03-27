#!/usr/bin/env python3
"""
Phase 2: Score model i'rab responses against Shamela reference.

For each model response, extracts grammatical items from the reference i'rab
(word + role pairs) and checks whether the model's output assigns the same
role to each word. Scoring uses proximity-based keyword matching — the same
word-by-word methodology as the blind test suite (tests/README.md).

Usage:
    python tests/benchmark_score.py                          # score all
    python tests/benchmark_score.py --model gpt-4o-mini      # one model
    python tests/benchmark_score.py --model gpt-4o --verse 1 # one response
    python tests/benchmark_score.py --show-errors            # print errors
    python tests/benchmark_score.py --show-items             # show extracted items
"""

import json
import re
import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "tests" / "benchmark_results" / "raw"
SCORES_DIR = PROJECT_ROOT / "tests" / "benchmark_results" / "scores"

# ---------------------------------------------------------------------------
# Role keywords — ordered from most specific to least specific.
# When extracting a role from analysis text, the first match wins.
# ---------------------------------------------------------------------------
KNOWN_ROLES = [
    # Compound / specific (must come before their substrings)
    "نائب فاعل", "نائب الفاعل",
    "مفعول به", "مفعول مطلق", "مفعول لأجله", "مفعول له",
    "مفعول فيه", "مفعول معه",
    "جار ومجرور", "جارّ ومجرور",
    "اسم إشارة", "اسم موصول",
    "عطف بيان",
    "اسم كان", "اسم يكن", "اسم يكون",
    "خبر كان", "خبر يكن", "خبر يكون",
    "اسم إن", "اسم إنّ", "اسمها",
    "خبر إن", "خبر إنّ", "خبرها",
    "اسم لا",
    "خبر لا",
    "نافية للجنس",
    "حرف توكيد ونصب",
    "فعل ماض", "فعل ماضٍ",
    "فعل مضارع",
    "فعل أمر",
    "ظرف زمان", "ظرف مكان",
    "مضاف إليه",
    "مقول القول",
    "ضمير فصل",
    "أداة استثناء", "أداة حصر",
    "حرف جر", "حرف نصب", "حرف جزم", "حرف عطف",
    "حرف شرط", "حرف مصدري",
    "لام التعليل", "لام القسم",
    # Single-word roles
    "مبتدأ",
    "خبر",
    "فاعل",
    "حال",
    "تمييز",
    "بدل",
    "نعت", "صفة",
    "معطوف",
    "مستثنى",
    "منادى",
    "ظرف",
    # Particle function types
    "عاطفة",
    "استئنافية",
    "رابطة",
    "نافية",
    "ناهية",
    "شرطية",
    "مصدرية",
    "تعليلية",
    "حرف",
    "أداة",
    "ضمير",
]

# Canonical grouping: map synonyms to canonical name
SYNONYMS = {
    "صفة": "نعت",
    "نائب الفاعل": "نائب فاعل",
    "جارّ ومجرور": "جار ومجرور",
    "فعل ماضٍ": "فعل ماض",
    "مفعول له": "مفعول لأجله",
    "اسم يكن": "اسم كان",
    "اسم يكون": "اسم كان",
    "خبر يكن": "خبر كان",
    "خبر يكون": "خبر كان",
    "اسم إنّ": "اسم إن",
    "خبر إنّ": "خبر إن",
}


def normalize(text: str) -> str:
    """Normalize Arabic text for matching: strip diacritics, unify letters."""
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)   # tashkeel
    text = re.sub(r'[إأآٱ]', 'ا', text)                 # hamza carriers
    text = text.replace('ى', 'ي')                         # alef maqsura
    text = text.replace('\u0640', '')                      # tatweel
    return text


def canonical(role: str) -> str:
    """Map a role keyword to its canonical form."""
    return SYNONYMS.get(role, role)


# Reverse map: canonical_role -> set of all surface forms that mean the same.
# Used during scoring so we check "نعت" AND "صفة" when the item expects "نعت".
ROLE_FORMS: dict[str, set[str]] = {}
for _role in KNOWN_ROLES:
    _c = canonical(_role)
    ROLE_FORMS.setdefault(_c, set()).add(_role)
    ROLE_FORMS[_c].add(_c)


# ---------------------------------------------------------------------------
# Reference parser — extract scored items from Shamela i'rab text
# ---------------------------------------------------------------------------

def find_first_role(text: str) -> str | None:
    """Return the first known grammatical role keyword found in *text*."""
    earliest_pos = len(text) + 1
    earliest_role = None
    for role in KNOWN_ROLES:
        pos = text.find(role)
        if pos != -1 and pos < earliest_pos:
            earliest_pos = pos
            earliest_role = role
    return earliest_role


def extract_alternatives(analysis: str) -> list[str]:
    """Extract alternative roles from [أو ...] brackets in the analysis."""
    alts = []
    for m in re.finditer(r'\[أو\s+([^\]]+)\]', analysis):
        alt_text = m.group(1)
        for part in re.split(r'أو\s+|[,،]\s*', alt_text):
            role = find_first_role(part.strip())
            if role:
                alts.append(canonical(role))
    return alts


def _extract_inline_items(text: str, already_seen: set[str],
                          verse_text: str = "") -> list[dict]:
    """
    Extract additional word-role pairs from flowing #2163-style text.

    Looks for the pattern: و + Arabic_word + whitespace + known_role_keyword.
    This captures inline items like "وإله اسمها" or "والحي خبر ثان".
    If *verse_text* is provided, only words that appear in the verse are kept
    (filters out meta-references like الهاء, الكاف, etc.).
    """
    # Build regex: "و" + Arabic word (2-15 chars) + space + known role
    # Sort roles longest-first so regex matches the most specific role.
    roles_by_len = sorted(KNOWN_ROLES, key=len, reverse=True)
    role_alt = "|".join(re.escape(r) for r in roles_by_len)
    pattern = re.compile(
        r'و([\u0600-\u06FF]{2,15})\s+(' + role_alt + r')',
    )

    # Words to skip (grammatical meta-terms, not actual verse words)
    SKIP = {
        "الجملة", "جملة", "محذوف", "مقدر", "تقديره", "مستتر",
        "الاسمية", "الفعلية", "المصدر", "المعنى", "الحرف",
        "بمحذوف", "والجملة", "المقدرة", "المحذوف",
    }

    verse_norm = normalize(verse_text) if verse_text else ""

    items = []
    for m in pattern.finditer(text):
        word = m.group(1)
        role = m.group(2)

        word_n = normalize(word)
        if word_n in already_seen:
            continue
        if word in SKIP or word_n in SKIP:
            continue
        # Filter: word must appear in the actual verse text
        if verse_norm and word_n not in verse_norm:
            continue

        already_seen.add(word_n)
        items.append({
            "word": word,
            "role": canonical(role),
            "alternatives": [],
        })

    return items


def extract_items(reference_text: str, verse_text: str = "") -> list[dict]:
    """
    Parse a reference i'rab text and extract (word, role, alternatives) items.

    Handles both ﴿word﴾ (Shamela #86 style) and (word) (Shamela #2163/#22916).
    When ﴿﴾ markers are present, only those are used as top-level items
    (the () inside are sub-markers within the analysis text).
    For ()-only references, also extracts inline "و[word] [role]" items from
    the flowing text between markers.
    *verse_text* is used to filter inline items to actual verse words.
    """
    if '﴿' in reference_text:
        # Shamela #86 style (and some #22916): ﴿﴾ are top-level word markers.
        # () inside are sub-analyses, not separate scored items.
        marker_re = re.compile(r'﴿([^﴾]+)﴾')
    else:
        # Shamela #2163/#22916 ()-only style
        marker_re = re.compile(r'\(([^)]+)\)')

    matches = list(marker_re.finditer(reference_text))

    items = []
    seen_words = set()  # normalized words already extracted

    for i, m in enumerate(matches):
        word = m.group(1).strip()

        # Analysis text: from end of this marker to start of next (or end)
        analysis_start = m.end()
        analysis_end = matches[i + 1].start() if i + 1 < len(matches) else len(reference_text)
        analysis = reference_text[analysis_start:analysis_end].strip()
        # Strip leading colon/space
        analysis = re.sub(r'^[:\s]+', '', analysis)

        if not word or not analysis:
            continue

        role = find_first_role(analysis)
        if not role:
            continue

        alts = extract_alternatives(analysis)

        items.append({
            "word": word,
            "role": canonical(role),
            "alternatives": alts,
        })
        seen_words.add(normalize(word))

    # For ()-only references, also extract inline items from flowing text
    if '﴿' not in reference_text:
        inline = _extract_inline_items(reference_text, seen_words, verse_text)
        items.extend(inline)

    return items


# ---------------------------------------------------------------------------
# Scorer — check model output against reference items
# ---------------------------------------------------------------------------

def find_word_positions(word: str, text_norm: str) -> list[int]:
    """Find all start positions of *word* (normalized) in *text_norm*."""
    w = normalize(word)
    positions = []
    idx = 0
    while True:
        pos = text_norm.find(w, idx)
        if pos == -1:
            break
        positions.append(pos)
        idx = pos + 1
    return positions


def role_present_near(positions: list[int], role: str, text_norm: str,
                      window: int = 300) -> bool:
    """Check if *role* or any of its synonym forms appears within *window* chars."""
    # Get all surface forms for this canonical role (e.g. نعت → {نعت, صفة})
    forms = ROLE_FORMS.get(role, {role})
    forms_n = [normalize(f) for f in forms]
    for pos in positions:
        start = max(0, pos - 30)
        end = min(len(text_norm), pos + window)
        chunk = text_norm[start:end]
        for fn in forms_n:
            if fn in chunk:
                return True
    return False


def score_verse(items: list[dict], model_response: str) -> dict:
    """Score one model response against its reference items."""
    if not model_response or len(model_response) < 30:
        return {
            "items_total": len(items),
            "items_correct": 0,
            "accuracy_pct": 0.0,
            "errors": [{"word": it["word"], "expected": it["role"],
                         "found": "no response"} for it in items],
        }

    resp_norm = normalize(model_response)
    correct = 0
    errors = []

    for item in items:
        word = item["word"]
        expected = item["role"]
        alternatives = item.get("alternatives", [])

        # All acceptable roles
        acceptable = [expected] + alternatives

        # Find word in model response
        positions = find_word_positions(word, resp_norm)
        if not positions:
            # Try without ال prefix
            bare = re.sub(r'^ال', '', normalize(word))
            if len(bare) >= 2:
                positions = find_word_positions(bare, resp_norm)

        matched = False
        if positions:
            for role in acceptable:
                if role_present_near(positions, role, resp_norm):
                    matched = True
                    break

        if matched:
            correct += 1
        else:
            # Try to identify what the model actually said
            found_role = "not found"
            if positions:
                for pos in positions:
                    chunk = model_response[max(0, pos - 30):min(len(model_response), pos + 300)]
                    r = find_first_role(chunk)
                    if r:
                        found_role = canonical(r)
                        break

            errors.append({
                "word": word,
                "expected": expected,
                "found": found_role,
            })

    total = len(items)
    return {
        "items_total": total,
        "items_correct": correct,
        "accuracy_pct": round(correct / total * 100, 1) if total > 0 else 0.0,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_verses(path: str | None = None) -> list[dict]:
    if path is None:
        path = PROJECT_ROOT / "data" / "irab_training_30.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_model_response(model_id: str, verse_id: int) -> str | None:
    """Load model's raw response text for a given verse."""
    slug = model_id.replace("/", "_")
    fpath = RAW_DIR / slug / f"verse_{verse_id:02d}.json"
    if not fpath.exists():
        return None
    try:
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except (json.JSONDecodeError, KeyError, IndexError):
        return None


def load_model_usage(model_id: str, verse_id: int) -> dict:
    """Load token usage from raw response."""
    slug = model_id.replace("/", "_")
    fpath = RAW_DIR / slug / f"verse_{verse_id:02d}.json"
    if not fpath.exists():
        return {}
    try:
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("usage", {})
    except (json.JSONDecodeError, KeyError):
        return {}


def save_score(model_id: str, verse_id: int, score: dict) -> Path:
    slug = model_id.replace("/", "_")
    dir_path = SCORES_DIR / slug
    dir_path.mkdir(parents=True, exist_ok=True)
    fpath = dir_path / f"verse_{verse_id:02d}.json"
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(score, f, ensure_ascii=False, indent=2)
    return fpath


def available_models() -> list[str]:
    """List model IDs that have raw results."""
    if not RAW_DIR.exists():
        return []
    return sorted(
        d.name.replace("_", "/", 1)
        for d in RAW_DIR.iterdir() if d.is_dir()
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Score benchmark i'rab responses")
    parser.add_argument("--model", type=str,
                        help="Score only this model (partial match)")
    parser.add_argument("--verse", type=int,
                        help="Score only this verse ID")
    parser.add_argument("--show-errors", action="store_true",
                        help="Print error details per verse")
    parser.add_argument("--show-items", action="store_true",
                        help="Print extracted reference items")
    parser.add_argument("--data", type=str, default=None,
                        help="Path to test data JSON")
    args = parser.parse_args()

    verses = load_verses(args.data)

    # Filter verses
    if args.verse:
        verses = [v for v in verses if v["id"] == args.verse]
        if not verses:
            print(f"No verse with ID {args.verse}.")
            sys.exit(1)

    # Pre-extract reference items for each verse
    verse_items = {}
    for v in verses:
        items = extract_items(v["correct_irab"], v.get("verse", ""))
        verse_items[v["id"]] = items

    if args.show_items:
        for v in verses:
            items = verse_items[v["id"]]
            print(f"\n=== Verse {v['id']} — {v['reference']}  ({len(items)} items) ===")
            for it in items:
                alts = f"  alts: {it['alternatives']}" if it['alternatives'] else ""
                print(f"  {it['word']:20s} -> {it['role']}{alts}")
        total = sum(len(verse_items[v["id"]]) for v in verses)
        print(f"\nTotal extracted items: {total}")
        return

    # Determine which models to score
    all_models = available_models()
    if not all_models:
        print("No raw results found. Run benchmark_models.py first.")
        sys.exit(1)

    models_to_score = all_models
    if args.model:
        q = args.model.lower()
        models_to_score = [m for m in all_models if q in m.lower()]
        if not models_to_score:
            print(f"No model matching '{args.model}'. Available:")
            for m in all_models:
                print(f"  {m}")
            sys.exit(1)

    for model_id in models_to_score:
        print(f"\n{'='*60}")
        print(f"Scoring: {model_id}")
        print(f"{'='*60}")

        model_correct = 0
        model_total = 0
        model_errors = []
        scored_count = 0

        for v in verses:
            vid = v["id"]
            items = verse_items[vid]
            if not items:
                continue

            response = load_model_response(model_id, vid)
            if response is None:
                print(f"  [{vid:2d}] {v['reference']:20s}  -- no response file")
                continue

            result = score_verse(items, response)
            result["model"] = model_id
            result["verse_id"] = vid
            result["verse_ref"] = v["reference"]
            save_score(model_id, vid, result)

            pct = result["accuracy_pct"]
            nerr = len(result["errors"])
            marker = " *" if pct == 100.0 else ""
            print(f"  [{vid:2d}] {v['reference']:20s}  "
                  f"{result['items_correct']}/{result['items_total']}  "
                  f"{pct:5.1f}%{marker}")

            if args.show_errors and result["errors"]:
                for err in result["errors"]:
                    print(f"        x {err['word']}  "
                          f"expected={err['expected']}  found={err['found']}")

            model_correct += result["items_correct"]
            model_total += result["items_total"]
            model_errors.extend(result["errors"])
            scored_count += 1

        if model_total > 0:
            overall = round(model_correct / model_total * 100, 1)
            print(f"\n  Overall: {model_correct}/{model_total}  {overall}%"
                  f"  ({scored_count} verses scored, {len(model_errors)} errors)")

    print(f"\nScores saved to {SCORES_DIR}")


if __name__ == "__main__":
    main()
