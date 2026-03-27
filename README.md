# Mizan — Arabic Grammatical Analysis Engine

**Deterministic Arabic i'rab using morphological lookup and classical grammar decision trees — no statistical guessing.**

<div dir="rtl">

محرّك إعراب عربي يجمع بين التحليل الصرفي الحاسوبي (محلّل بكوالتر، ٨٢ ألف جذع) وقواعد النحو العربي الكلاسيكي المستخرجة من شرح ابن عقيل ومغني اللبيب لابن هشام (أكثر من ٤٩٠٠ سطر).

</div>

---

**Input:** `كتبَ الطالبُ الرسالةَ`

**Output:**
> **كتبَ:** فعل ماضٍ مبني على الفتح، والفاعل ضمير مستتر جوازًا تقديره «هو».
>
> **الطالبُ:** فاعل مرفوع وعلامة رفعه الضمة الظاهرة على آخره.
>
> **الرسالةَ:** مفعول به منصوب وعلامة نصبه الفتحة الظاهرة على آخره.

## Why This Exists

LLMs produce Arabic grammatical analysis that sounds fluent but is unreliable. They assign grammatical roles based on statistical patterns, not on the actual rules of Arabic grammar. The result is output that mixes correct and incorrect analyses with no way to tell which is which.

Arabic i'rab is not a probabilistic problem. It is a rule-based system: a word's grammatical case is determined by its governor (عامل), its governor is identified by structural conditions, and those conditions are binary — either a particle is present or it isn't, either a verb is transitive or it isn't. When a word like "ما" appears in a sentence, it has exactly one correct classification based on what surrounds it: it is either نافية, or موصولية, or مصدرية, or شرطية, or استفهامية — and which one it is can be determined by checking a finite set of conditions, not by guessing.

This engine replaces probability with decision trees. Every grammar rule was extracted from two classical references:

1. **Sharh Ibn Aqil ala Alfiyyat Ibn Malik** (شرح ابن عقيل على ألفية ابن مالك) — the standard teaching commentary on Arabic grammar
2. **Mughni al-Labib an Kutub al-A'arib** (مغني اللبيب عن كتب الأعاريب) by Ibn Hisham al-Ansari — the comprehensive reference on particles, sentence types, and disambiguation

The rules are encoded as ~5,000 lines of structured decision trees covering النواسخ, المنصوبات, التوابع, الأساليب, and 11 disambiguation trees for multi-function particles. Morphological analysis is handled by the Buckwalter Arabic Morphological Analyzer (82,000+ stems), providing deterministic word classification before any syntactic reasoning begins.

## Results

We tested the engine against 10 leading LLMs on 30 Quranic verses, scoring each response word-by-word against published reference i'rab from three books:

1. **I'rab al-Quran al-Karim** (إعراب القرآن الكريم) — Dar al-Sahaba li'l-Turath
2. **I'rab al-Quran wa Bayanuhu** (إعراب القرآن وبيانه) — Muhyi al-Din al-Darwish
3. **Al-Jadwal fi I'rab al-Quran** (الجدول في إعراب القرآن) — Mahmud bin Abd al-Rahim al-Safi

Every model received the same prompt and the same 30 verses. For each word, we checked: grammatical role, case, case sign, governor, and sentence-level analysis against the published reference.

| # | Model | Tier | Accuracy | 100% Verses |
|---|-------|------|----------|-------------|
| 1 | **I'rab Engine** | **Ours** | **97.6%** | **20/30** |
| 2 | Command A | Open-source | 71.5% | 2/30 |
| 3 | Gemini 2.5 Pro | Frontier | 70.9% | 1/30 |
| 4 | GPT-4o | Frontier | 69.0% | 0/30 |
| 5 | Qwen 3 235B | Open-source | 69.0% | 2/30 |
| 6 | DeepSeek V3 | Open-source | 67.6% | 0/30 |
| 7 | Claude Haiku 4.5 | Mid-tier | 67.3% | 1/30 |
| 8 | Llama 4 Maverick | Open-source | 67.0% | 0/30 |
| 9 | Gemini 2.0 Flash | Mid-tier | 66.8% | 0/30 |
| 10 | Claude Sonnet 4 | Frontier | 65.4% | 0/30 |
| 11 | GPT-4o Mini | Mid-tier | 57.9% | 0/30 |

