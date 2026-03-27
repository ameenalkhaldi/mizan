"""
Arabic Verb Conjugation (تصريف)

Generates full conjugation tables for Arabic verbs using Buckwalter stems
from pyaramorph and deterministic suffix/prefix rules.
"""

import re

import pyaramorph

from .analyzer import analyzer, parse_solution, detect_verb_form, DIACRITICS_RE, _extract_root_consonants


# --- Person definitions ---

PERSONS = [
    {"key": "3MS", "label_ar": "هو", "label_en": "he"},
    {"key": "3FS", "label_ar": "هي", "label_en": "she"},
    {"key": "3MD", "label_ar": "هما (م)", "label_en": "they two (m.)"},
    {"key": "3FD", "label_ar": "هما (ف)", "label_en": "they two (f.)"},
    {"key": "3MP", "label_ar": "هم", "label_en": "they (m.)"},
    {"key": "3FP", "label_ar": "هنّ", "label_en": "they (f.)"},
    {"key": "2MS", "label_ar": "أنتَ", "label_en": "you (m.)"},
    {"key": "2FS", "label_ar": "أنتِ", "label_en": "you (f.)"},
    {"key": "2D", "label_ar": "أنتما", "label_en": "you two"},
    {"key": "2MP", "label_ar": "أنتم", "label_en": "you all (m.)"},
    {"key": "2FP", "label_ar": "أنتنّ", "label_en": "you all (f.)"},
    {"key": "1S", "label_ar": "أنا", "label_en": "I"},
    {"key": "1P", "label_ar": "نحن", "label_en": "we"},
]

IMPERATIVE_PERSONS = [
    {"key": "2MS", "label_ar": "أنتَ", "label_en": "you (m.)"},
    {"key": "2FS", "label_ar": "أنتِ", "label_en": "you (f.)"},
    {"key": "2D", "label_ar": "أنتما", "label_en": "you two"},
    {"key": "2MP", "label_ar": "أنتم", "label_en": "you all (m.)"},
    {"key": "2FP", "label_ar": "أنتنّ", "label_en": "you all (f.)"},
]

# Past tense suffixes (appended to PV stem)
PAST_SUFFIXES = {
    "3MS": "a",
    "3FS": "at",
    "3MD": "A",
    "3FD": "atA",
    "3MP": "uwA",
    "3FP": "ona",
    "2MS": "ota",
    "2FS": "oti",
    "2D": "otumA",
    "2MP": "otum",
    "2FP": "otun~a",
    "1S": "otu",
    "1P": "onA",
}

# Imperfect tense prefixes and suffixes (wrap IV stem)
IMPERFECT_ACTIVE_PREFIXES = {
    "3MS": "ya", "3FS": "ta", "3MD": "ya", "3FD": "ta",
    "3MP": "ya", "3FP": "ya",
    "2MS": "ta", "2FS": "ta", "2D": "ta", "2MP": "ta", "2FP": "ta",
    "1S": ">a", "1P": "na",
}

IMPERFECT_PASSIVE_PREFIXES = {
    "3MS": "yu", "3FS": "tu", "3MD": "yu", "3FD": "tu",
    "3MP": "yu", "3FP": "yu",
    "2MS": "tu", "2FS": "tu", "2D": "tu", "2MP": "tu", "2FP": "tu",
    "1S": ">u", "1P": "nu",
}

IMPERFECT_SUFFIXES = {
    "3MS": "u",
    "3FS": "u",
    "3MD": "Ani",
    "3FD": "Ani",
    "3MP": "uwna",
    "3FP": "ona",
    "2MS": "u",
    "2FS": "iyna",
    "2D": "Ani",
    "2MP": "uwna",
    "2FP": "ona",
    "1S": "u",
    "1P": "u",
}

# Subjunctive (منصوب) suffixes — after أنْ، لن، كي، etc.
SUBJUNCTIVE_SUFFIXES = {
    "3MS": "a",
    "3FS": "a",
    "3MD": "A",        # حذف النون
    "3FD": "A",
    "3MP": "uwA",      # حذف النون
    "3FP": "ona",      # same as indicative
    "2MS": "a",
    "2FS": "iy",       # حذف النون
    "2D": "A",
    "2MP": "uwA",
    "2FP": "ona",      # same as indicative
    "1S": "a",
    "1P": "a",
}

