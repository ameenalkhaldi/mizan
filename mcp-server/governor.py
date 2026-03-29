"""
Deterministic Pass 2-4 for Arabic i'rab analysis.

- Pass 2 (العوامل): Governor mapping — assigns عامل to every word
- Pass 3 (الإعراب): Case sign assignment — lookup (case, morph_class) → sign
- Pass 4 (المراجعة): Verification — 6-point constraint checker

Entry points:
  map_governors(text) -> GovernorMap      (Pass 1+2)
  full_irab(text) -> IrabResult           (Pass 1+2+3+4)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from disambiguator import (
    classify_sentence,
    SentenceClassification,
    WordClassification,
    _strip,
    STANDALONE_PREPOSITIONS,
)

# ---------------------------------------------------------------------------
# Section 1: Data structures
# ---------------------------------------------------------------------------


@dataclass
class GovernorAssignment:
    """Governor assignment for a single word."""

    word: str
    word_index: int
    role: str = ""                   # "فاعل" | "مبتدأ" | "خبر" | "مفعول به" | etc.
    governor: str | None = None      # The word/concept governing this word's case
    governor_index: int | None = None  # Index of governing word (-1 for abstract)
    case: str | None = None          # "رفع" | "نصب" | "جر" | "جزم" | None
    confidence: str = "high"         # "high" | "medium" | "low"
    hidden_pronoun: dict | None = None  # {"type": "مستتر", "estimate": "هو", "obligatory": "وجوباً"}


@dataclass
class GovernorMap:
    """Full Pass 2 result for a sentence."""

    original_text: str = ""
    clause_type: str = ""
    words: list[GovernorAssignment] = field(default_factory=list)
    ambiguities: list[dict] = field(default_factory=list)
    classification: SentenceClassification | None = None


@dataclass
class CaseSign:
    """Case sign (علامة الإعراب) for a single word — Pass 3 output."""

    sign: str = ""                   # "الضمة" | "الفتحة" | "الواو" | "حذف النون" | etc.
    sign_type: str = ""              # "أصلية" | "فرعية"
    estimated: bool = False          # True if إعراب تقديري
    estimated_reason: str | None = None  # "التعذر" | "الثقل" | "اشتغال المحل"
    note: str | None = None          # "بلا تنوين" | "نيابة عن الكسرة" | etc.


@dataclass
class IrabResult:
    """Complete i'rab analysis for a sentence (all 4 passes)."""

    original_text: str = ""
    governor_map: GovernorMap | None = None
    case_signs: list[CaseSign | None] = field(default_factory=list)
    verification: list[dict] = field(default_factory=list)
    passed_verification: bool = True


# ---------------------------------------------------------------------------
# Section 2: Constants
# ---------------------------------------------------------------------------

# عطف particles
ATF_PARTICLES: frozenset[str] = frozenset({
    "و", "ف", "ثم", "ثمّ", "أو", "أم", "بل", "لا", "لكن", "حتى",
})

# توكيد معنوي words
TAWKEED_WORDS: frozenset[str] = frozenset({
    "نفس", "عين", "كل", "جميع", "كلا", "كلتا", "أجمع", "أجمعين",
})

# ضمير مستتر rules: (tense, person, number[, gender]) -> (estimate, obligatory)
# وجوباً cases
HIDDEN_PRONOUN_WUJOOB: dict[tuple, tuple[str, str]] = {
    # أنا forms — 1st person singular
    ("مضارع", 1, "مفرد"): ("أنا", "وجوباً"),
    # نحن forms — 1st person plural
    ("مضارع", 1, "جمع"): ("نحن", "وجوباً"),
    # أنتَ — 2nd person masc sing imperative
    ("أمر", 2, "مفرد"): ("أنتَ", "وجوباً"),
}

# جوازاً cases
HIDDEN_PRONOUN_JAWAZ: dict[tuple, tuple[str, str]] = {
    # هو — 3rd person masc sing
    ("ماضٍ", 3, "مفرد", "مذكر"): ("هو", "جوازاً"),
    ("مضارع", 3, "مفرد", "مذكر"): ("هو", "جوازاً"),
    # هي — 3rd person fem sing
    ("ماضٍ", 3, "مفرد", "مؤنث"): ("هي", "جوازاً"),
    ("مضارع", 3, "مفرد", "مؤنث"): ("هي", "جوازاً"),
    # أنتَ — 2nd person masc sing present
    ("مضارع", 2, "مفرد", "مذكر"): ("أنتَ", "وجوباً"),
    # أنتِ — 2nd person fem sing present
    ("مضارع", 2, "مفرد", "مؤنث"): ("أنتِ", "وجوباً"),
}

# النواسخ الحرفية (particles that act as governors)
NAWASIKH_HUROOF_SET: frozenset[str] = frozenset({
    "إنّ", "إن", "أنّ", "أن", "كأنّ", "كأن",
    "لكنّ", "لكن", "ليت", "لعلّ", "لعل",
})


# ---------------------------------------------------------------------------
# Section 3: Positional governor rules
# ---------------------------------------------------------------------------


def _find_next_noun(words: list[WordClassification], start: int) -> int | None:
    """Find the index of the next noun after position start."""
    for i in range(start, len(words)):
        if words[i].word_type == "اسم":
            return i
    return None


def _find_next_noun_or_adj(words: list[WordClassification], start: int) -> int | None:
    """Find the next noun or adjective after position start."""
    for i in range(start, len(words)):
        if words[i].word_type == "اسم":
            return i
    return None


def _is_prep(wc: WordClassification) -> bool:
    """Check if word is a preposition."""
    s = _strip(wc.word)
    return (
        wc.subtype == "حرف جر"
        or s in STANDALONE_PREPOSITIONS
    )


