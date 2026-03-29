"""
Arabic Morphological Analyzer — Pure parsing logic and data.

Wraps the Buckwalter Arabic Morphological Analyzer (via pyaramorph)
and provides structured parsing of its output. No MCP dependency.
"""

import re
import json
import os

import pyaramorph

# --- Initialization ---

analyzer = pyaramorph.Analyzer()

# Diacritics regex for stripping tashkeel from lookup keys
DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670]")

# --- Data loading ---

_data_dir = os.path.join(os.path.dirname(__file__), "..", "data")

# Qabas verb transitivity lookup
QABAS_VERBS = {}
_qabas_path = os.path.join(_data_dir, "verb_transitivity.json")
if os.path.exists(_qabas_path):
    with open(_qabas_path, encoding="utf-8") as _f:
        _qabas_data = json.load(_f)
        QABAS_VERBS = _qabas_data.get("verbs", {})

# Passive stem lookup sets from Buckwalter dictStems categories.
# PV_Pass = past passive stems, IV_Pass* = imperfect passive stems.
PV_PASS_STEMS = set()
IV_PASS_STEMS = set()
for _entries in analyzer.stems.values():
    for _entry in _entries:
        _cat, _voc = _entry[2], _entry[1]
        if "Pass" in _cat:
            if _cat.startswith("PV"):
                PV_PASS_STEMS.add(_voc)
            elif _cat.startswith("IV"):
                IV_PASS_STEMS.add(_voc)

# Feminine noun lookup (مؤنث سماعي)
FEMININE_NOUNS = set()
_fem_path = os.path.join(_data_dir, "feminine_nouns.json")
if os.path.exists(_fem_path):
    with open(_fem_path, encoding="utf-8") as _f:
        _fem_data = json.load(_f)
        FEMININE_NOUNS = set(_fem_data.get("nouns", {}).keys())

# --- POS tag mappings ---

POS_MAP = {
    "VERB_PERFECT": {"type": "فعل", "tense": "ماضٍ"},
    "VERB_IMPERFECT": {"type": "فعل", "tense": "مضارع"},
    "VERB_IMPERATIVE": {"type": "فعل", "tense": "أمر"},
    "NOUN": {"type": "اسم", "subtype": "اسم"},
    "NOUN_PROP": {"type": "اسم", "subtype": "علم"},
    "NOUN_QUANT": {"type": "اسم", "subtype": "اسم كمية"},
    "NOUN_NUM": {"type": "اسم", "subtype": "عدد"},
    "ADJ": {"type": "اسم", "subtype": "صفة"},
    "ADJ_COMP": {"type": "اسم", "subtype": "اسم تفضيل"},
    "ADJ_NUM": {"type": "اسم", "subtype": "صفة عددية"},
    "ADV": {"type": "اسم", "subtype": "ظرف"},
    "PRON": {"type": "اسم", "subtype": "ضمير"},
    "PRON_DEM": {"type": "اسم", "subtype": "اسم إشارة"},
    "PRON_REL": {"type": "اسم", "subtype": "اسم موصول"},
    "DET": {"type": "أداة", "subtype": "أل التعريف"},
    "PREP": {"type": "حرف", "subtype": "حرف جر"},
    "CONJ": {"type": "حرف", "subtype": "حرف عطف"},
    "PART": {"type": "حرف", "subtype": "حرف"},
    "INTERJ": {"type": "حرف", "subtype": "حرف"},
    "ABBREV": {"type": "اسم", "subtype": "اختصار"},
    "INTERROG": {"type": "اسم", "subtype": "اسم استفهام"},
    "REL_PRON": {"type": "اسم", "subtype": "اسم موصول"},
}