# Jussive (مجزوم) suffixes — after لم، لمّا، لام الأمر، لا الناهية
JUSSIVE_SUFFIXES = {
    "3MS": "",          # sukun (implicit)
    "3FS": "",
    "3MD": "A",         # حذف النون
    "3FD": "A",
    "3MP": "uwA",       # حذف النون
    "3FP": "ona",       # same as indicative
    "2MS": "",
    "2FS": "iy",        # حذف النون
    "2D": "A",
    "2MP": "uwA",
    "2FP": "ona",       # same as indicative
    "1S": "",
    "1P": "",
}

# Imperative suffixes (appended to imperative stem)
IMPERATIVE_SUFFIXES = {
    "2MS": "",
    "2FS": "iy",
    "2D": "A",
    "2MP": "uwA",
    "2FP": "ona",
}

# --- Participle and masdar patterns by verb form ---

# Active participle pattern: Form → (prefix, infix_pattern)
# Applied to the 3 root consonants C1, C2, C3
ACTIVE_PARTICIPLE = {
    "I":    ("", "A{C2}i{C3}"),        # فَاعِل: C1AC2iC3
    "II":   ("mu", "a{C2}~i{C3}"),    # مُفَعِّل: muC1aC2~iC3
    "III":  ("mu", "A{C2}i{C3}"),     # مُفَاعِل: muC1AC2iC3
    "IV":   ("mu", "o{C2}i{C3}"),     # مُفْعِل: muC1oC2iC3
    "V":    ("muta", "a{C2}~i{C3}"),  # مُتَفَعِّل: mutaC1aC2~iC3
    "VI":   ("muta", "A{C2}i{C3}"),   # مُتَفَاعِل: mutaC1AC2iC3
    "VII":  ("mun", "a{C2}i{C3}"),    # مُنْفَعِل: munC1aC2iC3
    "VIII": ("mu", "ota{C2}i{C3}"),   # مُفْتَعِل: muC1otaC2iC3
    "X":    ("musota", "o{C2}i{C3}"), # مُسْتَفْعِل: musotaC1oC2iC3
}

# Passive participle pattern
PASSIVE_PARTICIPLE = {
    "I":    ("ma", "o{C2}uw{C3}"),     # مَفْعُول: maC1oC2uwC3
    "II":   ("mu", "a{C2}~a{C3}"),    # مُفَعَّل: muC1aC2~aC3
    "III":  ("mu", "A{C2}a{C3}"),     # مُفَاعَل: muC1AC2aC3
    "IV":   ("mu", "o{C2}a{C3}"),     # مُفْعَل: muC1oC2aC3
    "V":    ("muta", "a{C2}~a{C3}"),  # مُتَفَعَّل: mutaC1aC2~aC3
    "VI":   ("muta", "A{C2}a{C3}"),   # مُتَفَاعَل: mutaC1AC2aC3
    "VII":  ("mun", "a{C2}a{C3}"),    # مُنْفَعَل: munC1aC2aC3
    "VIII": ("mu", "ota{C2}a{C3}"),   # مُفْتَعَل: muC1otaC2aC3
    "X":    ("musota", "o{C2}a{C3}"), # مُسْتَفْعَل: musotaC1oC2aC3
}

# Masdar patterns (Forms II-X are regular; Form I is irregular per verb)
MASDAR_PATTERNS = {
    "II":   ("ta", "o{C2}iy{C3}"),       # تَفْعِيل: taC1oC2iyC3
    "III":  ("mu", "A{C2}a{C3}ap"),      # مُفَاعَلَة: muC1AC2aCap
    "IV":   ("<i", "o{C2}A{C3}"),        # إِفْعَال: <iC1oC2AC3
    "V":    ("ta", "a{C2}~u{C3}"),       # تَفَعُّل: taC1aC2~uC3
    "VI":   ("ta", "A{C2}u{C3}"),        # تَفَاعُل: taC1AC2uC3
    "VII":  ("Ain", "i{C2}A{C3}"),       # اِنْفِعَال: AinC1iC2AC3
    "VIII": ("Ai", "oti{C2}A{C3}"),      # اِفْتِعَال: AiC1otiC2AC3
    "X":    ("Aisoti", "o{C2}A{C3}"),    # اِسْتِفْعَال: AisotiC1oC2AC3
}


