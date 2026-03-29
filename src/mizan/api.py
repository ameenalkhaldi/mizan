"""
REST API for Arabic Morphological Analysis (صرف)
HTTP wrapper around the analyzer module — no MCP dependency.

Run:
    python mcp-server/api.py
    # or: uvicorn api:app --host 0.0.0.0 --port 8000  (from mcp-server/)
"""

import json
import os
import re
import shutil
import subprocess

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import pyaramorph

from analyzer import (
    analyzer,
    parse_solution,
    detect_verb_form,
    lookup_transitivity,
    QABAS_VERBS,
    PV_PASS_STEMS,
    IV_PASS_STEMS,
    FEMININE_NOUNS,
)
from conjugator import conjugate

# --- Configuration (from env vars with defaults) ---

IRAB_MODEL = os.environ.get("IRAB_MODEL", "claude-opus-4-6-20250619")
IRAB_MAX_TOKENS = int(os.environ.get("IRAB_MAX_TOKENS", "16384"))
IRAB_MAX_TOOL_ROUNDS = int(os.environ.get("IRAB_MAX_TOOL_ROUNDS", "10"))

# Arabic character range for input validation
_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")


def _validate_arabic(text: str, field: str = "input") -> str | None:
    """Validate that input is non-empty and contains Arabic text.

    Returns an error message string, or None if valid.
    """
    if not text or not text.strip():
        return f"{field} cannot be empty"
    if not _ARABIC_RE.search(text):
        return f"{field} does not contain Arabic text"
    return None


app = FastAPI(
    title="irab",
    version="0.1.0",
    description="Arabic morphological analysis API powered by the Buckwalter "
    "Arabic Morphological Analyzer (82,000+ stems) and Qabas lexical data.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# --- I'rab system prompt (loaded once at startup) ---

_base_dir = os.path.dirname(__file__)
_skill_path = os.path.join(_base_dir, "..", "skill", "SKILL.md")
_grammar_dir = os.path.join(_base_dir, "..", "grammar")

_IRAB_SYSTEM_PROMPT = None


def _load_irab_prompt() -> str:
    """Load SKILL.md + all grammar reference files as the i'rab system prompt."""
    global _IRAB_SYSTEM_PROMPT
    if _IRAB_SYSTEM_PROMPT is not None:
        return _IRAB_SYSTEM_PROMPT

    parts = []

    # Load main skill file
    if os.path.exists(_skill_path):
        with open(_skill_path, encoding="utf-8") as f:
            parts.append(f.read())

    # Load all grammar reference files
    if os.path.isdir(_grammar_dir):
        for fname in sorted(os.listdir(_grammar_dir)):
            if fname.endswith(".md"):
                fpath = os.path.join(_grammar_dir, fname)
                with open(fpath, encoding="utf-8") as f:
                    parts.append(f"\n\n---\n\n# Reference: {fname}\n\n{f.read()}")

    _IRAB_SYSTEM_PROMPT = "\n".join(parts)
    return _IRAB_SYSTEM_PROMPT


# --- Claude API tool definitions for i'rab ---

IRAB_TOOLS = [
    {
        "name": "analyze_word",
        "description": (
            "Analyze a single Arabic word morphologically. "
            "Returns all possible readings from the Buckwalter database (82,000+ stems). "
            "Each analysis includes: vocalized form, POS type (اسم/فعل/حرف), tense, voice, "
            "gender, number, definiteness, glosses, and prefix/suffix decomposition. "
            "Use this when unsure about a word's type or morphological class."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "word": {
                    "type": "string",
                    "description": "A single Arabic word (with or without tashkeel)",
                }
            },
            "required": ["word"],
        },
    },
    {
        "name": "analyze_sentence",
        "description": (
            "Analyze all words in an Arabic sentence morphologically. "
            "Returns the top 5 morphological readings per word with full features: "
            "vocalized form, POS type (اسم/فعل/حرف), tense, voice, gender, number, "
            "definiteness, glosses, and prefix/suffix decomposition. "
            "Use this in Pass 1 to build the classification table from definitive data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Arabic sentence (with or without tashkeel)",
                }
            },
            "required": ["text"],
        },
    },
    {
        "name": "check_transitivity",
        "description": (
            "Check if an Arabic verb is transitive (متعدٍّ) or intransitive (لازم). "
            "Also detects the verb form (I-X) and voice. "
            "Use this in Pass 2 to determine whether a verb takes a مفعول به."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "verb": {
                    "type": "string",
                    "description": "Arabic verb (with or without tashkeel)",
                }
            },
            "required": ["verb"],
        },
    },
    {
        "name": "classify_particle",
        "description": (
            "Classify a multi-function Arabic particle (ما، لا، أنْ/إنْ، الواو، الفاء) "
            "based on its context. Returns ranked possible classifications with "
            "morphological evidence from the surrounding words. "
            "Use this when encountering ambiguous particles during i'rab analysis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "particle": {
                    "type": "string",
                    "description": "The Arabic particle to classify",
                },
                "before": {
                    "type": "string",
                    "description": "The word immediately before the particle (empty if sentence-initial)",
                    "default": "",
                },
                "after": {
                    "type": "string",
                    "description": "The word immediately after the particle",
                    "default": "",
                },
            },
            "required": ["particle"],
        },
    },
]