def _assign_verbal_sentence(
    words: list[WordClassification],
    assignments: list[GovernorAssignment],
    verb_idx: int,
    nawasikh_type: str | None = None,
) -> set[int]:
    """Assign governors for a verbal sentence pattern (فعل + فاعل + مفعول).

    Returns set of indices that were assigned.
    """
    assigned: set[int] = set()
    verb = words[verb_idx]
    verb_word = verb.vocalized or verb.word

    # The verb itself: مبني, no governor needed — already in assignments
    # but we note it has no case
    assignments[verb_idx].role = "فعل"
    assignments[verb_idx].case = None
    assignments[verb_idx].confidence = "high"

    # Find subject (فاعل or نائب فاعل)
    subject_idx = None
    for i in range(verb_idx + 1, len(words)):
        wc = words[i]
        if wc.word_type == "اسم" and i not in assigned:
            # Skip words already claimed by prepositions
            if i > 0 and _is_prep(words[i - 1]):
                continue
            subject_idx = i
            break
        if wc.word_type == "فعل":
            # Hit another verb — stop looking
            break
        if wc.word_type == "حرف" and _is_prep(wc):
            # Skip the prep and its object
            continue

    if subject_idx is not None:
        if verb.voice == "مبني للمجهول":
            assignments[subject_idx].role = "نائب فاعل"
        else:
            assignments[subject_idx].role = "فاعل"
        assignments[subject_idx].governor = verb_word
        assignments[subject_idx].governor_index = verb_idx
        assignments[subject_idx].case = "رفع"
        assignments[subject_idx].confidence = "high"
        assigned.add(subject_idx)

        # Find object (مفعول به) if verb is transitive
        if verb.transitivity and "متعد" in verb.transitivity and verb.voice != "مبني للمجهول":
            for i in range(subject_idx + 1, len(words)):
                wc = words[i]
                if wc.word_type == "اسم" and i not in assigned:
                    if i > 0 and _is_prep(words[i - 1]):
                        continue
                    assignments[i].role = "مفعول به"
                    assignments[i].governor = verb_word
                    assignments[i].governor_index = verb_idx
                    assignments[i].case = "نصب"
                    assignments[i].confidence = "high"
                    assigned.add(i)
                    break
                if wc.word_type == "فعل":
                    break
    else:
        # No explicit subject → hidden pronoun (ضمير مستتر)
        hp = _detect_hidden_pronoun(verb)
        if hp:
            assignments[verb_idx].hidden_pronoun = hp

    return assigned


def _assign_nominal_sentence(
    words: list[WordClassification],
    assignments: list[GovernorAssignment],
    start: int = 0,
    already_assigned: set[int] | None = None,
) -> set[int]:
    """Assign governors for a nominal sentence (مبتدأ + خبر)."""
    assigned: set[int] = set()
    skip = already_assigned or set()

    # Find مبتدأ
    mubtada_idx = None
    for i in range(start, len(words)):
        if i in skip:
            continue
        wc = words[i]
        if wc.word_type == "اسم":
            mubtada_idx = i
            break
        if wc.word_type in ("حرف", "أداة"):
            continue
        break

    if mubtada_idx is None:
        return assigned

    mubtada = words[mubtada_idx]
    assignments[mubtada_idx].role = "مبتدأ"
    assignments[mubtada_idx].governor = "الابتداء"
    assignments[mubtada_idx].governor_index = -1
    assignments[mubtada_idx].case = "رفع"
    assignments[mubtada_idx].confidence = "high"
    assigned.add(mubtada_idx)

    # Find خبر
    for i in range(mubtada_idx + 1, len(words)):
        if i in skip or i in assigned:
            continue
        wc = words[i]

        # خبر can be:
        # 1. Noun/adjective
        if wc.word_type == "اسم":
            # Check if it's a مجرور (governed by preposition) — then it's شبه جملة as خبر
            if i > 0 and _is_prep(words[i - 1]):
                continue  # This noun is governed by the preposition, not مبتدأ
            assignments[i].role = "خبر"
            assignments[i].governor = mubtada.vocalized or mubtada.word
            assignments[i].governor_index = mubtada_idx
            assignments[i].case = "رفع"
            assignments[i].confidence = "high"
            assigned.add(i)
            break

        # 2. Verb → خبر is a جملة فعلية (handle verb as start of embedded clause)
        if wc.word_type == "فعل":
            assignments[i].role = "خبر (جملة فعلية)"
            assignments[i].governor = mubtada.vocalized or mubtada.word
            assignments[i].governor_index = mubtada_idx
            assignments[i].case = None  # Clause in محل رفع
            assignments[i].confidence = "medium"
            assigned.add(i)
            break

        # 3. Preposition → شبه الجملة as خبر
        if _is_prep(wc):
            # The prep phrase is the خبر — mark the prep
            assignments[i].role = "خبر (شبه جملة)"
            assignments[i].governor = mubtada.vocalized or mubtada.word
            assignments[i].governor_index = mubtada_idx
            assignments[i].case = None  # في محل رفع
            assignments[i].confidence = "high"
            assigned.add(i)
            break

    return assigned


def _assign_kana_sentence(
    words: list[WordClassification],
    assignments: list[GovernorAssignment],
    nasikh_idx: int,
) -> set[int]:
    """Assign governors for كان وأخواتها pattern."""
    assigned: set[int] = set()
    nasikh = words[nasikh_idx]
    nasikh_word = nasikh.vocalized or nasikh.word

    assignments[nasikh_idx].role = "فعل ناسخ"
    assignments[nasikh_idx].case = None
    assignments[nasikh_idx].confidence = "high"

    # اسم كان (مرفوع) — first noun
    ism_idx = None
    for i in range(nasikh_idx + 1, len(words)):
        wc = words[i]
        if wc.word_type == "اسم":
            if i > 0 and _is_prep(words[i - 1]):
                continue
            ism_idx = i
            break

    if ism_idx is not None:
        assignments[ism_idx].role = "اسم " + _strip(nasikh.word)
        assignments[ism_idx].governor = nasikh_word
        assignments[ism_idx].governor_index = nasikh_idx
        assignments[ism_idx].case = "رفع"
        assignments[ism_idx].confidence = "high"
        assigned.add(ism_idx)

        # خبر كان (منصوب) — next noun/adj/شبه جملة
        for i in range(ism_idx + 1, len(words)):
            wc = words[i]
            if i in assigned:
                continue
            if wc.word_type == "اسم":
                if i > 0 and _is_prep(words[i - 1]):
                    continue
                assignments[i].role = "خبر " + _strip(nasikh.word)
                assignments[i].governor = nasikh_word
                assignments[i].governor_index = nasikh_idx
                assignments[i].case = "نصب"
                assignments[i].confidence = "high"
                assigned.add(i)
                break
            if _is_prep(wc):
                # شبه جملة as خبر
                assignments[i].role = "خبر " + _strip(nasikh.word) + " (شبه جملة)"
                assignments[i].governor = nasikh_word
                assignments[i].governor_index = nasikh_idx
                assignments[i].case = None  # في محل نصب
                assignments[i].confidence = "high"
                assigned.add(i)
                break
    else:
        # Hidden subject
        hp = _detect_hidden_pronoun(nasikh)
        if hp:
            assignments[nasikh_idx].hidden_pronoun = hp

    return assigned


