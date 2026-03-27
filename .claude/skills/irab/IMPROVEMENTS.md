# Improving I'rab Reliability Beyond the Skill

## The Problem

The grammar rules are now complete (4,056 lines across 8 files). The remaining failure mode is not missing rules — it's the LLM misapplying rules under cognitive load (long sentences, multiple nested clauses, several ambiguous particles at once). More reference files can't fix this. The question is: how do we make the mechanical parts deterministic?

---

## Approaches

### 1. Structured Output (cheapest fix)

Force Claude to output JSON for each word, not freeform Arabic text. When you have to fill `{"word": "...", "type": "...", "role": "...", "case": "...", "sign": "...", "governor": "..."}` for every word, you can't skip fields. The skill already has a template but doesn't enforce it structurally. This reduces the "forgot to identify the عامل" failure mode.

**Status: IMPLEMENTED** — Pass 3 output format now requires structured fields per word (type, subtype, declinable, role, case, sign, sign_type, governor, position, notes). No field may be left empty.

### 2. Multi-Pass Agentic Approach

Instead of one prompt doing everything, break it into forced sequential passes with explicit intermediate output:

- **Pass 1**: Tokenize + classify every word (اسم/فعل/حرف + subtype + morphological features). Output a classification table. Stop.
- **Pass 2**: Given that table, identify every عامل + hidden elements + embedded clauses. Output the governor map. Stop.
- **Pass 3**: Given Passes 1+2, assign case + sign for every word mechanically. Output full structured analysis. Stop.
- **Pass 4**: Verify Pass 3 against 6 explicit checks. Output a checklist. Fix any failures.

Each pass is a focused task with less cognitive load. The LLM is much better at one focused step than at juggling all steps simultaneously.

**Status: IMPLEMENTED** — SKILL.md pipeline restructured from 6 merged steps to 4 explicit passes with visible intermediate output.

### 3. MCP Server with Morphological Tools

Build an MCP server that gives Claude **deterministic tools** it can call:

- `analyze_morphology(word)` → returns all possible readings (noun/verb/particle, root, pattern, gender, number, definiteness)
- `lookup_transitivity(verb)` → returns لازم/متعدٍّ/متعدٍّ لمفعولين
- `classify_particle(particle, context)` → returns which type of ما/لا/أنْ/etc. based on syntactic position
- `lookup_verb_conjugation(verb)` → returns full conjugation table to identify بناء

This makes the hardest part — morphological disambiguation — deterministic. Claude just does the syntactic reasoning, which it's actually good at.

#### What is an MCP server?

MCP (Model Context Protocol) is a standard that lets Claude Code (and other AI tools) call external tools — essentially local HTTP servers that expose functions Claude can invoke. Instead of Claude guessing whether a word is masculine or feminine, it calls a tool that looks it up in a database and returns a definitive answer.

**How it works:**
1. You write a small server (Python/TypeScript) that exposes functions
2. You register it in Claude Code's settings (`.claude/settings.json`)
3. When Claude encounters an Arabic word it needs to analyze, it calls `analyze_morphology("كتب")` and gets back structured data: `{root: "ك ت ب", type: "verb", form: "I", transitivity: "transitive", ...}`
4. Claude uses that deterministic data to do the syntactic analysis

**Why it matters for i'rab:**
The hardest part of i'rab for an LLM is morphological analysis (صرف) — is this word a noun or a verb? What's its root? Is it masculine or feminine? Is it مصروف or ممنوع من الصرف? These are lookup problems, not reasoning problems. A database can answer them perfectly. Claude is good at the reasoning part (identifying عوامل, applying grammar rules, handling nested clauses).

