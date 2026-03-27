# Contributing

Thank you for your interest in improving the Arabic grammatical analysis engine. This document explains how to set up a development environment, report issues, and submit changes.

## Setting Up the Development Environment

```bash
git clone https://github.com/ameen/irab.git
cd irab

python3 -m venv .venv
source .venv/bin/activate

pip install -e .
```

Requirements: Python 3.10 or later. The install pulls in `pyaramorph`, `mcp`, and `pydantic` automatically.

## Running the MCP Server Locally

```bash
# Standalone (stdio transport)
python mcp-server/server.py

# Or via the installed entry point
irab-server
```

To connect it to Claude Code, add this to `.claude/settings.json`:

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

You can then test the three MCP tools (`analyze_word`, `analyze_sentence`, `check_transitivity`) through Claude Code or any MCP client.

## What We Need Help With

The most valuable contributions, roughly in priority order:

1. **Grammar rule corrections** -- if the engine produces an incorrect i'rab for a sentence.
2. **New worked examples** -- especially complex or edge-case constructions (conditionals, nested relative clauses, rare particles, etc.).
3. **Disambiguation tree refinements** -- better decision logic in `grammar/disambiguation.md` for particles like ma, la, an, al-waw, al-fa', etc.
4. **MCP server improvements** -- verb form detection accuracy, passive voice patterns, error handling, new tool functions.
5. **Expanding data files** -- adding verbs to `data/verb_transitivity.json` or nouns to `data/feminine_nouns.json`.

## Reporting an I'rab Error

If the engine produces an incorrect analysis for a sentence, open an issue with this information:

```
Sentence:    كتبَ الطالبُ الرسالةَ
Word:        الطالبُ
Engine gave: مفعول به منصوب
Expected:    فاعل مرفوع
Grammar ref: (optional) which rule in grammar/ applies
Source:      (optional) textbook or grammar reference that supports the correction
```

Include the full sentence, not just the word in isolation -- syntactic role depends on context.

## Adding or Correcting Grammar Rules

Grammar rules live in six files under `grammar/`:

| File | Scope |
|------|-------|
| `grammar-rules.md` | Copulas, subjunctive/jussive particles, derived nouns |
| `special-cases.md` | Five nouns, five verbs, diptotes, estimated/positional i'rab |
| `disambiguation.md` | Decision trees for multi-function particles |
| `roles-and-functions.md` | Subject, object types, prepositional phrases |
| `sentence-analysis.md` | Appositionals, hal, tamyiz, clauses with positional i'rab |
| `asaleeb.md` | Special constructions (exclamation, oath, praise/blame, etc.) |

When editing these files:

- Follow the existing format: Arabic heading, rule statement, then examples with full i'rab.
- Use Arabic grammatical terminology as the primary label; an English gloss in the heading is fine.
- If correcting an existing rule, explain the correction in your PR description and cite a grammar reference if possible.
- Keep rules self-contained -- each section should be usable as a standalone reference.

## Adding Worked Examples

Examples live in `examples/examples.md`. Each example follows this structure:

```markdown
## المثال N: (short description)

**الجملة:** (the Arabic sentence)

**نوع الجملة:** (sentence type)

---

**word:**
- نوعها: (word type and definiteness)
- إعرابها: (grammatical role and case)
- علامة إعرابها: (case marker and whether it is original or substitute)
- العامل: (the governor that assigns the case)

(repeat for each word)

### ملاحظات
- (any notes about the sentence, e.g., "ابتدائية لا محل لها من الإعراب")
```

Good candidates for new examples: sentences that exercise rules not yet covered, constructions where disambiguation is tricky, or sentences from classical texts that expose edge cases.

## Extending the Data Files

### verb_transitivity.json

This file maps unvocalized verb stems to their transitivity and root. The primary data comes from the Qabas lexicographic database (scraped by `scripts/build_transitivity_table.py`). There is also a `"_supplement"` section at the end for manually added entries.

To add a verb that Qabas does not cover, add it to the supplement section:

```json
{
  "_supplement": [
    { "verb": "فعل", "transitivity": "متعد", "root": "ف ع ل", "source": "reason or reference" }
  ]
}
```

Then run the build script to regenerate and merge:

```bash
python scripts/build_transitivity_table.py
```

Do not manually edit entries in the main `"verbs"` object -- those are machine-generated from Qabas.

### feminine_nouns.json

This file lists nouns that are grammatically feminine without a morphological marker (no ta' marbuta). These are called "muannath sama'i". The format is:

```json
{
  "nouns": {
    "شمس": "مؤنث",
    "أرض": "مؤنث"
  }
}
```

Add entries for nouns that the engine misclassifies as masculine. Include both the hamza form and the bare-alif form if applicable (e.g., both `"أرض"` and `"ارض"`). Cite a grammar reference in your PR description.

## Pull Request Guidelines

- **Open an issue first** for non-trivial changes (new grammar sections, server refactors, new MCP tools). Quick fixes and new examples can go straight to a PR.
- Keep PRs focused. One grammar correction or one new feature per PR is easier to review than a combined change.
- If your change affects grammar rules, include at least one example sentence that demonstrates the rule.
- If your change affects the MCP server, verify the three tools still work: `analyze_word`, `analyze_sentence`, `check_transitivity`.
- Write PR descriptions in English. Grammar rule content and examples should be in Arabic.

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