def _assign_inna_sentence(
    words: list[WordClassification],
    assignments: list[GovernorAssignment],
    nasikh_idx: int,
) -> set[int]:
    """Assign governors for إنّ وأخواتها pattern."""
    assigned: set[int] = set()
    nasikh = words[nasikh_idx]
    nasikh_word = nasikh.vocalized or nasikh.word

    assignments[nasikh_idx].role = "حرف ناسخ"
    assignments[nasikh_idx].case = None
    assignments[nasikh_idx].confidence = "high"

    # اسم إنّ (منصوب) — first noun
    ism_idx = None
    for i in range(nasikh_idx + 1, len(words)):
        wc = words[i]
        if wc.word_type == "اسم":
            ism_idx = i
            break

    if ism_idx is not None:
        assignments[ism_idx].role = "اسم " + _strip(nasikh.word)
        assignments[ism_idx].governor = nasikh_word
        assignments[ism_idx].governor_index = nasikh_idx
        assignments[ism_idx].case = "نصب"
        assignments[ism_idx].confidence = "high"
        assigned.add(ism_idx)

        # خبر إنّ (مرفوع) — next noun/adj
        for i in range(ism_idx + 1, len(words)):
            wc = words[i]
            if i in assigned:
                continue
            if wc.word_type == "اسم":
                if i > 0 and _is_prep(words[i - 1]):
                    continue
                assignments[i].role = "خبر " + _strip(nasikh.word)
                assignments[i].governor = nasikh_word
                assignments[i].governor_index = nasikh_idx
                assignments[i].case = "رفع"
                assignments[i].confidence = "high"
                assigned.add(i)
                break
            if _is_prep(wc):
                assignments[i].role = "خبر " + _strip(nasikh.word) + " (شبه جملة)"
                assignments[i].governor = nasikh_word
                assignments[i].governor_index = nasikh_idx
                assignments[i].case = None
                assignments[i].confidence = "high"
                assigned.add(i)
                break

    return assigned


def _assign_zanna_sentence(
    words: list[WordClassification],
    assignments: list[GovernorAssignment],
    verb_idx: int,
) -> set[int]:
    """Assign governors for ظنّ وأخواتها pattern (فاعل + مفعولين)."""
    assigned: set[int] = set()
    verb = words[verb_idx]
    verb_word = verb.vocalized or verb.word

    assignments[verb_idx].role = "فعل قلبي/تحويلي"
    assignments[verb_idx].case = None
    assignments[verb_idx].confidence = "high"

    nouns_found: list[int] = []
    for i in range(verb_idx + 1, len(words)):
        wc = words[i]
        if wc.word_type == "اسم":
            if i > 0 and _is_prep(words[i - 1]):
                continue
            nouns_found.append(i)
            if len(nouns_found) == 3:
                break
        if wc.word_type == "فعل":
            break

    if len(nouns_found) >= 1:
        # فاعل
        assignments[nouns_found[0]].role = "فاعل"
        assignments[nouns_found[0]].governor = verb_word
        assignments[nouns_found[0]].governor_index = verb_idx
        assignments[nouns_found[0]].case = "رفع"
        assignments[nouns_found[0]].confidence = "high"
        assigned.add(nouns_found[0])

    if len(nouns_found) >= 2:
        # مفعول به أول
        assignments[nouns_found[1]].role = "مفعول به أول"
        assignments[nouns_found[1]].governor = verb_word
        assignments[nouns_found[1]].governor_index = verb_idx
        assignments[nouns_found[1]].case = "نصب"
        assignments[nouns_found[1]].confidence = "high"
        assigned.add(nouns_found[1])

    if len(nouns_found) >= 3:
        # مفعول به ثانٍ
        assignments[nouns_found[2]].role = "مفعول به ثانٍ"
        assignments[nouns_found[2]].governor = verb_word
        assignments[nouns_found[2]].governor_index = verb_idx
        assignments[nouns_found[2]].case = "نصب"
        assignments[nouns_found[2]].confidence = "high"
        assigned.add(nouns_found[2])

    if not nouns_found:
        hp = _detect_hidden_pronoun(verb)
        if hp:
            assignments[verb_idx].hidden_pronoun = hp

    return assigned


def _assign_laa_nafiya_liljins(
    words: list[WordClassification],
    assignments: list[GovernorAssignment],
    laa_idx: int,
) -> set[int]:
    """Assign governors for لا النافية للجنس pattern."""
    assigned: set[int] = set()
    assignments[laa_idx].role = "لا النافية للجنس"
    assignments[laa_idx].case = None
    assignments[laa_idx].confidence = "high"

    # اسم لا (منصوب or مبني على الفتح)
    for i in range(laa_idx + 1, len(words)):
        wc = words[i]
        if wc.word_type == "اسم":
            assignments[i].role = "اسم لا"
            assignments[i].governor = "لا"
            assignments[i].governor_index = laa_idx
            assignments[i].case = "نصب"
            assignments[i].confidence = "high"
            assigned.add(i)

            # خبر لا (مرفوع) — look for next nominal
            for j in range(i + 1, len(words)):
                wj = words[j]
                if j in assigned:
                    continue
                if wj.word_type == "اسم":
                    if j > 0 and _is_prep(words[j - 1]):
                        continue
                    assignments[j].role = "خبر لا"
                    assignments[j].governor = "لا"
                    assignments[j].governor_index = laa_idx
                    assignments[j].case = "رفع"
                    assignments[j].confidence = "medium"
                    assigned.add(j)
                    break
                if _is_prep(wj):
                    assignments[j].role = "خبر لا (شبه جملة)"
                    assignments[j].governor = "لا"
                    assignments[j].governor_index = laa_idx
                    assignments[j].case = None
                    assignments[j].confidence = "high"
                    assigned.add(j)
                    # Also mark the noun after the preposition as مجرور
                    if j + 1 < len(words) and words[j + 1].word_type == "اسم":
                        assignments[j + 1].role = "اسم مجرور"
                        assignments[j + 1].governor = wj.vocalized or wj.word
                        assignments[j + 1].governor_index = j
                        assignments[j + 1].case = "جر"
                        assignments[j + 1].confidence = "high"
                        assigned.add(j + 1)
                    break
            break

    return assigned