SUFFIX_MAP = {
    "PVSUFF_SUBJ:3MS": {"person": 3, "gender": "مذكر", "number": "مفرد", "desc": "هو"},
    "PVSUFF_SUBJ:3FS": {"person": 3, "gender": "مؤنث", "number": "مفرد", "desc": "هي"},
    "PVSUFF_SUBJ:3MD": {"person": 3, "gender": "مذكر", "number": "مثنى", "desc": "هما"},
    "PVSUFF_SUBJ:3FD": {"person": 3, "gender": "مؤنث", "number": "مثنى", "desc": "هما"},
    "PVSUFF_SUBJ:3MP": {"person": 3, "gender": "مذكر", "number": "جمع", "desc": "هم"},
    "PVSUFF_SUBJ:3FP": {"person": 3, "gender": "مؤنث", "number": "جمع", "desc": "هنّ"},
    "PVSUFF_SUBJ:1S": {"person": 1, "gender": None, "number": "مفرد", "desc": "أنا"},
    "PVSUFF_SUBJ:1P": {"person": 1, "gender": None, "number": "جمع", "desc": "نحن"},
    "PVSUFF_SUBJ:2MS": {"person": 2, "gender": "مذكر", "number": "مفرد", "desc": "أنتَ"},
    "PVSUFF_SUBJ:2FS": {"person": 2, "gender": "مؤنث", "number": "مفرد", "desc": "أنتِ"},
    "PVSUFF_SUBJ:2MP": {"person": 2, "gender": "مذكر", "number": "جمع", "desc": "أنتم"},
    "PVSUFF_SUBJ:2FP": {"person": 2, "gender": "مؤنث", "number": "جمع", "desc": "أنتنّ"},
    "PVSUFF_SUBJ:2D": {"person": 2, "gender": None, "number": "مثنى", "desc": "أنتما"},
    "IVSUFF_SUBJ:3MS": {"person": 3, "gender": "مذكر", "number": "مفرد", "desc": "هو"},
    "IVSUFF_SUBJ:3FS": {"person": 3, "gender": "مؤنث", "number": "مفرد", "desc": "هي"},
    "IVSUFF_SUBJ:3MD": {"person": 3, "gender": "مذكر", "number": "مثنى", "desc": "هما"},
    "IVSUFF_SUBJ:3FD": {"person": 3, "gender": "مؤنث", "number": "مثنى", "desc": "هما"},
    "IVSUFF_SUBJ:3MP": {"person": 3, "gender": "مذكر", "number": "جمع", "desc": "هم"},
    "IVSUFF_SUBJ:3FP": {"person": 3, "gender": "مؤنث", "number": "جمع", "desc": "هنّ"},
    "IVSUFF_SUBJ:1S": {"person": 1, "gender": None, "number": "مفرد", "desc": "أنا"},
    "IVSUFF_SUBJ:1P": {"person": 1, "gender": None, "number": "جمع", "desc": "نحن"},
    "IVSUFF_SUBJ:2MS": {"person": 2, "gender": "مذكر", "number": "مفرد", "desc": "أنتَ"},
    "IVSUFF_SUBJ:2FS": {"person": 2, "gender": "مؤنث", "number": "مفرد", "desc": "أنتِ"},
    "IVSUFF_SUBJ:2MP": {"person": 2, "gender": "مذكر", "number": "جمع", "desc": "أنتم"},
    "IVSUFF_SUBJ:D": {"person": None, "gender": None, "number": "مثنى", "desc": "المثنى"},
    "NSUFF_FEM_SG": {"gender": "مؤنث", "number": "مفرد"},
    "NSUFF_FEM_DU": {"gender": "مؤنث", "number": "مثنى"},
    "NSUFF_MASC_DU": {"gender": "مذكر", "number": "مثنى"},
    "NSUFF_MASC_PL": {"gender": "مذكر", "number": "جمع مذكر سالم"},
    "NSUFF_FEM_PL": {"gender": "مؤنث", "number": "جمع مؤنث سالم"},
}

# --- Morphological pattern detection ---