**Status: V1 IMPLEMENTED** — MCP server built using pyaramorph (Buckwalter, 82k stems). Provides `analyze_word`, `analyze_sentence`, and `check_transitivity` tools. Registered as `arabic-morphology` MCP server. Limitations: Form I transitivity is heuristic (needs lexical data from Lane's), verb form detection needs refinement for some patterns.

### 4. Hybrid: Rule Engine + LLM (Long-Term Vision)

The ultimate architecture: a deterministic Arabic analysis engine that handles صرف (morphology) and hands structured data to Claude for نحو (syntax).

#### Architecture

```
User Input (Arabic text)
       │
       ▼
┌──────────────────────┐
│  Morphological Engine │  ← Deterministic (code)
│  (صرف)               │
│                      │
│  - Tokenization      │
│  - Root extraction   │
│  - Pattern matching  │
│  - Gender/number     │
│  - Definiteness      │
│  - Transitivity      │
│  - All possible      │
│    readings per word  │
└──────────┬───────────┘
           │ Structured morphological data
           ▼
┌──────────────────────┐
│  Claude (LLM)        │  ← Reasoning (AI)
│  (نحو)               │
│                      │
│  - Sentence type     │
│  - Governor ID       │
│  - Case assignment   │
│  - Disambiguation    │
│  - Clause analysis   │
│  - Output formatting │
└──────────┬───────────┘
           │
           ▼
    Final i'rab output
```

#### Data Sources for the Morphological Engine

**Lane's Lexicon:**
- Edward William Lane's Arabic-English Lexicon — comprehensive classical Arabic dictionary
- Parsed/digitized versions exist (e.g., the Linguistic Research Center at UT Austin, or community projects on GitHub)
- Contains root entries with all derived forms, meanings, and usage
- Can be used to build a root → derived forms → transitivity/meaning database

**Buckwalter Arabic Morphological Analyzer:**
- The standard computational Arabic morphological analyzer
- Given a word, returns all possible analyses (root, pattern, POS, features)
- Available as open-source data tables
- Maps Arabic words to their possible morphological breakdowns

**CAMeL Tools (NYU Abu Dhabi):**
- Modern Python toolkit for Arabic NLP
- Includes morphological analysis, disambiguation, POS tagging
- Built on Buckwalter-style analysis with ML disambiguation
- Could serve as the backbone of the morphological engine

**Deterministic Sarf Patterns:**
Arabic morphology is famously regular — the root+pattern (جذر+وزن) system means:
- Given a 3-letter root (ك ت ب) and a pattern (فَاعِل), the output is deterministic: كَاتِب
- The 10 verb forms (أوزان) have fixed patterns for active/passive, noun of agent/patient, verbal noun, etc.
- This is a perfect candidate for code, not AI — it's pure pattern matching

```
Root: ك ت ب
├── Form I:   كَتَبَ (to write) → transitive
│   ├── Active participle: كَاتِب
│   ├── Passive participle: مَكْتُوب
│   ├── Verbal noun: كِتَابَة / كَتْب
│   └── Passive: كُتِبَ
├── Form II:  كَتَّبَ (to make write) → transitive (causative)
├── Form III: كَاتَبَ (to correspond with) → transitive
├── Form IV:  أَكْتَبَ (to dictate) → transitive
├── Form V:   تَكَتَّبَ (reflexive of II)
├── Form VI:  تَكَاتَبَ (to correspond with each other) → intransitive
├── Form VII: اِنْكَتَبَ (to be written) → intransitive (passive-reflexive)
├── Form VIII: اِكْتَتَبَ (to copy/subscribe) → transitive
├── Form X:  اِسْتَكْتَبَ (to ask to write) → transitive
└── ... etc
```

Each form has known, fixed transitivity patterns. This is code, not guessing.

**Status: LONG-TERM — the ideal solution. Requires:**
1. Sourcing and parsing Lane's Lexicon data (or Buckwalter tables)
2. Building a root extraction algorithm
3. Building a pattern matching engine
4. Wrapping it as an MCP server
5. Integrating with the existing skill

### 5. Fine-Tuned Model

Collect thousands of correctly-parsed sentences (from textbooks, online grammar sites) and fine-tune a smaller model specifically on i'rab. A specialized model trained on this exact task would outperform a general model with a prompt.

**Status: FUTURE — needs training data collection**

---

## Ranking

| Approach | Reliability Gain | Effort | Practicality |
|----------|-----------------|--------|-------------|
| Structured output | Small | Low | Do it now |
| Multi-pass agentic | Medium | Medium | Best bang for buck |
| MCP morphological tools | Large | High | Best for the hardest failure mode |
| Hybrid rule engine | Largest | Very high | The right long-term answer |
| Fine-tuned model | Large | High | Needs training data |

---

## Implementation Plan

### Phase 1: Structured Output + Multi-Pass (NOW)
- Add JSON schema to SKILL.md output format
- Restructure the 6-step pipeline as forced sequential passes
- Each pass validates the previous pass's output

### Phase 2: MCP Morphological Server (NEXT)
- Source Buckwalter or CAMeL Tools morphological data
- Build a simple MCP server exposing `analyze_morphology()`, `lookup_root()`, `check_transitivity()`
- Register it in Claude Code settings
- Update the skill to call these tools in Pass 1

### Phase 3: Full Hybrid Engine (FUTURE)
- Parse Lane's Lexicon data into a queryable database
- Build complete root+pattern engine for all 10 verb forms
- Add comprehensive noun pattern recognition
- The morphological engine handles صرف deterministically
- Claude handles نحو (syntax/grammar) with structured input
- Effectively splits the problem: code does what code is good at, AI does what AI is good at