# ---------------------------------------------------------------------------
# Section 4: Hidden element detection (ضمائر مستترة)
# ---------------------------------------------------------------------------


def _detect_hidden_pronoun(verb: WordClassification) -> dict | None:
    """Detect hidden pronoun for a verb that has no explicit subject."""
    if verb.word_type != "فعل":
        return None

    suffix = verb.subject_suffix
    tense = verb.tense
    if not suffix or not tense:
        # Default: 3rd person masc sing
        if tense == "ماضٍ":
            return {"type": "مستتر", "estimate": "هو", "obligatory": "جوازاً"}
        if tense == "مضارع":
            return {"type": "مستتر", "estimate": "هو", "obligatory": "جوازاً"}
        if tense == "أمر":
            return {"type": "مستتر", "estimate": "أنتَ", "obligatory": "وجوباً"}
        return None

    person = suffix.get("person")
    number = suffix.get("number", "مفرد")
    gender = suffix.get("gender", "مذكر")

    # Check وجوباً cases
    key3 = (tense, person, number)
    if key3 in HIDDEN_PRONOUN_WUJOOB:
        est, obl = HIDDEN_PRONOUN_WUJOOB[key3]
        return {"type": "مستتر", "estimate": est, "obligatory": obl}

    # Check جوازاً cases
    key4 = (tense, person, number, gender)
    if key4 in HIDDEN_PRONOUN_JAWAZ:
        est, obl = HIDDEN_PRONOUN_JAWAZ[key4]
        return {"type": "مستتر", "estimate": est, "obligatory": obl}

    # Fallback
    desc = suffix.get("desc", "هو")
    return {"type": "مستتر", "estimate": desc, "obligatory": "جوازاً"}


# ---------------------------------------------------------------------------
# Section 5: شبه الجملة attachment
# ---------------------------------------------------------------------------


def _attach_shibh_jumla(
    words: list[WordClassification],
    assignments: list[GovernorAssignment],
    prep_idx: int,
    assigned: set[int],
) -> None:
    """Attach a شبه الجملة (prep + noun) to its متعلَّق."""
    if assignments[prep_idx].role:
        return  # Already assigned (e.g., as خبر شبه جملة)

    # Find the nearest verb before this preposition
    verb_idx = None
    for i in range(prep_idx - 1, -1, -1):
        if words[i].word_type == "فعل":
            verb_idx = i
            break
        # Stop at another preposition or sentence boundary
        if words[i].word_type == "حرف" and _is_prep(words[i]):
            break

    if verb_idx is not None:
        verb = words[verb_idx]
        assignments[prep_idx].role = "جار ومجرور"
        assignments[prep_idx].governor = verb.vocalized or verb.word
        assignments[prep_idx].governor_index = verb_idx
        assignments[prep_idx].confidence = "high"
    else:
        # No verb found — attach to implicit (محذوف: كائن/مستقر)
        # This is typically خبر or صفة or حال
        assignments[prep_idx].role = "جار ومجرور"
        assignments[prep_idx].governor = "محذوف (كائن/مستقر)"
        assignments[prep_idx].governor_index = -1
        assignments[prep_idx].confidence = "medium"


# ---------------------------------------------------------------------------
# Section 6: التوابع detection
# ---------------------------------------------------------------------------


def _detect_tawabi(
    words: list[WordClassification],
    assignments: list[GovernorAssignment],
    assigned: set[int],
) -> None:
    """Detect التوابع (نعت، عطف، توكيد، بدل) using agreement patterns."""
    for i in range(1, len(words)):
        if i in assigned:
            continue
        if assignments[i].role:
            continue

        wc = words[i]
        prev = words[i - 1]

        # Check for عطف: preceded by عطف particle
        if prev.word_type == "حرف" and _strip(prev.word) in ATF_PARTICLES:
            # Find the معطوف عليه (word before the particle)
            matoof_alayh_idx = None
            for j in range(i - 2, -1, -1):
                if words[j].word_type == "اسم":
                    matoof_alayh_idx = j
                    break
            if matoof_alayh_idx is not None and wc.word_type == "اسم":
                matoof = words[matoof_alayh_idx]
                assignments[i].role = "معطوف"
                assignments[i].governor = matoof.vocalized or matoof.word
                assignments[i].governor_index = matoof_alayh_idx
                assignments[i].case = assignments[matoof_alayh_idx].case
                assignments[i].confidence = "high"
                # Also mark the particle
                if not assignments[i - 1].role:
                    assignments[i - 1].role = "حرف عطف"
                    assignments[i - 1].confidence = "high"
                continue

        # Check for نعت: same definiteness + gender/number agreement
        if wc.word_type == "اسم" and prev.word_type == "اسم":
            if wc.definiteness == prev.definiteness:
                if wc.subtype == "صفة" or wc.noun_class in ("اسم فاعل", "اسم مفعول", "اسم تفضيل"):
                    assignments[i].role = "نعت"
                    assignments[i].governor = prev.vocalized or prev.word
                    assignments[i].governor_index = i - 1
                    assignments[i].case = assignments[i - 1].case
                    assignments[i].confidence = "medium"
                    continue

        # Check for توكيد معنوي
        if wc.word_type == "اسم" and _strip(wc.word) in TAWKEED_WORDS:
            if prev.word_type == "اسم":
                assignments[i].role = "توكيد معنوي"
                assignments[i].governor = prev.vocalized or prev.word
                assignments[i].governor_index = i - 1
                assignments[i].case = assignments[i - 1].case
                assignments[i].confidence = "medium"


# ---------------------------------------------------------------------------
# Section 6b: حرف الجر الزائد detection
# ---------------------------------------------------------------------------