def _execute_tool(name: str, input_data: dict) -> str:
    """Execute a morphological tool locally and return JSON result."""
    if name == "analyze_word":
        word = input_data["word"]
        results = analyzer.analyze_text(word)
        if not results:
            return json.dumps({"word": word, "analyses": [], "error": "Word not found"}, ensure_ascii=False)
        analyses = [parse_solution(sol) for sol in results[0][1:]]
        return json.dumps({"word": word, "total_analyses": len(analyses), "analyses": analyses}, ensure_ascii=False)

    elif name == "analyze_sentence":
        text = input_data["text"]
        results = analyzer.analyze_text(text)
        words = []
        for entry in results:
            header = entry[0]
            solutions = entry[1:]
            m = re.match(r"analysis for:\s+(\S+)", header)
            original = m.group(1) if m else header
            analyses = [parse_solution(sol) for sol in solutions[:5]]
            words.append({
                "word": original,
                "total_readings": len(solutions),
                "top_analyses": analyses,
            })
        return json.dumps({"text": text, "words": words}, ensure_ascii=False)

    elif name == "check_transitivity":
        verb = input_data["verb"]
        results = analyzer.analyze_text(verb)
        if not results:
            return json.dumps({"verb": verb, "error": "Not found"}, ensure_ascii=False)
        readings = []
        for sol in results[0][1:]:
            parsed = parse_solution(sol)
            if parsed["type"] != "فعل":
                continue
            voc = parsed.get("vocalized", "")
            form = "I"
            if voc:
                try:
                    buck = pyaramorph.buckwalter.uni2buck(voc)
                except Exception:
                    buck = ""
                if buck:
                    form = detect_verb_form(buck)
            is_passive = parsed.get("voice") == "مبني للمجهول"
            transitivity = None
            transitivity_source = None
            result = lookup_transitivity(voc)
            if result:
                transitivity, transitivity_source = result
            if not transitivity:
                intransitive_forms = {"V", "VI", "VII", "IX"}
                if is_passive:
                    transitivity = "مبني للمجهول (أصله متعدٍّ)"
                elif form in intransitive_forms:
                    transitivity = "لازم"
                else:
                    transitivity = "متعدٍّ"
                transitivity_source = "heuristic"
            readings.append({
                "vocalized": voc, "form": form, "voice": parsed.get("voice"),
                "transitivity": transitivity, "transitivity_source": transitivity_source,
                "gloss": parsed.get("gloss"), "tense": parsed.get("tense"),
            })
        return json.dumps({"verb": verb, "readings": readings}, ensure_ascii=False)

    elif name == "classify_particle":
        particle = input_data.get("particle", "")
        before = input_data.get("before", "")
        after = input_data.get("after", "")
        # Import and call the MCP server's classify_particle logic
        from server import classify_particle as _classify_particle
        return _classify_particle(particle, before, after)

    return json.dumps({"error": f"Unknown tool: {name}"})


# --- Endpoints ---