# Buckwalter consonants (non-vowel, non-diacritic characters)
_BUCK_CONSONANTS = set("btjHxd*rzs$SDTZEgfqklmnhwy'>|}&<}")
_BUCK_VOWELS = set("aiu")


def _extract_root_consonants(buck_stem: str) -> str | None:
    """Extract root consonants from a Buckwalter stem, stripping known affixes.

    Returns a Buckwalter consonantal string (e.g., 'ktb') or None.
    """
    if not buck_stem:
        return None
    # Strip common derivational prefixes: m (مَفْعَل), t (تَفْعيل), {i/in/ist (Forms VII/VIII/X)
    s = buck_stem
    # Form X: various representations of ist- prefix
    # Buckwalter uses {isot, Aisot, isot, {ist, Aist, ist, etc.
    stripped = False
    for pfx in ("{isot", "Aisot", "isot", "{ist", "Aist", "ist"):
        if s.startswith(pfx):
            s = s[len(pfx):]
            stripped = True
            break
    if not stripped:
        # Form VII/VIII: in/it prefix
        if s.startswith(("{in", "Ain", "{it", "Ait")):
            s = s[3:]
        elif s.startswith(("in",)):
            s = s[2:]
        # Form IV: >a/Oa prefix
        elif s.startswith((">a", "Oa")):
            s = s[2:]
        # Form V/VI: ta prefix
        elif s.startswith("ta") and len(s) > 4:
            s = s[2:]
        # Noun prefixes: mu (مُـ), ma (مَـ)
        elif s.startswith(("mu", "ma")) and len(s) > 4:
            s = s[2:]

    # Remove known pattern vowel-letters before extracting consonants:
    # مفعول has 'uw' (واو المد) — not a root letter
    # تفعيل has 'iy' (ياء المد) — not a root letter
    # فعال has 'A' (ألف المد) — not a root letter in this context
    s = s.replace("uw", "").replace("iy", "")

    consonants = [c for c in s if c in _BUCK_CONSONANTS]
    # Handle shadda: doubled consonant counts once
    deduped = []
    for c in consonants:
        if not deduped or c != deduped[-1]:
            deduped.append(c)

    if len(deduped) >= 3:
        return "".join(deduped[:3])
    return "".join(deduped) if deduped else None


def _detect_pattern(buck_stem: str, pos_tag: str) -> str | None:
    """Detect Arabic morphological pattern (وزن) from Buckwalter vocalized stem.

    Returns pattern label or None.
    """
    if not buck_stem:
        return None

    s = buck_stem
    consonants = [c for c in s if c in _BUCK_CONSONANTS]

    # Active participle: فَاعِل pattern (CACiC)
    if len(s) >= 4 and len(consonants) >= 3:
        # fACiC / CACiC pattern
        if s[1:2] == "A" and "i" in s:
            idx_a = s.index("A")
            rest = s[idx_a + 1:]
            if rest and "i" in rest:
                return "فاعل"

    # Passive participle: مَفْعُول pattern (maCCuwC)
    if s.startswith("ma") and "uw" in s:
        return "مفعول"

    # Masdar of Form II: تَفْعِيل (taCCiyC / taC~iyC)
    if s.startswith("ta") and ("iy" in s or "~" in s):
        if "~" in s and "iy" not in s:
            pass  # Form V verb, not masdar
        elif "iy" in s:
            return "تفعيل"

    # Elative/comparative: أَفْعَل (>aCCaC)
    if (s.startswith(">a") or s.startswith("Oa")) and len(consonants) >= 3:
        if pos_tag in ("NOUN", "ADJ", "ADJ_COMP"):
            return "أفعل"

    # مَفْعَل / مَفْعِل place noun
    if s.startswith("ma") and len(consonants) >= 3 and "uw" not in s:
        if pos_tag in ("NOUN",):
            return "مفعل"

    # فِعَالَة masdar of Form I (CiCAC / CiCACap)
    if len(consonants) >= 3 and len(s) >= 5:
        if s[1:2] == "i" and "A" in s[2:]:
            if pos_tag in ("NOUN",):
                return "فعالة"

    return None