def _detect_zaaid_min(
    words: list[WordClassification],
    assignments: list[GovernorAssignment],
    idx: int,
) -> bool:
    """Detect زائدة مِن: after نفي/استفهام/نهي + before نكرة.

    Example: هل مِن خالقٍ غيرُ الله → من زائدة, خالقٍ مجرور لفظاً في محل رفع مبتدأ
    """
    if idx == 0 or idx + 1 >= len(words):
        return False

    wc = words[idx]
    if _strip(wc.word) != "من":
        return False

    # Check: preceded by نفي/استفهام/نهي
    prev = words[idx - 1]
    is_negation = _strip(prev.word) in ("ما", "لا", "لم", "لن", "ليس", "هل", "أ")
    if not is_negation:
        return False

    # Check: followed by نكرة
    next_wc = words[idx + 1]
    if next_wc.word_type != "اسم" or next_wc.definiteness == "معرفة":
        return False

    # This is مِن الزائدة
    assignments[idx].role = "حرف جر زائد"
    assignments[idx].case = None
    assignments[idx].confidence = "high"
    assignments[idx].governor = None

    # The noun after it: مجرور لفظاً, but the محل depends on position
    # Determine محل from context
    if assignments[idx + 1].role:
        return True  # Already assigned

    # Default: مجرور لفظاً في محل رفع (most common: فاعل or مبتدأ)
    assignments[idx + 1].role = "مجرور لفظاً بمن الزائدة"
    assignments[idx + 1].case = "جر"  # لفظاً
    assignments[idx + 1].governor = "من (زائدة)"
    assignments[idx + 1].governor_index = idx
    assignments[idx + 1].confidence = "high"
    return True


def _detect_zaaid_baa(
    words: list[WordClassification],
    assignments: list[GovernorAssignment],
    idx: int,
    classification: SentenceClassification,
) -> bool:
    """Detect الباء الزائدة in خبر ليس / خبر ما الحجازية / after كفى.

    Example: ليس زيدٌ بكسولٍ → الباء زائدة, كسولٍ خبر ليس مجرور لفظاً في محل نصب
    """
    wc = words[idx]
    stripped = _strip(wc.word)

    # Prefixed باء (part of the word) or standalone ب
    is_baa = stripped in ("ب", "بـ") or (wc.subtype == "حرف جر" and stripped.startswith("ب"))
    if not is_baa:
        return False

    # Check: is this after ليس or ما الحجازية?
    for naw in classification.nawasikh:
        nasikh_word = _strip(words[naw["index"]].word) if naw["index"] < len(words) else ""
        if nasikh_word in ("ليس", "ما") and naw.get("type") in ("كان", "ما الحجازية"):
            # The noun after الباء is likely the خبر
            if idx + 1 < len(words) and words[idx + 1].word_type == "اسم":
                assignments[idx].role = "حرف جر زائد (الباء الزائدة)"
                assignments[idx].case = None
                assignments[idx].confidence = "high"
                assignments[idx + 1].role = "خبر (مجرور لفظاً بالباء الزائدة)"
                assignments[idx + 1].case = "جر"  # لفظاً, محل نصب
                assignments[idx + 1].governor = nasikh_word
                assignments[idx + 1].governor_index = naw["index"]
                assignments[idx + 1].confidence = "high"
                return True

    # Check: after كفى (كفى بالله شهيداً)
    for i in range(idx - 1, -1, -1):
        if _strip(words[i].word) in ("كفى", "يكفي"):
            if idx + 1 < len(words) and words[idx + 1].word_type == "اسم":
                assignments[idx].role = "حرف جر زائد (الباء الزائدة)"
                assignments[idx].case = None
                assignments[idx].confidence = "high"
                assignments[idx + 1].role = "فاعل (مجرور لفظاً بالباء الزائدة)"
                assignments[idx + 1].case = "جر"  # لفظاً, محل رفع
                assignments[idx + 1].governor = "كفى"
                assignments[idx + 1].governor_index = i
                assignments[idx + 1].confidence = "high"
                return True
            break

    return False


def _detect_exception_pattern(
    words: list[WordClassification],
    assignments: list[GovernorAssignment],
) -> None:
    """Detect الاستثناء بإلا and assign case deterministically.

    Rules:
    - تام مثبت → نصب واجب
    - مفرّغ (no مستثنى منه) → حسب الموقع
    - تام منفي → بدل (الأرجح) أو نصب
    """
    for i, wc in enumerate(words):
        if _strip(wc.word) != "إلا":
            continue

        # إلا found — check what follows
        if i + 1 >= len(words):
            continue

        noun_idx = i + 1
        noun = words[noun_idx]
        if noun.word_type != "اسم":
            continue

        # Check if there's a مستثنى منه before إلا (= تام) or not (= مفرّغ)
        has_mustathna_minhu = False
        has_negation = False
        for j in range(i):
            if words[j].word_type == "اسم" and assignments[j].role in ("فاعل", "مبتدأ", "اسم كان", "اسم إنّ", "مفعول به"):
                has_mustathna_minhu = True
            if _strip(words[j].word) in ("ما", "لا", "لم", "لن", "ليس", "لمّا", "غير"):
                has_negation = True

        assignments[i].role = "أداة استثناء"
        assignments[i].case = None
        assignments[i].confidence = "high"

        if has_mustathna_minhu and not has_negation:
            # تام مثبت → نصب واجب
            assignments[noun_idx].role = "مستثنى"
            assignments[noun_idx].case = "نصب"
            assignments[noun_idx].governor = "إلا"
            assignments[noun_idx].governor_index = i
            assignments[noun_idx].confidence = "high"
        elif not has_mustathna_minhu:
            # مفرّغ → حسب الموقع (determined by what's missing in the sentence)
            assignments[noun_idx].role = "مستثنى (مفرّغ — حسب الموقع)"
            assignments[noun_idx].confidence = "medium"
            assignments[noun_idx].governor = "إلا (مفرّغ)"
            assignments[noun_idx].governor_index = i
        else:
            # تام منفي → بدل (الأرجح)
            assignments[noun_idx].role = "بدل (من المستثنى منه)"
            assignments[noun_idx].case = assignments[j].case if j else "رفع"
            assignments[noun_idx].governor = "إلا"
            assignments[noun_idx].governor_index = i
            assignments[noun_idx].confidence = "medium"


# ---------------------------------------------------------------------------
# Section 6c: الاشتغال and التنازع detection
# ---------------------------------------------------------------------------


def _detect_ishtighal(
    classification: SentenceClassification,
    assignments: list[GovernorAssignment],
) -> bool:
    """Detect الاشتغال pattern: fronted noun + verb + pronoun referring to noun.

    Pattern: اسم + فعل + ضمير يعود على الاسم
    Example: زيداً أكرمتُه (or زيدٌ أكرمتُه)

    Returns True if pattern detected and assignments modified.
    """
    words = classification.words
    if len(words) < 2:
        return False

    for i in range(len(words) - 1):
        wc_noun = words[i]
        wc_verb = words[i + 1] if i + 1 < len(words) else None

        if wc_noun.word_type != "اسم" or not wc_verb or wc_verb.word_type != "فعل":
            continue

        # Check if the verb has any attached pronoun suffix
        if not wc_verb.suffixes:
            continue

        # Check if the assignment for the noun is still unassigned
        if assignments[i].role:
            continue

        # This looks like اشتغال — the noun before the verb
        # Default: مبتدأ (ترجيح الرفع) unless context says otherwise
        assignments[i].role = "مبتدأ (اشتغال)"
        assignments[i].case = "رفع"
        assignments[i].governor = "الابتداء"
        assignments[i].governor_index = -1
        assignments[i].confidence = "medium"
        return True

    return False