def _find_stems(verb: str) -> dict | None:
    """Find all verb stems (PV, IV, PV_Pass, IV_Pass, CV) for a given verb.

    Analyzes the verb to find its lemma ID, then searches the Buckwalter
    stem database for all related stem entries.

    Returns dict with keys: lemma_id, gloss, form, PV, IV, PV_Pass, IV_Pass, CV
    or None if the verb is not found.
    """
    results = analyzer.analyze_text(verb)
    if not results:
        return None

    # Find a verb reading and extract lemma ID
    lemma_id = None
    gloss = None
    form = "I"
    for sol_text in results[0][1:]:
        parsed = parse_solution(sol_text)
        if parsed["type"] != "فعل":
            continue

        # Extract raw lemma ID from solution line
        for line in sol_text.strip().split("\n"):
            line = line.strip()
            if line.startswith("solution:"):
                m = re.search(r'\[([^\]]+)\]', line)
                if m:
                    lemma_id = m.group(1)
                break

        gloss = parsed.get("gloss")

        # Detect verb form
        voc = parsed.get("vocalized", "")
        if voc:
            try:
                buck = pyaramorph.buckwalter.uni2buck(voc)
                form = detect_verb_form(buck)
            except Exception:
                pass

        if lemma_id:
            break

    if not lemma_id:
        return None

    # Search all stems for entries matching this lemma ID
    stems = {"PV": None, "IV": None, "PV_Pass": None, "IV_Pass": None, "CV": None}
    for entries in analyzer.stems.values():
        for entry in entries:
            if entry[5] != lemma_id:
                continue
            cat = entry[2]
            voc = entry[1]
            is_pv = cat.startswith("PV")
            is_iv = cat.startswith("IV")
            is_cv = cat.startswith("CV")
            is_pass = "Pass" in cat
            if is_pv and not is_pass and stems["PV"] is None:
                stems["PV"] = voc
            elif is_iv and not is_pass and stems["IV"] is None:
                stems["IV"] = voc
            elif is_pv and is_pass and stems["PV_Pass"] is None:
                stems["PV_Pass"] = voc
            elif is_iv and is_pass and stems["IV_Pass"] is None:
                stems["IV_Pass"] = voc
            elif is_cv and stems["CV"] is None:
                stems["CV"] = voc

    if not stems["PV"] and not stems["IV"]:
        return None

    return {
        "lemma_id": lemma_id,
        "gloss": gloss,
        "form": form,
        **stems,
    }


def _make_imperative_stem(iv_stem: str, cv_stem: str | None) -> str | None:
    """Derive the imperative stem from the IV (imperfect) stem.

    If a CV (command verb) stem exists in the database, use it directly.
    Otherwise, derive from IV stem by adding hamza wasl if the stem starts
    with a consonant cluster.
    """
    if cv_stem:
        # Replace hamza wasl '{' with bare alif 'A' for buck2uni compatibility
        return cv_stem.replace("{", "A")

    if not iv_stem:
        return None

    # Check if stem starts with a consonant cluster (second char is sukun 'o')
    if len(iv_stem) >= 2 and iv_stem[1] == "o":
        # Need hamza wasl — determine its vowel
        # Find the characteristic vowel (vowel of the middle radical)
        vowels = [c for c in iv_stem if c in "aiu"]
        # If the main vowel is 'u', hamza wasl gets damma; otherwise kasra
        # Use 'A' (bare alif) since buck2uni doesn't map '{' (hamza wasl)
        hamza_vowel = "u" if vowels and vowels[-1] == "u" else "i"
        return "A" + hamza_vowel + iv_stem
    else:
        # Stem starts with consonant+vowel (e.g., Form V takat~ab) — no hamza wasl
        return iv_stem


def _generate_forms(stem: str, person_suffixes: dict, prefix_map: dict | None = None) -> list[dict]:
    """Generate conjugated forms for all persons.

    Args:
        stem: Buckwalter vocalized stem
        person_suffixes: dict mapping person key to suffix string
        prefix_map: optional dict mapping person key to prefix string (for imperfect)

    Returns:
        List of dicts with person info and conjugated Arabic form.
    """
    person_list = IMPERATIVE_PERSONS if prefix_map is None and len(person_suffixes) == 5 else PERSONS
    forms = []
    for person in person_list:
        key = person["key"]
        if key not in person_suffixes:
            continue
        prefix = prefix_map[key] if prefix_map else ""
        suffix = person_suffixes[key]
        buck = prefix + stem + suffix
        arabic = pyaramorph.buckwalter.buck2uni(buck)
        forms.append({
            "person": key,
            "label_ar": person["label_ar"],
            "label_en": person["label_en"],
            "arabic": arabic,
            "buckwalter": buck,
        })
    return forms