The engine achieved **zero** errors in case assignment, case signs, and governor identification. Its remaining ~2.4% consists entirely of legitimate differences of grammatical opinion (خلاف نحوي) where classical grammarians themselves disagree. For example:

> In **آل عمران: 3**, the reference (*إعراب القرآن الكريم*) says مُصَدِّقاً is حال من الضمير في عليك — the hidden pronoun "you" is the owner of the state. The engine analyzed it as حال من الكتاب — the "book" is described as "confirming". Both positions are attested in classical grammar: the majority of grammarians hold that when multiple candidates exist, the حال attaches to the nearest eligible noun (Ibn Aqil, *Sharh Alfiyyat Ibn Malik*, section on الحال; al-Sabban, *Hashiyat al-Sabban ala Sharh al-Ashmuni*), while others tie it to the logical agent. Neither analysis changes the case (منصوب) or the governor (the verb نزّل).

The full error inventory, scoring methodology, and per-verse breakdowns are in [`tests/blind_test_report.md`](tests/blind_test_report.md). The benchmark scripts that called the 10 models are in [`tests/benchmark_models.py`](tests/benchmark_models.py).

## Architecture

```
┌──────────────────────────────┐
│  صرف — Morphology (Code)     │  Deterministic: Buckwalter Analyzer
│  82,000+ stems, 299 prefixes │  → word type, root, gender, number,
│  618 suffixes                │    voice, transitivity, definiteness
└──────────────┬───────────────┘
               │ structured morphological data
               ▼
┌──────────────────────────────┐
│  نحو — Syntax (Rules)        │  Decision trees: governor identification,
│  ~5,000 lines of grammar     │  case assignment, disambiguation,
│  rules + decision trees      │  clause analysis, verification
└──────────────────────────────┘
```

**Morphology is a lookup problem. Syntax is a reasoning problem.** This engine uses the right tool for each.

### Analysis Pipeline

A 4-pass sequential pipeline:

1. **Classification** (التصنيف) — Classify every word using morphological tools + disambiguation trees
2. **Governor Mapping** (العوامل) — Identify what causes each word's grammatical case
3. **Case Assignment** (الإعراب) — Assign case and case sign mechanically from governor → case → sign chain
4. **Verification** (المراجعة) — Validate against 6 explicit checks; fix inconsistencies

### MCP Server