def _detect_tanazue(
    classification: SentenceClassification,
    assignments: list[GovernorAssignment],
) -> bool:
    """Detect التنازع pattern: two verbs sharing one trailing argument.

    Pattern: فعل + (و/ف/ثم) + فعل + اسم
    Example: جاء وذهبَ زيدٌ

    On the البصريون view: الثاني (nearer) governs the shared argument.
    Returns True if pattern detected and assignments modified.
    """
    words = classification.words
    if len(words) < 3:
        return False

    for i in range(len(words) - 2):
        wc1 = words[i]
        wc2 = words[i + 1]
        wc3 = words[i + 2] if i + 2 < len(words) else None

        # Pattern: verb + conjunction + verb + noun
        if wc1.word_type != "فعل":
            continue
        if _strip(wc2.word) not in ("و", "ف", "ثم", "ثمّ"):
            continue
        if not wc3 or wc3.word_type != "فعل":
            continue

        # Check if there's a noun after the second verb
        noun_idx = i + 3
        if noun_idx >= len(words) or words[noun_idx].word_type != "اسم":
            continue

        # التنازع detected — assign the shared noun to the nearer verb (البصريون)
        if not assignments[noun_idx].role:
            assignments[noun_idx].role = "فاعل"
            assignments[noun_idx].case = "رفع"
            assignments[noun_idx].governor = wc3.vocalized or wc3.word
            assignments[noun_idx].governor_index = i + 2
            assignments[noun_idx].confidence = "medium"

            # The first verb gets a hidden pronoun
            if not assignments[i].hidden_pronoun:
                assignments[i].hidden_pronoun = {
                    "type": "مستتر",
                    "estimate": "هو",
                    "obligatory": "جوازاً",
                    "note": "تنازع — الفاعل مُضمر في الأول على مذهب البصريين",
                }
            return True

    return False


# ---------------------------------------------------------------------------
# Section 7: Orchestrator
# ---------------------------------------------------------------------------


def map_governors(text: str) -> GovernorMap:
    """Perform deterministic Pass 2 governor mapping on an Arabic sentence.

    Calls classify_sentence (Pass 1) internally, then assigns governors
    to every word using positional rules. Flags ambiguous cases.
    """
    if not text or not text.strip():
        return GovernorMap(original_text=text)

    # Step 1: Run Pass 1
    classification = classify_sentence(text)
    if not classification.words:
        return GovernorMap(original_text=text, classification=classification)

    words = classification.words

    # Initialize assignments
    assignments = [
        GovernorAssignment(word=wc.word, word_index=i)
        for i, wc in enumerate(words)
    ]

    assigned: set[int] = set()

    # Step 2: Handle النواسخ first (they override normal patterns)
    for naw in classification.nawasikh:
        idx = naw["index"]
        naw_type = naw["type"]
        s = _strip(words[idx].word)

        if "كان" in naw_type:
            new_assigned = _assign_kana_sentence(words, assignments, idx)
            assigned |= new_assigned
            assigned.add(idx)
        elif "إنّ" in naw_type:
            new_assigned = _assign_inna_sentence(words, assignments, idx)
            assigned |= new_assigned
            assigned.add(idx)
        elif "ظنّ" in naw_type:
            new_assigned = _assign_zanna_sentence(words, assignments, idx)
            assigned |= new_assigned
            assigned.add(idx)
        elif "كاد" in naw_type:
            # كاد works like كان
            new_assigned = _assign_kana_sentence(words, assignments, idx)
            assigned |= new_assigned
            assigned.add(idx)

    # Step 3: Handle لا النافية للجنس
    laa_handled = False
    for i, wc in enumerate(words):
        if i in assigned:
            continue
        if wc.particle_type and "نافية للجنس" in wc.particle_type:
            new_assigned = _assign_laa_nafiya_liljins(words, assignments, i)
            assigned |= new_assigned
            assigned.add(i)
            laa_handled = True

    # Step 3.5: Assign ALL preposition effects early (Rule Group F)
    # This must happen before nominal/verbal sentence assignment so that
    # prep+noun pairs are already claimed and don't get misassigned.
    # Use word text matching against STANDALONE_PREPOSITIONS as the primary
    # check — this handles cases where Pass 1 misclassified the preposition.
    for i, wc in enumerate(words):
        if i in assigned:
            continue
        s = _strip(wc.word)
        is_prep_word = (
            (wc.subtype == "حرف جر")
            or (s in STANDALONE_PREPOSITIONS)
        )
        if is_prep_word:
            if not assignments[i].role:
                assignments[i].role = "حرف جر"
                assignments[i].case = None
                assignments[i].confidence = "high"
            assigned.add(i)
            if i + 1 < len(words) and words[i + 1].word_type == "اسم":
                if not assignments[i + 1].role:
                    assignments[i + 1].role = "اسم مجرور"
                    assignments[i + 1].governor = wc.vocalized or wc.word
                    assignments[i + 1].governor_index = i
                    assignments[i + 1].case = "جر"
                    assignments[i + 1].confidence = "high"
                    assigned.add(i + 1)

    # Step 4: Handle main sentence structure (if not handled by nawasikh or لا)
    if not classification.nawasikh and not laa_handled:
        if classification.sentence_type == "جملة فعلية":
            # Find the main verb
            for i, wc in enumerate(words):
                if wc.word_type == "فعل" and i not in assigned:
                    new_assigned = _assign_verbal_sentence(words, assignments, i)
                    assigned |= new_assigned
                    assigned.add(i)
                    break
        elif classification.sentence_type == "جملة اسمية":
            # Find first noun for مبتدأ/خبر
            start = 0
            for i, wc in enumerate(words):
                if wc.word_type in ("حرف", "أداة") and i not in assigned:
                    continue
                start = i
                break
            new_assigned = _assign_nominal_sentence(words, assignments, start, already_assigned=assigned)
            assigned |= new_assigned

    # Step 5: Handle حروف النصب والجزم (Rule Group H)
    for i, wc in enumerate(words):
        if i in assigned:
            continue
        if wc.subtype == "حرف جزم":
            assignments[i].role = "حرف جزم"
            assignments[i].case = None
            assignments[i].confidence = "high"
            assigned.add(i)
            # The مضارع after it should be مجزوم
            if i + 1 < len(words) and words[i + 1].word_type == "فعل" and words[i + 1].tense == "مضارع":
                if not assignments[i + 1].case:
                    assignments[i + 1].case = "جزم"
                    assignments[i + 1].governor = wc.vocalized or wc.word
                    assignments[i + 1].governor_index = i
        elif wc.subtype == "حرف نصب":
            assignments[i].role = "حرف نصب"
            assignments[i].case = None
            assignments[i].confidence = "high"
            assigned.add(i)
            if i + 1 < len(words) and words[i + 1].word_type == "فعل" and words[i + 1].tense == "مضارع":
                if not assignments[i + 1].case:
                    assignments[i + 1].case = "نصب"
                    assignments[i + 1].governor = wc.vocalized or wc.word
                    assignments[i + 1].governor_index = i

    # Step 6: Detect حرف الجر الزائد (مِن الزائدة, الباء الزائدة)
    for i, wc in enumerate(words):
        if i in assigned:
            continue
        if _detect_zaaid_min(words, assignments, i):
            assigned.add(i)
            if i + 1 < len(words):
                assigned.add(i + 1)
        elif _detect_zaaid_baa(words, assignments, i, classification):
            assigned.add(i)
            if i + 1 < len(words):
                assigned.add(i + 1)

    # Step 6b: Detect الاستثناء بإلا
    _detect_exception_pattern(words, assignments)

    # Step 7: شبه الجملة attachment for unassigned preps
    for i, wc in enumerate(words):
        if _is_prep(wc) and wc.word_type == "حرف" and not assignments[i].role:
            _attach_shibh_jumla(words, assignments, i, assigned)

    # Step 8: التوابع detection
    _detect_tawabi(words, assignments, assigned)

    # Step 8b: الاشتغال detection (noun + verb + pronoun referring back)
    _detect_ishtighal(classification, assignments)

    # Step 8c: التنازع detection (two verbs sharing one argument)
    _detect_tanazue(classification, assignments)

    # Step 9: Mark remaining unassigned particles
    for i, wc in enumerate(words):
        if not assignments[i].role:
            if wc.word_type in ("حرف", "أداة"):
                assignments[i].role = wc.subtype or "حرف"
                assignments[i].confidence = "high"

    # Step 10: Collect ambiguities
    ambiguities = []
    for a in assignments:
        if not a.role:
            ambiguities.append({
                "word": a.word,
                "index": a.word_index,
                "reason": "لم يُحدد دوره الإعرابي",
            })
        elif a.confidence == "low":
            ambiguities.append({
                "word": a.word,
                "index": a.word_index,
                "reason": "ثقة منخفضة في التحديد",
                "current_role": a.role,
            })

    return GovernorMap(
        original_text=text,
        clause_type=classification.sentence_type,
        words=assignments,
        ambiguities=ambiguities,
        classification=classification,
    )