def _derive_form(root_buck: str, form: str, pattern_table: dict) -> str | None:
    """Generate a derived noun (participle/masdar) from root consonants and verb form.

    Args:
        root_buck: 3 Buckwalter root consonants (e.g., 'ktb')
        form: Verb form as Roman numeral
        pattern_table: One of ACTIVE_PARTICIPLE, PASSIVE_PARTICIPLE, MASDAR_PATTERNS

    Returns:
        Arabic string or None if pattern not available.
    """
    if form not in pattern_table or len(root_buck) < 3:
        return None

    c1, c2, c3 = root_buck[0], root_buck[1], root_buck[2]
    prefix, template = pattern_table[form]

    # Replace placeholders
    buck = prefix + c1 + template.format(C2=c2, C3=c3)
    try:
        return pyaramorph.buckwalter.buck2uni(buck)
    except Exception:
        return None


def conjugate(verb: str) -> dict:
    """Generate full conjugation table for an Arabic verb.

    Returns structured dict with past, imperfect, and imperative sections,
    each containing active and (where available) passive forms.
    """
    stem_info = _find_stems(verb)
    if not stem_info:
        return {"verb": verb, "error": "Verb not found in database"}

    form = stem_info["form"]

    result = {
        "verb": verb,
        "lemma_id": stem_info["lemma_id"],
        "gloss": stem_info["gloss"],
        "form": form,
        "past": {"active": [], "passive": []},
        "imperfect": {"active": [], "passive": []},
        "subjunctive": {"active": [], "passive": []},
        "jussive": {"active": [], "passive": []},
        "imperative": [],
        "active_participle": None,
        "passive_participle": None,
        "masdar": None,
    }

    # Past tense — active
    if stem_info["PV"]:
        result["past"]["active"] = _generate_forms(
            stem_info["PV"], PAST_SUFFIXES
        )

    # Past tense — passive
    if stem_info["PV_Pass"]:
        result["past"]["passive"] = _generate_forms(
            stem_info["PV_Pass"], PAST_SUFFIXES
        )

    # Imperfect indicative (مرفوع) — active
    if stem_info["IV"]:
        result["imperfect"]["active"] = _generate_forms(
            stem_info["IV"], IMPERFECT_SUFFIXES, IMPERFECT_ACTIVE_PREFIXES
        )
        # #9: Subjunctive (منصوب)
        result["subjunctive"]["active"] = _generate_forms(
            stem_info["IV"], SUBJUNCTIVE_SUFFIXES, IMPERFECT_ACTIVE_PREFIXES
        )
        # #10: Jussive (مجزوم)
        result["jussive"]["active"] = _generate_forms(
            stem_info["IV"], JUSSIVE_SUFFIXES, IMPERFECT_ACTIVE_PREFIXES
        )

    # Imperfect — passive (all three moods)
    if stem_info["IV_Pass"]:
        result["imperfect"]["passive"] = _generate_forms(
            stem_info["IV_Pass"], IMPERFECT_SUFFIXES, IMPERFECT_PASSIVE_PREFIXES
        )
        result["subjunctive"]["passive"] = _generate_forms(
            stem_info["IV_Pass"], SUBJUNCTIVE_SUFFIXES, IMPERFECT_PASSIVE_PREFIXES
        )
        result["jussive"]["passive"] = _generate_forms(
            stem_info["IV_Pass"], JUSSIVE_SUFFIXES, IMPERFECT_PASSIVE_PREFIXES
        )

    # Imperative (active only, 5 forms)
    imp_stem = _make_imperative_stem(stem_info["IV"], stem_info["CV"])
    if imp_stem:
        result["imperative"] = _generate_forms(
            imp_stem, IMPERATIVE_SUFFIXES
        )

    # #12: Participles — derive from root consonants
    pv_stem = stem_info["PV"]
    if pv_stem:
        root_buck = _extract_root_consonants(pv_stem)
        if root_buck and len(root_buck) >= 3:
            result["active_participle"] = _derive_form(root_buck, form, ACTIVE_PARTICIPLE)
            result["passive_participle"] = _derive_form(root_buck, form, PASSIVE_PARTICIPLE)
            # #11: Masdar (Forms II-X only; Form I is irregular)
            result["masdar"] = _derive_form(root_buck, form, MASDAR_PATTERNS)

    return result