@app.get("/analyze/word")
def api_analyze_word(word: str = Query(..., description="Arabic word (with or without tashkeel)")):
    """Analyze a single Arabic word morphologically.

    Returns all possible readings from the Buckwalter database.
    """
    err = _validate_arabic(word, "word")
    if err:
        return {"word": word, "analyses": [], "error": err}
    results = analyzer.analyze_text(word)
    if not results:
        return {"word": word, "analyses": [], "error": "Word not found in database"}

    entry = results[0]
    analyses = [parse_solution(sol) for sol in entry[1:]]

    return {
        "word": word,
        "total_analyses": len(analyses),
        "analyses": analyses,
    }


@app.get("/analyze/sentence")
def api_analyze_sentence(text: str = Query(..., description="Arabic sentence")):
    """Analyze all words in an Arabic sentence.

    Returns the top 5 morphological readings per word.
    """
    err = _validate_arabic(text, "text")
    if err:
        return {"text": text, "words": [], "error": err}
    results = analyzer.analyze_text(text)
    words = []

    for entry in results:
        header = entry[0]
        solutions = entry[1:]

        m = re.match(r"analysis for:\s+(\S+)", header)
        original = m.group(1) if m else header

        analyses = [parse_solution(sol) for sol in solutions[:5]]

        words.append({
            "word": original,
            "total_readings": len(solutions),
            "top_analyses": analyses,
        })

    return {"text": text, "words": words}


@app.get("/check/transitivity")
def api_check_transitivity(verb: str = Query(..., description="Arabic verb")):
    """Check verb transitivity (متعدٍّ/لازم) and detect form (I-X)."""
    err = _validate_arabic(verb, "verb")
    if err:
        return {"verb": verb, "error": err}
    results = analyzer.analyze_text(verb)
    if not results:
        return {"verb": verb, "error": "Not found"}

    readings = []
    for sol in results[0][1:]:
        parsed = parse_solution(sol)
        if parsed["type"] != "فعل":
            continue

        voc = parsed.get("vocalized", "")
        form = "I"
        if voc:
            try:
                buck = pyaramorph.buckwalter.uni2buck(voc)
            except Exception:
                buck = ""
            if buck:
                form = detect_verb_form(buck)

        is_passive = parsed.get("voice") == "مبني للمجهول"

        transitivity = None
        transitivity_source = None
        result = lookup_transitivity(voc)
        if result:
            transitivity, transitivity_source = result
        if not transitivity:
            intransitive_forms = {"V", "VI", "VII", "IX"}
            if is_passive:
                transitivity = "مبني للمجهول (أصله متعدٍّ)"
            elif form in intransitive_forms:
                transitivity = "لازم"
            else:
                transitivity = "متعدٍّ"
            transitivity_source = "heuristic"

        readings.append({
            "vocalized": voc,
            "form": form,
            "voice": parsed.get("voice"),
            "transitivity": transitivity,
            "transitivity_source": transitivity_source,
            "gloss": parsed.get("gloss"),
            "tense": parsed.get("tense"),
        })

    return {"verb": verb, "readings": readings}


@app.get("/irab/full")
def api_full_irab(text: str = Query(..., description="Arabic sentence")):
    """Complete deterministic i'rab analysis (all 4 passes).

    Returns per-word role, governor, case, case sign, hidden pronouns,
    and verification report.
    """
    import dataclasses
    err = _validate_arabic(text, "text")
    if err:
        return {"text": text, "error": err}
    from governor import full_irab
    result = full_irab(text)
    gov_words = []
    if result.governor_map:
        for i, w in enumerate(result.governor_map.words):
            sign = result.case_signs[i] if i < len(result.case_signs) and result.case_signs[i] else None
            entry = dataclasses.asdict(w)
            entry["case_sign"] = dataclasses.asdict(sign) if sign else None
            gov_words.append(entry)
    return {
        "original_text": result.original_text,
        "clause_type": result.governor_map.clause_type if result.governor_map else "",
        "words": gov_words,
        "ambiguities": result.governor_map.ambiguities if result.governor_map else [],
        "verification": result.verification,
        "passed_verification": result.passed_verification,
    }