def _is_diptote(buck_stem: str, pos_tag: str, pattern: str | None) -> bool:
    """Detect if a noun is ممنوع من الصرف (diptote).

    Common diptote categories:
    - Proper nouns (NOUN_PROP) that are foreign or feminine
    - أفعل comparative/superlative pattern
    - صيغة منتهى الجموع (broken plurals on مَفاعِل/مَفاعِيل pattern)
    """
    if pos_tag == "NOUN_PROP":
        return True
    if pattern == "أفعل" and pos_tag in ("ADJ", "ADJ_COMP", "NOUN"):
        return True
    # صيغة منتهى الجموع: maCACiC / maCACiyC pattern
    if buck_stem and buck_stem.startswith("ma") and len(buck_stem) >= 6:
        # Check for مَفاعِل (maCACiC) or مَفاعِيل (maCACiyC)
        inner = buck_stem[2:]
        if "A" in inner and ("i" in inner[inner.index("A"):] if "A" in inner else False):
            return True
    return False


# --- Functions ---


def detect_verb_form(buck: str) -> str:
    """Detect Arabic verb form (I-X) from Buckwalter transliteration.

    Args:
        buck: Buckwalter ASCII transliteration of the vocalized verb form.

    Returns:
        Form as Roman numeral string: "I" through "X".
    """
    has_shadda = "~" in buck
    if buck.startswith("ta") and len(buck) > 5:
        if has_shadda:  # taCaC~aCa = Form V
            return "V"
        else:
            return "VI"  # taCACaCa
    elif buck.startswith(">a") or buck.startswith("Oa"):
        return "IV"  # >aCCaCa
    elif buck.startswith("Ais") or buck.startswith("is") or buck.startswith("{is"):
        return "X"  # istaCCaCa
    elif (buck.startswith("Ai") or buck.startswith("i") or buck.startswith("{i")) and len(buck) > 4:
        rest = buck[2:] if buck.startswith(("Ai", "{i")) else buck[1:]
        if rest.startswith("n"):
            return "VII"  # inCaCaCa
        elif len(rest) > 1 and rest[-1] == rest[-2]:
            return "IX"  # iCCaCC — doubled final
        else:
            return "VIII"  # iCtaCaCa
    elif has_shadda:
        return "II"  # CaC~aCa
    elif len(buck) > 3 and buck[1] == "A":
        return "III"  # CACaCa
    return "I"


def lookup_transitivity(vocalized: str) -> tuple[str, str] | None:
    """Look up verb transitivity from Qabas lexical data.

    Args:
        vocalized: Arabic vocalized verb form (with or without diacritics).

    Returns:
        (transitivity, source) tuple, or None if not found.
        transitivity is "متعد" or "لازم", source is "qabas".
    """
    if not QABAS_VERBS or not vocalized:
        return None
    stripped = DIACRITICS_RE.sub("", vocalized)
    entry = QABAS_VERBS.get(stripped)
    if entry:
        return (entry["transitivity"], "qabas")
    return None