An [MCP](https://modelcontextprotocol.io/) server exposing morphological analysis tools:

| Tool | Purpose |
|------|---------|
| `analyze_word(word)` | All morphological readings for a single word |
| `analyze_sentence(text)` | Top 5 readings per word in a sentence |
| `check_transitivity(verb)` | Verb form (I–X), voice, and transitivity |

Built on [pyaramorph](https://pypi.org/project/pyaramorph/) (Python port of the Buckwalter Arabic Morphological Analyzer).

### Grammar Rules

Extracted from Sharh Ibn Aqil and Mughni al-Labib, encoded as six structured reference files:

| File | Lines | Coverage |
|------|-------|----------|
| `grammar-rules.md` | 1,027 | النواسخ (كان/إنّ/ظنّ), حروف النصب والجزم, المشتقات العاملة |
| `disambiguation.md` | 995 | 11 decision trees for multi-function particles (ما، لا، أنْ، الواو, ...) |
| `roles-and-functions.md` | 853 | المرفوعات, المنصوبات (16 types), المجرورات, تعلّق شبه الجملة |
| `special-cases.md` | 821 | الأسماء الخمسة, الأفعال الخمسة, الممنوع من الصرف, الإعراب التقديري/المحلي |
| `sentence-analysis.md` | 710 | التوابع (نعت/عطف/توكيد/بدل), الحال, التمييز, الجمل ذات المحل |
| `asaleeb.md` | 553 | 12 أسلوب: التعجب, المدح/الذم, القسم, الاشتغال, التنازع, ... |

## Installation

### Requirements

- Python 3.10+

### Setup

```bash
git clone https://github.com/ameenalkhaldi/mizan.git
cd mizan
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Use with Claude Code

1. Add the MCP server to your Claude Code settings (`.claude/settings.json`):

```json
{
  "mcpServers": {
    "arabic-morphology": {
      "command": "/path/to/irab/.venv/bin/python3",
      "args": ["/path/to/irab/mcp-server/server.py"]
    }
  }
}
```

2. Copy the skill and grammar references to your project:

```bash
cp -r skill/SKILL.md /your/project/.claude/skills/irab/SKILL.md
cp -r grammar/ /your/project/.claude/skills/irab/references/
cp -r examples/ /your/project/.claude/skills/irab/examples/
```

3. Use the trigger words: `أعرب`, `إعراب`, `irab`, `parse arabic`

## Project Structure

```
mizan/
├── mcp-server/
│   ├── server.py              # MCP server entry point
│   ├── analyzer.py            # Morphological analysis wrapper
│   ├── disambiguator.py       # Particle disambiguation logic
│   ├── governor.py            # Governor identification
│   ├── conjugator.py          # Verb conjugation
│   └── api.py                 # HTTP API
├── grammar/                   # Classical Arabic grammar rules (~5,000 lines)
│   ├── grammar-rules.md       # النواسخ, حروف النصب/الجزم
│   ├── disambiguation.md      # 11 particle decision trees
│   ├── roles-and-functions.md # المرفوعات, المنصوبات, تعلّق شبه الجملة
│   ├── special-cases.md       # الأسماء الخمسة, الممنوع من الصرف
│   ├── sentence-analysis.md   # التوابع, الحال, الجمل ذات المحل
│   └── asaleeb.md             # 12 special constructions
├── data/
│   ├── irab_training_30.json  # 30 test verses with reference i'rab
│   ├── verb_transitivity.json # Verb transitivity lookup
│   └── feminine_nouns.json    # Feminine noun list
├── examples/
│   └── examples.md            # 25 worked i'rab examples
├── skill/
│   └── SKILL.md               # Claude Code skill definition
├── tests/
│   ├── blind_test_report.md   # Full scored results (97.6%)
│   ├── benchmark_models.py    # LLM benchmark: call 10 models via OpenRouter
│   ├── benchmark_score.py     # Score responses against published reference
│   ├── benchmark_report.py    # Generate comparison table
│   └── test_*.py              # Unit tests (governor, disambiguator, etc.)
├── docs/
│   └── architecture.md        # System design & data flow
├── web/
│   └── index.html             # Web demo
└── pyproject.toml
```

## Contributing

Contributions are welcome — especially:

- **Grammar rule corrections** — if the engine parses a sentence incorrectly
- **New worked examples** — particularly for complex or edge-case constructions
- **Disambiguation tree refinements** — better decision logic for ambiguous particles

Please open an issue first to discuss non-trivial changes. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Support

If this project is useful to you, consider [sponsoring](https://github.com/sponsors/ameenalkhaldi) its development.

## License

[Apache License 2.0](LICENSE)

## Acknowledgments

- [Buckwalter Arabic Morphological Analyzer](https://catalog.ldc.upenn.edu/LDC2004L02) — the foundational morphological database
- [pyaramorph](https://pypi.org/project/pyaramorph/) — Python port of the Buckwalter analyzer
- [FastMCP](https://github.com/jlowin/fastmcp) — Model Context Protocol framework
- Classical Arabic grammarians whose work underpins the grammar rules: Sibawayh, Ibn Hisham, Ibn Aqil, Ibn Malik