@app.get("/map/governors")
def api_map_governors(text: str = Query(..., description="Arabic sentence")):
    """Deterministic Pass 1+2: classification + governor mapping.

    Returns per-word governor, grammatical role, expected case,
    hidden pronouns, and flagged ambiguities.
    """
    import dataclasses
    err = _validate_arabic(text, "text")
    if err:
        return {"text": text, "error": err}
    from governor import map_governors
    result = map_governors(text)
    data = {
        "original_text": result.original_text,
        "clause_type": result.clause_type,
        "words": [dataclasses.asdict(w) for w in result.words],
        "ambiguities": result.ambiguities,
    }
    return data


@app.get("/classify/sentence")
def api_classify_sentence(text: str = Query(..., description="Arabic sentence")):
    """Deterministic Pass 1 classification for an Arabic sentence.

    Returns per-word classification with type, subtype, tense, voice,
    gender, number, definiteness, مبني/معرب, particle type, tashkeel,
    sentence type, and النواسخ identification.
    """
    import dataclasses
    err = _validate_arabic(text, "text")
    if err:
        return {"text": text, "error": err}
    from disambiguator import classify_sentence
    result = classify_sentence(text)
    return dataclasses.asdict(result)


@app.get("/tasrif")
def api_tasrif(verb: str = Query(..., description="Arabic verb to conjugate")):
    """Generate full conjugation table (تصريف) for an Arabic verb."""
    err = _validate_arabic(verb, "verb")
    if err:
        return {"verb": verb, "error": err}
    return conjugate(verb)


class IrabRequest(BaseModel):
    text: str


def _irab_via_cli(text: str) -> str:
    """Run i'rab analysis via the claude CLI (uses Claude Code Max auth)."""
    result = subprocess.run(
        ["claude", "-p", f"أعرب: {text}", "--output-format", "text"],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=os.path.join(_base_dir, ".."),
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"claude exited with code {result.returncode}")
    return result.stdout.strip()


def _irab_via_api(text: str, api_key: str) -> str:
    """Run i'rab analysis via the Anthropic API (uses API key)."""
    import anthropic

    system_prompt = _load_irab_prompt()
    client = anthropic.Anthropic(api_key=api_key)
    messages = [{"role": "user", "content": f"أعرب: {text}"}]

    # Tool use loop with iteration limit (#14)
    for _ in range(IRAB_MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=IRAB_MODEL,
            system=system_prompt,
            messages=messages,
            tools=IRAB_TOOLS,
            max_tokens=IRAB_MAX_TOKENS,
        )

        if response.stop_reason == "end_turn":
            break

        # Handle tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result_text = _execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                })

        if not tool_results:
            break

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    # Extract final text from response
    parts = []
    for block in response.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "".join(parts)


@app.post("/irab")
async def api_irab(request: IrabRequest):
    """Perform full i'rab (grammatical case analysis) on an Arabic sentence.

    Uses Anthropic API if ANTHROPIC_API_KEY is set, otherwise falls back
    to the claude CLI (for local testing with Claude Code Max).
    """
    err = _validate_arabic(request.text, "text")
    if err:
        return {"text": request.text, "error": err}

    api_key = os.environ.get("ANTHROPIC_API_KEY")

    try:
        if api_key:
            irab_text = _irab_via_api(request.text, api_key)
        elif shutil.which("claude"):
            irab_text = _irab_via_cli(request.text)
        else:
            return {"text": request.text, "error": "No API key set and claude CLI not found"}

        return {"text": request.text, "irab": irab_text}
    except Exception as e:
        return {"text": request.text, "error": str(e)}


_web_dir = os.path.join(_base_dir, "..", "web")


@app.get("/")
def serve_index():
    """Serve the web UI."""
    index_path = os.path.join(_web_dir, "index.html")
    if os.path.exists(index_path):
        from fastapi.responses import HTMLResponse
        with open(index_path, encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return {"error": "web/index.html not found"}


@app.get("/health")
def health():
    """Server health check with loaded data stats."""
    return {
        "status": "ok",
        "data": {
            "stems": len(analyzer.stems),
            "qabas_verbs": len(QABAS_VERBS),
            "passive_past_stems": len(PV_PASS_STEMS),
            "passive_imperfect_stems": len(IV_PASS_STEMS),
            "feminine_nouns": len(FEMININE_NOUNS),
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