# ---------------------------------------------------------------------------
# Section 8: Pass 3 — Case Sign Assignment (الإعراب)
# ---------------------------------------------------------------------------

# Lookup table: (case, morph_class) → (sign, sign_type, note)
CASE_SIGNS_TABLE: dict[tuple[str, str], tuple[str, str, str | None]] = {
    # --- الرفع ---
    ("رفع", "صحيح"):           ("الضمة", "أصلية", None),
    ("رفع", "جمع تكسير"):      ("الضمة", "أصلية", None),
    ("رفع", "جمع مؤنث سالم"):  ("الضمة", "أصلية", None),
    ("رفع", "الأسماء الخمسة"):  ("الواو", "فرعية", None),
    ("رفع", "جمع مذكر سالم"):  ("الواو", "فرعية", None),
    ("رفع", "مثنى"):           ("الألف", "فرعية", None),
    ("رفع", "الأفعال الخمسة"):  ("ثبوت النون", "فرعية", None),
    ("رفع", "ممنوع من الصرف"):  ("الضمة", "أصلية", None),
    # --- النصب ---
    ("نصب", "صحيح"):           ("الفتحة", "أصلية", None),
    ("نصب", "جمع تكسير"):      ("الفتحة", "أصلية", None),
    ("نصب", "الأسماء الخمسة"):  ("الألف", "فرعية", None),
    ("نصب", "مثنى"):           ("الياء", "فرعية", None),
    ("نصب", "جمع مذكر سالم"):  ("الياء", "فرعية", None),
    ("نصب", "جمع مؤنث سالم"):  ("الكسرة", "فرعية", "بدلاً من الفتحة"),
    ("نصب", "الأفعال الخمسة"):  ("حذف النون", "فرعية", None),
    ("نصب", "ممنوع من الصرف"):  ("الفتحة", "فرعية", "بلا تنوين"),
    # --- الجر ---
    ("جر", "صحيح"):            ("الكسرة", "أصلية", None),
    ("جر", "جمع تكسير"):       ("الكسرة", "أصلية", None),
    ("جر", "جمع مؤنث سالم"):   ("الكسرة", "أصلية", None),
    ("جر", "الأسماء الخمسة"):   ("الياء", "فرعية", None),
    ("جر", "مثنى"):            ("الياء", "فرعية", None),
    ("جر", "جمع مذكر سالم"):   ("الياء", "فرعية", None),
    ("جر", "ممنوع من الصرف"):   ("الفتحة", "فرعية", "نيابة عن الكسرة"),
    # --- الجزم ---
    ("جزم", "صحيح"):           ("السكون", "أصلية", None),
    ("جزم", "الأفعال الخمسة"):  ("حذف النون", "فرعية", None),
    ("جزم", "معتل الآخر"):     ("حذف حرف العلة", "فرعية", None),
}