def parse_solution(solution_text: str) -> dict:
    """Parse a single Buckwalter analysis solution into structured data."""
    result = {
        "vocalized": None,
        "lemma": None,
        "root": None,           # #1: trilateral root (الجذر)
        "pattern": None,        # #2: morphological pattern (الوزن)
        "pos_raw": None,
        "gloss": None,
        "type": None,
        "subtype": None,
        "tense": None,
        "voice": None,
        "mood": None,           # #6: verb mood (مرفوع/منصوب/مجزوم)
        "gender": None,
        "number": None,
        "definiteness": None,
        "diptote": None,        # #4: ممنوع من الصرف
        "noun_class": None,     # #7/#8: participle/masdar classification
        "prefixes": [],
        "suffixes": [],
        "subject_suffix": None,
    }

    verb_buck_stem = None
    noun_buck_stem = None
    main_pos_tag = None
    has_subjunc = False

    lines = solution_text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith("solution:"):
            m = re.search(r'\(([^)]+)\)\s+\[([^\]]+)\]', line)
            if m:
                result["vocalized"] = m.group(1).split()[0]
                raw_lemma = m.group(2)
                bare = raw_lemma.split("_")[0].split("-")[0]
                result["lemma"] = pyaramorph.buckwalter.buck2uni(bare)
        elif line.startswith("pos:"):
            pos_str = line.replace("pos:", "").strip()
            result["pos_raw"] = pos_str

            # #6: detect SUBJUNC prefix for mood
            if "/SUBJUNC" in pos_str:
                has_subjunc = True

            parts = pos_str.split("+")
            for part in parts:
                stem_part = part.split("/")
                if len(stem_part) == 2:
                    tag = stem_part[1]
                    for key, val in POS_MAP.items():
                        if tag == key or tag.startswith(key):
                            result["type"] = val["type"]
                            if "subtype" in val:
                                result["subtype"] = val["subtype"]
                            if "tense" in val:
                                result["tense"] = val["tense"]
                            if tag in ("VERB_PERFECT", "VERB_IMPERFECT"):
                                verb_buck_stem = stem_part[0]
                            if tag == "VERB_IMPERFECT":
                                main_pos_tag = tag
                            # Capture noun/adj stem for pattern detection
                            if tag in ("NOUN", "NOUN_PROP", "NOUN_QUANT",
                                       "NOUN_NUM", "ADJ", "ADJ_COMP", "ADJ_NUM"):
                                noun_buck_stem = stem_part[0]
                                main_pos_tag = tag
                    for key, val in SUFFIX_MAP.items():
                        if tag == key:
                            result["subject_suffix"] = val
                            if "gender" in val and val["gender"]:
                                result["gender"] = val["gender"]
                            if "number" in val:
                                result["number"] = val["number"]
                    for key, val in SUFFIX_MAP.items():
                        if tag == key and key.startswith("NSUFF"):
                            if "gender" in val:
                                result["gender"] = val["gender"]
                            if "number" in val:
                                result["number"] = val["number"]
                    if tag == "DET":
                        result["definiteness"] = "معرفة"
                        result["prefixes"].append("أل")
                    if tag in ("PREP",):
                        result["prefixes"].append(stem_part[0])

        elif line.startswith("gloss:"):
            gloss_str = line.replace("gloss:", "").strip()
            parts = [p.strip() for p in gloss_str.split("+") if p.strip() != "___"]
            result["gloss"] = " + ".join(parts) if parts else None

    # --- #5: Voice detection (improved) ---
    if result["type"] == "فعل" and verb_buck_stem:
        if result["tense"] == "ماضٍ":
            if verb_buck_stem in PV_PASS_STEMS:
                result["voice"] = "مبني للمجهول"
            else:
                voc = result.get("vocalized", "")
                if voc:
                    try:
                        buck = pyaramorph.buckwalter.uni2buck(voc)
                    except Exception:
                        buck = ""
                    s = buck.lstrip("{>AOiI")
                    vowel_seq = [c for c in s if c in "aui"]
                    # Passive: u...i (Form I) or u...a (Form IV+)
                    if len(vowel_seq) >= 2 and vowel_seq[0] == "u":
                        if "i" in vowel_seq[1:] or "a" in vowel_seq[1:]:
                            result["voice"] = "مبني للمجهول"
                        else:
                            result["voice"] = "مبني للمعلوم"
                    else:
                        result["voice"] = "مبني للمعلوم"
                else:
                    result["voice"] = "مبني للمعلوم"
        elif result["tense"] == "مضارع":
            if verb_buck_stem in IV_PASS_STEMS:
                result["voice"] = "مبني للمجهول"
            else:
                # #5: Improved fallback — check prefix vowel pattern
                # Passive imperfect has 'u' after prefix consonant (yu- vs ya-)
                pos_raw = result.get("pos_raw", "")
                if pos_raw:
                    # Look for yu/tu/nu/etc. prefix indicating passive
                    prefix_match = re.search(r'(\w+)/IV\d', pos_raw)
                    if prefix_match:
                        pfx = prefix_match.group(1)
                        if pfx.endswith("u"):
                            result["voice"] = "مبني للمجهول"
                        else:
                            result["voice"] = "مبني للمعلوم"
                    else:
                        result["voice"] = "مبني للمعلوم"
                else:
                    result["voice"] = "مبني للمعلوم"
        elif result["tense"] == "أمر":
            result["voice"] = "مبني للمعلوم"

    # --- #6: Mood detection ---
    if result["type"] == "فعل" and result["tense"] == "مضارع":
        if has_subjunc:
            result["mood"] = "منصوب"
        else:
            # Default: indicative (مرفوع). Jussive (مجزوم) requires
            # sentence-level context (لم، لمّا، etc.) not available here.
            result["mood"] = "مرفوع"

    # --- #1: Root extraction ---
    stem_for_root = verb_buck_stem or noun_buck_stem
    if stem_for_root:
        root_buck = _extract_root_consonants(stem_for_root)
        if root_buck:
            try:
                result["root"] = pyaramorph.buckwalter.buck2uni(root_buck)
            except Exception:
                pass

    # --- #2: Pattern detection & #7/#8: Participle/masdar classification ---
    if result["type"] == "اسم" and noun_buck_stem and main_pos_tag:
        pattern = _detect_pattern(noun_buck_stem, main_pos_tag)
        result["pattern"] = pattern

        # #7: Participle detection
        if pattern == "فاعل":
            result["noun_class"] = "اسم فاعل"
        elif pattern == "مفعول":
            result["noun_class"] = "اسم مفعول"
        # #8: Masdar detection
        elif pattern == "تفعيل":
            result["noun_class"] = "مصدر"
        elif pattern == "فعالة":
            result["noun_class"] = "مصدر"
        elif pattern == "أفعل" and main_pos_tag in ("ADJ", "ADJ_COMP"):
            result["noun_class"] = "اسم تفضيل"

        # #4: Diptote detection
        result["diptote"] = _is_diptote(noun_buck_stem, main_pos_tag, pattern)

    # --- #3: Broken plural detection (via number field) ---
    # If number was set by NSUFF_FEM_PL/NSUFF_MASC_PL → sound plural (already handled)
    # If number not set and word is a noun, check stem category for plural patterns
    if result["type"] == "اسم" and not result["number"]:
        result["number"] = "مفرد"
    # Detect broken plural: if a noun has no explicit plural suffix but its
    # gloss or stem category suggests plural, mark it
    if result["type"] == "اسم" and result["number"] == "مفرد":
        # Buckwalter glosses for plurals often contain plural indicators
        if noun_buck_stem:
            # Check if this stem is in the stems dict as a plural category
            stripped = "".join(c for c in noun_buck_stem if c not in "aeiou~oFNK")
            if stripped in analyzer.stems:
                for entry in analyzer.stems[stripped]:
                    if entry[1] == noun_buck_stem:
                        cat = entry[2]
                        # Ndip = broken plural, NAt = sound fem plural
                        if "dip" in cat.lower() or cat == "Ndip":
                            result["number"] = "جمع تكسير"
                            break

    # Default gender: check مؤنث سماعي list before defaulting to مذكر
    if result["type"] == "اسم" and not result["gender"]:
        voc = result.get("vocalized", "")
        bare = DIACRITICS_RE.sub("", voc) if voc else ""
        if bare and bare in FEMININE_NOUNS:
            result["gender"] = "مؤنث"
        else:
            result["gender"] = "مذكر"

    return result
