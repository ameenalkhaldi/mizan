# I'rab Blind Test Suite

## What this tests

30 Quranic verses from 3 published إعراب reference books are sent to the i'rab skill **without access to the answers**. The skill's output is then scored word-by-word against the published references. This measures real-world accuracy of the complete i'rab pipeline.

## Test data

| File | Contents |
|------|----------|
| `../data/irab_training_30.json` | 30 verses with reference i'rab (source of truth) |
| `blind_prompts.txt` | The 30 verses as prompts (no answers) |
| `answer_key.txt` | The reference answers (for scoring) |
| `blind_test_report.md` | Full scored results from the last test run |

## Standard test procedure

### Step 1: Generate blind prompts

```bash
python tests/run_blind_tests.py --export-prompts
```

This creates `tests/blind_prompts.txt` containing 30 verses formatted as إعراب prompts. No reference answers are included.

### Step 2: Run the blind test

Open a **new Claude Code conversation** (so there is no context contamination from the answer key). In that conversation:

1. Load the i'rab skill
2. Feed it the contents of `tests/blind_prompts.txt` — all 30 verses, one at a time or in batches
3. For each verse, the skill should produce a complete إعراب
4. Save the full output to `tests/latest_run.md`

Alternatively, use subagents to run the tests in parallel (5-10 verses per agent). The key rule: **the agent performing the إعراب must NOT have access to `answer_key.txt` or `irab_training_30.json`**.

### Step 3: Score against the answer key

```bash
python tests/run_blind_tests.py --export-keys
```

This creates `tests/answer_key.txt`. Open it alongside `tests/latest_run.md` and score each verse:

For every word in every verse, check:
- **Role** (فاعل/مبتدأ/خبر/مفعول به/...): does the agent match the reference?
- **Case** (رفع/نصب/جر/جزم): match?
- **Case sign** (الضمة/الفتحة/الياء/الواو/حذف النون/...): match?
- **Governor** (العامل): match?
- **محل** for مبني words: match?
- **الجمل**: does the agent correctly identify which have محل and which don't?

Count total items and total errors. An "error" is when the agent gives a **different** analysis than the reference. If the agent provides multiple أوجه and one of them matches the reference, it is **not** an error.

### Step 4: Record results

Update `tests/blind_test_report.md` with:
- Per-verse accuracy (items correct / total items)
- Every error listed with: verse, word, reference answer, agent answer, severity, category
- Overall accuracy across all 30 verses
- Error breakdown by category

### Error categories

| Category | What it means |
|----------|---------------|
| `case-error` | Wrong case (رفع instead of نصب, etc.) |
| `sign-error` | Wrong case sign (الضمة instead of الواو, etc.) |
| `role-error` | Wrong grammatical role (فاعل instead of مبتدأ, etc.) |
| `governor-error` | Wrong عامل identified |
| `particle-type` | Wrong particle classification (واو عاطفة vs استئنافية, etc.) |
| `تعلّق` | Wrong attachment target for جار ومجرور / ظرف |
| `محل-الجملة` | Wrong positional case for a sentence |
| `صاحب-الحال` | Wrong noun identified as the حال's owner |

### Severity levels

| Severity | Meaning |
|----------|---------|
| **HIGH** | Would change the tashkeel or fundamentally alter the parse |
| **MEDIUM** | Different analysis, but both positions are held by classical grammarians |
| **LOW** | Wording or precision difference with no structural impact |

## Baseline results (2026-03-26)

| Metric | Value |
|--------|-------|
| Total verses | 30 |
| Total items scored | 434 |
| Total errors | 10.5 |
| **Overall accuracy** | **97.6%** |
| Verses at 100% | 20 / 30 |
| HIGH severity errors | 0 |
| case/sign/governor errors | 0 |

See `blind_test_report.md` for the full breakdown.

## Adding new test verses

To expand the test set, add entries to `../data/irab_training_30.json` following this format:

```json
{
    "id": 31,
    "verse": "الآية بالتشكيل الكامل",
    "reference": "اسم السورة: رقم الآية",
    "source_book": "رقم الكتاب في المكتبة الشاملة",
    "patterns_tested": ["كان وأخواتها", "حال مفردة"],
    "correct_irab": "الإعراب الكامل منسوخ حرفياً من الكتاب المرجعي"
}
```

Source books available in `/home/ameen/texts/output/التفسير/`:
- `86_إعراب القرآن الكريم - ط دار الصحابة.txt`
- `2163_إعراب القرآن وبيانه.txt`
- `22916_الجدول في إعراب القرآن.txt`