def assign_case_signs(gov_map: GovernorMap) -> list[CaseSign | None]:
    """Pass 3: Determine the case sign for each word from (case, morph_class).

    Returns a list parallel to gov_map.words. None for words that don't
    get case signs (مبني words, particles).
    """
    if not gov_map.classification:
        return [None] * len(gov_map.words)

    words = gov_map.classification.words
    signs: list[CaseSign | None] = []

    for i, assignment in enumerate(gov_map.words):
        case = assignment.case
        if not case or i >= len(words):
            signs.append(None)
            continue

        wc = words[i]

        # مبني words don't get case signs (they use محل)
        if wc.declinable == "مبني":
            signs.append(None)
            continue

        morph = wc.morph_class or "صحيح"

        # Check for إعراب تقديري
        if morph == "مقصور":
            # All 3 cases estimated — reason: التعذر
            sign, stype, note = CASE_SIGNS_TABLE.get((case, "صحيح"), ("الضمة", "أصلية", None))
            signs.append(CaseSign(
                sign=sign, sign_type=stype, estimated=True,
                estimated_reason="التعذر",
                note="مقدرة على الألف منع من ظهورها التعذر",
            ))
            continue

        if morph == "منقوص":
            if case in ("رفع", "جر"):
                # Estimated — reason: الثقل
                sign = "الضمة" if case == "رفع" else "الكسرة"
                signs.append(CaseSign(
                    sign=sign, sign_type="أصلية", estimated=True,
                    estimated_reason="الثقل",
                    note="مقدرة على الياء منع من ظهورها الثقل",
                ))
                continue
            # نصب is ظاهرة for منقوص
            morph = "صحيح"

        # Normal lookup
        key = (case, morph)
        entry = CASE_SIGNS_TABLE.get(key)
        if entry:
            sign, stype, note = entry
            signs.append(CaseSign(sign=sign, sign_type=stype, note=note))
        else:
            # Fallback: use primary signs for the case
            fallback = CASE_SIGNS_TABLE.get((case, "صحيح"))
            if fallback:
                sign, stype, note = fallback
                signs.append(CaseSign(sign=sign, sign_type=stype, note=note))
            else:
                signs.append(None)

    return signs


# ---------------------------------------------------------------------------
# Section 9: Pass 4 — Verification (المراجعة)
# ---------------------------------------------------------------------------

# Expected case for each governor type
GOVERNOR_CASE_MAP: dict[str, str] = {
    "الابتداء": "رفع",
    "المبتدأ": "رفع",
}


def verify(gov_map: GovernorMap, signs: list[CaseSign | None]) -> list[dict]:
    """Pass 4: Run 6-point verification checklist.

    Returns a list of issues found. Empty list = all checks pass.
    """
    issues: list[dict] = []
    if not gov_map.classification:
        return issues

    words = gov_map.classification.words

    for i, assignment in enumerate(gov_map.words):
        if i >= len(words):
            continue
        wc = words[i]

        # Check 1: Every case matches its عامل
        # (Governor→case consistency is enforced by construction in Pass 2,
        #  so this mainly catches bugs in the pipeline)
        if assignment.case and assignment.governor:
            # Verbs governed by جزم particles should be مجزوم
            if assignment.governor_index is not None and assignment.governor_index >= 0:
                gov_wc_idx = assignment.governor_index
                if gov_wc_idx < len(words):
                    gov_wc = words[gov_wc_idx]
                    if gov_wc.subtype == "حرف جزم" and assignment.case != "جزم":
                        issues.append({
                            "check": 1, "word": assignment.word, "index": i,
                            "issue": f"بعد حرف جزم لكن الحالة {assignment.case} بدلاً من جزم",
                        })
                    if gov_wc.subtype == "حرف نصب" and assignment.case != "نصب":
                        issues.append({
                            "check": 1, "word": assignment.word, "index": i,
                            "issue": f"بعد حرف نصب لكن الحالة {assignment.case} بدلاً من نصب",
                        })

        # Check 2: Every sign matches its morphological class
        if i < len(signs) and signs[i] is not None and assignment.case:
            morph = wc.morph_class or "صحيح"
            expected = CASE_SIGNS_TABLE.get((assignment.case, morph))
            if expected and signs[i].sign != expected[0] and not signs[i].estimated:
                issues.append({
                    "check": 2, "word": assignment.word, "index": i,
                    "issue": f"العلامة {signs[i].sign} لا تطابق ({assignment.case}, {morph}) المتوقع {expected[0]}",
                })

        # Check 3: No مبني word has ظاهر case
        if wc.declinable == "مبني" and assignment.case and assignment.role:
            # مبني words should use محل, not direct case
            # This is OK if the role mentions محل — we check signs
            if i < len(signs) and signs[i] is not None:
                issues.append({
                    "check": 3, "word": assignment.word, "index": i,
                    "issue": "كلمة مبنية لها علامة إعراب ظاهرة",
                })

        # Check 4: Every مبني word has محل or لا محل
        if wc.declinable == "مبني" and wc.word_type in ("اسم",):
            if not assignment.role:
                issues.append({
                    "check": 4, "word": assignment.word, "index": i,
                    "issue": "اسم مبني بلا محل إعرابي محدد",
                })

        # Check 5: Every word accounted for
        if not assignment.role and wc.word_type:
            issues.append({
                "check": 5, "word": assignment.word, "index": i,
                "issue": "كلمة بلا دور إعرابي",
            })

    # Check 6: Every تقديري has its reason
    for i, sign in enumerate(signs):
        if sign and sign.estimated and not sign.estimated_reason:
            issues.append({
                "check": 6, "word": gov_map.words[i].word if i < len(gov_map.words) else "?",
                "index": i,
                "issue": "إعراب تقديري بلا سبب",
            })

    return issues


# ---------------------------------------------------------------------------
# Section 10: Full i'rab (all 4 passes)
# ---------------------------------------------------------------------------


def full_irab(text: str) -> IrabResult:
    """Run all 4 passes of i'rab analysis deterministically.

    Pass 1: classify_sentence (word types, particles, مبني/معرب)
    Pass 2: map_governors (عامل, role, case)
    Pass 3: assign_case_signs (علامة الإعراب)
    Pass 4: verify (6-point checklist)

    Returns a complete IrabResult ready for output formatting.
    """
    if not text or not text.strip():
        return IrabResult(original_text=text)

    # Pass 1+2
    gov_map = map_governors(text)

    # Pass 3
    signs = assign_case_signs(gov_map)

    # Pass 4
    issues = verify(gov_map, signs)

    return IrabResult(
        original_text=text,
        governor_map=gov_map,
        case_signs=signs,
        verification=issues,
        passed_verification=len(issues) == 0,
    )
