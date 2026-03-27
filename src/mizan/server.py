"""
MCP Server for Arabic Morphological Analysis (صرف)
Thin MCP wrapper around the analyzer module.
"""

import re
import json
from mcp.server.fastmcp import FastMCP

import pyaramorph

from .analyzer import (
    analyzer,
    parse_solution,
    detect_verb_form,
    lookup_transitivity,
    DIACRITICS_RE,
)

mcp = FastMCP("arabic-morphology", instructions="""
Arabic Morphological Analysis Server (صرف).
Provides deterministic morphological analysis for Arabic words using the
Buckwalter Arabic Morphological Analyzer (82,000+ stem entries).
Use these tools during i'rab analysis to get definitive word classifications
instead of guessing.
""")


@mcp.tool()
def analyze_word(word: str) -> str:
    """Analyze a single Arabic word morphologically.

    Returns all possible morphological analyses from the Buckwalter database (82,000+ stems).
    Each analysis includes: vocalized form, POS, type (اسم/فعل/حرف), tense, voice,
    gender, number, definiteness, glosses, and prefix/suffix decomposition.

    Use this to get DEFINITIVE morphological data for a word before doing i'rab.
    The first analysis is usually the most common reading.

    Args:
        word: A single Arabic word (with or without tashkeel)
    """
    results = analyzer.analyze_text(word)
    if not results:
        return json.dumps({"word": word, "analyses": [], "error": "Word not found in database"}, ensure_ascii=False)

    entry = results[0]
    solutions = entry[1:]

    analyses = []
    for sol_text in solutions:
        parsed = parse_solution(sol_text)
        analyses.append(parsed)

    return json.dumps({
        "word": word,
        "total_analyses": len(analyses),
        "analyses": analyses
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def analyze_sentence(text: str) -> str:
    """Analyze all words in an Arabic sentence morphologically.

    Returns morphological analyses for every word in the sentence.
    For each word, returns the top 5 most likely readings with full
    morphological features.

    Use this as the first step of i'rab — get definitive morphological
    data for all words before doing syntactic analysis.

    Args:
        text: An Arabic sentence (with or without tashkeel)
    """
    results = analyzer.analyze_text(text)
    sentence_analysis = []

    for entry in results:
        header = entry[0]
        solutions = entry[1:]

        m = re.match(r'analysis for:\s+(\S+)', header)
        original = m.group(1) if m else header

        analyses = []
        for sol_text in solutions[:5]:
            parsed = parse_solution(sol_text)
            analyses.append(parsed)

        sentence_analysis.append({
            "word": original,
            "total_readings": len(solutions),
            "top_analyses": analyses
        })

    return json.dumps({
        "text": text,
        "words": sentence_analysis
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def check_transitivity(verb: str) -> str:
    """Check if an Arabic verb is transitive (متعدٍّ) or intransitive (لازم).

    Analyzes the verb morphologically and checks its gloss patterns to
    determine transitivity. Returns the verb form (I-X) when detectable.

    Args:
        verb: An Arabic verb (with or without tashkeel)
    """
    results = analyzer.analyze_text(verb)
    if not results:
        return json.dumps({"verb": verb, "error": "Not found"}, ensure_ascii=False)

    entry = results[0]
    solutions = entry[1:]

    verb_readings = []
    for sol_text in solutions:
        parsed = parse_solution(sol_text)
        if parsed["type"] == "فعل":
            gloss = parsed.get("gloss", "") or ""
            is_passive = parsed.get("voice") == "مبني للمجهول"

            # Detect verb form
            voc = parsed.get("vocalized", "")
            form = "I"
            if voc:
                try:
                    buck = pyaramorph.buckwalter.uni2buck(voc)
                except Exception:
                    buck = ""
                if buck:
                    form = detect_verb_form(buck)

            # Transitivity: Qabas lookup first, heuristic fallback
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

            verb_readings.append({
                "vocalized": voc,
                "form": form,
                "voice": parsed.get("voice"),
                "transitivity": transitivity,
                "transitivity_source": transitivity_source,
                "gloss": gloss,
                "tense": parsed.get("tense"),
            })

    return json.dumps({
        "verb": verb,
        "readings": verb_readings
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def classify_particle(particle: str, before: str = "", after: str = "") -> str:
    """Classify a multi-function Arabic particle based on its context.

    Disambiguates particles like ما، لا، أنْ/إنْ، الواو، الفاء that have
    multiple grammatical functions depending on context. Returns ranked
    possible classifications with morphological evidence.

    Args:
        particle: The Arabic particle to classify (ما، لا، أن، إن، و، ف, etc.)
        before: The word immediately before the particle (empty if sentence-initial)
        after: The word immediately after the particle
    """
    stripped = DIACRITICS_RE.sub("", particle)

    # Analyze surrounding words morphologically
    before_info = None
    after_info = None
    if before:
        results = analyzer.analyze_text(before)
        if results and len(results[0]) > 1:
            before_info = parse_solution(results[0][1])
    if after:
        results = analyzer.analyze_text(after)
        if results and len(results[0]) > 1:
            after_info = parse_solution(results[0][1])

    classifications = []

    # --- ما ---
    if stripped == "ما":
        # Check for كافة after إنّ and sisters
        nawasikh = {"إن", "أن", "كأن", "لكن", "ليت", "لعل", "رب", "حيث", "بعد",
                    "إنّ", "أنّ", "كأنّ", "لكنّ"}
        before_bare = DIACRITICS_RE.sub("", before) if before else ""
        if before_bare in nawasikh:
            classifications.append({"type": "ما الكافة (زائدة)", "confidence": "high",
                                    "effect": "كفّت العامل عن العمل", "evidence": f"جاءت بعد «{before}»"})
        # After: أفعل pattern → تعجبية
        if after_info and after_info.get("type") == "فعل" and after_info.get("tense") == "ماضٍ":
            voc = after_info.get("vocalized", "")
            if voc:
                buck = ""
                try:
                    buck = pyaramorph.buckwalter.uni2buck(voc)
                except Exception:
                    pass
                if buck.startswith(">a") or buck.startswith("Oa"):
                    classifications.append({"type": "ما التعجبية", "confidence": "high",
                                            "role": "مبتدأ في محل رفع", "evidence": f"تليها «{after}» على وزن أفعلَ"})
        # Before verb → نافية or مصدرية
        if after_info and after_info.get("type") == "فعل":
            tense = after_info.get("tense", "")
            classifications.append({"type": "ما النافية", "confidence": "medium",
                                    "effect": "لا عمل لها مع الأفعال", "evidence": f"تليها فعل ({tense})"})
            classifications.append({"type": "ما المصدرية", "confidence": "medium",
                                    "effect": "مصدر مؤول", "evidence": f"تليها فعل يصح تأويله بمصدر"})
        # Before noun
        if after_info and after_info.get("type") == "اسم":
            classifications.append({"type": "ما النافية (حجازية/تميمية)", "confidence": "medium",
                                    "effect": "قد تعمل عمل ليس", "evidence": f"تليها اسم «{after}»"})
            classifications.append({"type": "ما الموصولة", "confidence": "medium",
                                    "role": "اسم موصول بمعنى الذي", "evidence": "يُحتمل أن تكون موصولة"})
        if not classifications:
            classifications.append({"type": "ما الموصولة", "confidence": "low"})
            classifications.append({"type": "ما الزائدة", "confidence": "low"})

    # --- لا ---
    elif stripped == "لا":
        if after_info and after_info.get("type") == "فعل" and after_info.get("tense") == "مضارع":
            classifications.append({"type": "لا الناهية (جازمة)", "confidence": "high",
                                    "effect": "تجزم المضارع", "evidence": f"تليها فعل مضارع «{after}»"})
            classifications.append({"type": "لا النافية", "confidence": "medium",
                                    "effect": "لا عمل لها", "evidence": "تليها فعل مضارع (نفي)"})
        elif after_info and after_info.get("type") == "اسم":
            if after_info.get("definiteness") != "معرفة":
                classifications.append({"type": "لا النافية للجنس", "confidence": "high",
                                        "effect": "تعمل عمل إنّ", "evidence": f"تليها اسم نكرة «{after}»"})
            classifications.append({"type": "لا النافية", "confidence": "medium"})
        elif before_info and before_info.get("type") == "اسم":
            classifications.append({"type": "لا العاطفة", "confidence": "medium",
                                    "effect": "حرف عطف", "evidence": "بين اسمين"})
        if not classifications:
            classifications.append({"type": "لا النافية", "confidence": "low"})

    # --- أنْ (open hamza) ---
    elif stripped in ("أن", "ان"):
        if after_info and after_info.get("type") == "فعل" and after_info.get("tense") == "مضارع":
            classifications.append({"type": "أنْ المصدرية الناصبة", "confidence": "high",
                                    "effect": "تنصب المضارع + مصدر مؤول", "evidence": f"تليها فعل مضارع «{after}»"})
        elif after_info and after_info.get("type") == "فعل":
            classifications.append({"type": "أنْ التفسيرية", "confidence": "medium",
                                    "evidence": "تليها فعل غير مضارع"})
            classifications.append({"type": "أنْ المخففة من أنّ", "confidence": "medium"})
        else:
            classifications.append({"type": "أنْ المخففة من أنّ", "confidence": "low"})

    # --- إنْ (broken hamza) ---
    elif stripped in ("إن",):
        if after_info and after_info.get("type") == "فعل":
            classifications.append({"type": "إنْ الشرطية الجازمة", "confidence": "high",
                                    "effect": "تجزم فعلين", "evidence": f"تليها فعل «{after}»"})
        elif after_info and after_info.get("type") == "اسم":
            classifications.append({"type": "إنْ النافية", "confidence": "medium",
                                    "evidence": "تليها اسم"})
            classifications.append({"type": "إنْ المخففة من إنّ", "confidence": "medium"})
        if not classifications:
            classifications.append({"type": "إنْ الشرطية الجازمة", "confidence": "low"})

    # --- الواو ---
    elif stripped in ("و", "وا"):
        if after_info and after_info.get("type") == "اسم" and after_info.get("subtype") == "علم":
            classifications.append({"type": "واو القسم", "confidence": "high",
                                    "effect": "حرف جر", "evidence": f"تليها اسم علم «{after}»"})
        if before_info and before_info.get("type") == "فعل" and after_info and after_info.get("subtype") == "ضمير":
            classifications.append({"type": "واو الحال", "confidence": "high",
                                    "effect": "حرف لا محل له", "evidence": "بعد فعل + تليها ضمير/جملة اسمية"})
        classifications.append({"type": "واو العطف", "confidence": "medium",
                                "effect": "حرف عطف", "evidence": "الاحتمال الأكثر شيوعاً"})
        if before_info and before_info.get("type") == "فعل":
            classifications.append({"type": "واو المعية", "confidence": "low",
                                    "effect": "ينصب ما بعدها (مفعول معه)", "evidence": "بعد فعل"})

    # --- الفاء ---
    elif stripped in ("ف", "فا"):
        if before_info and before_info.get("type") == "فعل" and before_info.get("tense") == "أمر":
            classifications.append({"type": "فاء السببية", "confidence": "high",
                                    "effect": "تنصب المضارع بعدها", "evidence": "بعد أمر/طلب"})
        classifications.append({"type": "فاء العطف", "confidence": "medium",
                                "effect": "حرف عطف (بالترتيب والتعقيب)"})
        classifications.append({"type": "فاء الاستئنافية", "confidence": "low",
                                "effect": "حرف استئناف لا محل له"})

    # --- Fallback ---
    else:
        classifications.append({"type": "غير معروف", "confidence": "low",
                                "note": f"الأداة «{particle}» غير مدعومة حالياً"})

    # Add morphological context to output
    context = {}
    if before_info:
        context["before"] = {"word": before, "type": before_info.get("type"),
                             "subtype": before_info.get("subtype"), "tense": before_info.get("tense")}
    if after_info:
        context["after"] = {"word": after, "type": after_info.get("type"),
                            "subtype": after_info.get("subtype"), "tense": after_info.get("tense"),
                            "definiteness": after_info.get("definiteness")}

    return json.dumps({
        "particle": particle,
        "classifications": classifications,
        "context": context,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def full_irab(text: str) -> str:
    """Complete deterministic i'rab analysis (all 4 passes).

    Performs Pass 1 (classification), Pass 2 (governor mapping),
    Pass 3 (case sign assignment), and Pass 4 (verification) —
    all deterministically with zero LLM calls.

    Returns per-word: grammatical role, governor, case, case sign
    (with أصلية/فرعية and تقديري detection), hidden pronouns,
    and a verification report.

    Use this as the PRIMARY tool for i'rab — it replaces manual
    Passes 1-4 entirely. Only review flagged ambiguities and
    verification issues manually.

    Args:
        text: An Arabic sentence (with or without tashkeel)
    """
    import dataclasses
    from .governor import full_irab as _full_irab, GovernorMap

    result = _full_irab(text)
    # Serialize concisely
    gov_words = []
    if result.governor_map:
        for i, w in enumerate(result.governor_map.words):
            sign = result.case_signs[i] if i < len(result.case_signs) and result.case_signs[i] else None
            entry = dataclasses.asdict(w)
            entry["case_sign"] = dataclasses.asdict(sign) if sign else None
            gov_words.append(entry)

    data = {
        "original_text": result.original_text,
        "clause_type": result.governor_map.clause_type if result.governor_map else "",
        "words": gov_words,
        "ambiguities": result.governor_map.ambiguities if result.governor_map else [],
        "verification": result.verification,
        "passed_verification": result.passed_verification,
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def map_governors(text: str) -> str:
    """Map governors (العوامل) for every word in an Arabic sentence.

    Performs Pass 1 (classification) then Pass 2 (governor mapping)
    deterministically. Returns per-word governor, grammatical role,
    expected case, and hidden pronouns. Flags ambiguous cases for
    manual review.

    Use this as the FIRST step of i'rab — it replaces manual Pass 1
    AND Pass 2 with deterministic rules. The result is a complete
    governor map ready for Pass 3 (case assignment).

    Args:
        text: An Arabic sentence (with or without tashkeel)
    """
    import dataclasses
    from .governor import map_governors as _map_governors

    result = _map_governors(text)
    # Serialize, excluding the full classification to keep output concise
    data = {
        "original_text": result.original_text,
        "clause_type": result.clause_type,
        "words": [dataclasses.asdict(w) for w in result.words],
        "ambiguities": result.ambiguities,
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def classify_sentence(text: str) -> str:
    """Perform deterministic Pass 1 classification on an Arabic sentence.

    Returns per-word classification with: type (اسم/فعل/حرف), subtype,
    tense, voice, gender, number, definiteness, مبني/معرب status, particle
    disambiguation, tashkeel (vocalized form), sentence type (اسمية/فعلية),
    and النواسخ identification.

    Use this as the FIRST step of i'rab — it replaces manual Pass 1
    classification with deterministic rules. The result is a complete
    classification table ready for Pass 2 (governor mapping).

    Args:
        text: An Arabic sentence (with or without tashkeel)
    """
    import dataclasses
    from .disambiguator import classify_sentence as _classify

    result = _classify(text)
    return json.dumps(dataclasses.asdict(result), ensure_ascii=False, indent=2)


def main():
    """Entry point for the mizan-server command."""
    mcp.run()


if __name__ == "__main__":
    main()
