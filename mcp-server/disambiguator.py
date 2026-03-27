"""
Deterministic Pass 1 (التصنيف) for Arabic i'rab analysis.

Replaces LLM-driven classification with rule-based disambiguation:
- Layer 1: Context rules to eliminate impossible Buckwalter readings
- Layer 2: Particle decision trees (ما، لا، أنْ/إنْ، الواو، الفاء, etc.)
- Layer 3: مبني/معرب classification, sentence type, النواسخ identification

Entry point: classify_sentence(text) -> SentenceClassification
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pyaramorph

from analyzer import (
    analyzer,
    parse_solution,
    detect_verb_form,
    lookup_transitivity,
    DIACRITICS_RE,
)

# ---------------------------------------------------------------------------
# Section 1: Data structures
# ---------------------------------------------------------------------------


@dataclass
class WordClassification:
    """Classification result for a single word in a sentence."""

    word: str
    vocalized: str | None = None
    lemma: str | None = None
    root: str | None = None
    pattern: str | None = None
    word_type: str | None = None        # "فعل" | "اسم" | "حرف"
    subtype: str | None = None
    tense: str | None = None
    voice: str | None = None
    mood: str | None = None
    transitivity: str | None = None
    transitivity_source: str | None = None
    verb_form: str | None = None
    gender: str | None = None
    number: str | None = None
    definiteness: str | None = None
    noun_class: str | None = None
    diptote: bool = False
    morph_class: str | None = None
    particle_type: str | None = None
    particle_effect: str | None = None
    declinable: str = "مُعرب"
    build_on: str | None = None
    prefixes: list[str] = field(default_factory=list)
    suffixes: list[str] = field(default_factory=list)
    subject_suffix: dict | None = None
    reading_index: int = 0
    total_readings: int = 0
    disambiguation_rule: str | None = None


@dataclass
class SentenceClassification:
    """Full Pass 1 result for a sentence."""

    original_text: str
    vocalized_text: str = ""
    sentence_type: str = ""
    nawasikh: list[dict] = field(default_factory=list)
    words: list[WordClassification] = field(default_factory=list)
    ambiguities: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Section 2: Constants — النواسخ, حروف, المبني
# ---------------------------------------------------------------------------

# كان وأخواتها — the 8 that work unconditionally
KANA_SISTERS: frozenset[str] = frozenset({
    "كان", "أصبح", "اصبح", "أضحى", "اضحى", "أمسى", "امسى",
    "ظل", "ظلّ", "بات", "صار", "ليس",
    # Imperfect forms
    "يكون", "تكون", "نكون", "أكون",
    "يصبح", "تصبح", "يضحي", "يمسي", "يظل", "يبيت", "يصير",
})

# كان sisters that require preceding negation/prohibition/supplication
KANA_NEGATION_SISTERS: frozenset[str] = frozenset({
    "زال", "يزال", "تزال", "نزال", "أزال",
    "فتئ", "يفتأ", "تفتأ",
    "برح", "يبرح", "تبرح",
    "انفك", "انفكّ", "ينفك", "ينفكّ", "تنفك",
    "دام", "يدوم", "تدوم",
})

# إنّ وأخواتها
INNA_SISTERS: frozenset[str] = frozenset({
    "إنّ", "إن", "أنّ", "أن",
    "كأنّ", "كأن", "كان",  # كأنّ can lose hamza in some spellings
    "لكنّ", "لكن",
    "ليت", "لعلّ", "لعل",
})
# Subset: only the ones that are definitely إنّ sisters (not ambiguous with other uses)
INNA_UNAMBIGUOUS: frozenset[str] = frozenset({
    "إنّ", "كأنّ", "كأن", "لكنّ", "لكن", "ليت", "لعلّ", "لعل",
})

# كاد وأخواتها
KAAD_MUQARABA: frozenset[str] = frozenset({
    "كاد", "يكاد", "تكاد", "أوشك", "اوشك", "يوشك",
    "كرب", "يكرب",  # added from Ibn Aqil
})
KAAD_RAJAA: frozenset[str] = frozenset({
    "عسى", "حرى", "اخلولق",
})
KAAD_SHUROO: frozenset[str] = frozenset({
    "شرع", "يشرع", "أنشأ", "انشأ", "ينشئ",
    "طفق", "يطفق",
    "أخذ", "اخذ", "يأخذ",
    "بدأ", "يبدأ",
    "هبّ", "هب", "يهبّ",
    "انبرى", "ينبري",
    "علق", "يعلق",  # added from Ibn Aqil
})
KAAD_ALL = KAAD_MUQARABA | KAAD_RAJAA | KAAD_SHUROO

# ظنّ وأخواتها
ZANNA_YAQEEN: frozenset[str] = frozenset({
    "علم", "يعلم", "رأى", "يرى", "وجد", "يجد", "درى", "يدري",
})
ZANNA_RUJHAN: frozenset[str] = frozenset({
    "ظنّ", "ظن", "يظن", "حسب", "يحسب",
    "خال", "يخال", "زعم", "يزعم", "عدّ", "عد", "يعد",
    "حجا", "يحجو",  # added from Ibn Aqil
})
ZANNA_TAHWEEL: frozenset[str] = frozenset({
    "صيّر", "صير", "يصيّر", "جعل", "يجعل",
    "اتخذ", "اتّخذ", "يتخذ", "يتّخذ",
    "تخذ", "ترك", "يترك", "ردّ", "رد", "يرد",
})
ZANNA_ALL = ZANNA_YAQEEN | ZANNA_RUJHAN | ZANNA_TAHWEEL

# حروف الجر (standalone words)
STANDALONE_PREPOSITIONS: frozenset[str] = frozenset({
    "من", "إلى", "الى", "عن", "على", "في",
    "حتى", "مذ", "منذ",
})

# Negation particles (for checking KANA_NEGATION_SISTERS condition)
NEGATION_PARTICLES: frozenset[str] = frozenset({
    "ما", "لا", "لم", "لمّا", "لما", "لن", "ليس", "غير",
})

# حروف النصب
HUROOF_NASB: frozenset[str] = frozenset({"أن", "ان", "لن", "كي", "إذن", "اذن"})

# حروف الجزم (single verb)
HUROOF_JAZM: frozenset[str] = frozenset({"لم", "لمّا", "لما"})

# أدوات الشرط الجازمة (two verbs) — حروف
HUROOF_SHART: frozenset[str] = frozenset({"إن", "إنْ", "ان", "إذما", "اذما"})

# أدوات الشرط الجازمة — أسماء
ASMAA_SHART: frozenset[str] = frozenset({
    "من", "ما", "مهما", "متى", "أيّان", "ايان",
    "أين", "اين", "أينما", "اينما", "حيثما",
    "أنّى", "انى", "كيفما", "أيّ", "اي",
})

# حروف التحضيض
HUROOF_TAHDEED: frozenset[str] = frozenset({
    "هلّا", "هلا", "ألّا", "الا", "ألا",
    "لولا", "لوما",
})

# حروف العرض
HUROOF_ARD: frozenset[str] = frozenset({"ألا", "الا"})

# قد — contextual meaning depends on what follows
QAD: frozenset[str] = frozenset({"قد", "لقد"})

# المبني من الأسماء
MABNI_NOUNS: frozenset[str] = frozenset({
    # الضمائر المنفصلة
    "هو", "هي", "هما", "هم", "هنّ", "هن",
    "أنا", "نحن", "أنت", "أنتَ", "أنتِ", "أنتما", "أنتم", "أنتنّ", "أنتن",
    # أسماء الإشارة (except dual)
    "هذا", "هذه", "هذي", "هؤلاء",
    "ذلك", "تلك", "ذاك", "أولئك", "اولئك",
    # الأسماء الموصولة (except dual)
    "الذي", "التي", "الذين", "اللائي", "اللاتي", "اللواتي",
    # أسماء الاستفهام (except أيّ)
    "من", "ما", "ماذا", "متى", "أين", "اين", "كيف", "كم", "أيّان", "ايان", "أنّى", "انى",
    # أسماء الشرط
    "مهما", "حيثما", "أينما", "اينما", "كيفما",
    # ظروف مبنية
    "الآن", "حيث", "إذ", "اذ", "إذا", "اذا", "أمس",
    # أسماء الأفعال
    "هيهات", "صه", "آمين", "أف",
})

# النواسخ that are definitely حروف (not أفعال)
NAWASIKH_HUROOF: frozenset[str] = frozenset({
    "إنّ", "إن", "أنّ", "أن", "كأنّ", "كأن",
    "لكنّ", "لكن", "ليت", "لعلّ", "لعل",
})

# Particles that need disambiguation
AMBIGUOUS_PARTICLES: frozenset[str] = frozenset({
    "ما", "لا", "أن", "ان", "إن", "و", "ف",
    "من", "جعل",
})

# Known function words that Buckwalter returns as type=None.
# These override the reading selection to force the correct type/subtype.
KNOWN_FUNCTION_WORDS: dict[str, dict] = {
    "لم": {"type": "حرف", "subtype": "حرف جزم"},
    "لن": {"type": "حرف", "subtype": "حرف نصب"},
    "لا": {"type": "حرف", "subtype": "حرف"},
    "ما": {"type": "حرف", "subtype": "حرف"},  # default; refined by Layer 2
    # إن without diacritics: default to إنّ (inna sister) since it's far more common
    # than إنْ (conditional). Layer 2 will refine based on context.
    "إن": {"type": "حرف", "subtype": "حرف ناسخ"},
    # أن without shadda: default to أنْ الناصبة (most common before verbs).
    # Layer 2 refines to تفسيرية/مخففة/زائدة based on context.
    "أن": {"type": "حرف", "subtype": "حرف نصب"},
    "إنّ": {"type": "حرف", "subtype": "حرف ناسخ"},
    "أنّ": {"type": "حرف", "subtype": "حرف ناسخ"},
    "كأنّ": {"type": "حرف", "subtype": "حرف ناسخ"},
    "كأن": {"type": "حرف", "subtype": "حرف ناسخ"},
    "لكنّ": {"type": "حرف", "subtype": "حرف ناسخ"},
    "لكن": {"type": "حرف", "subtype": "حرف ناسخ"},
    "ليت": {"type": "حرف", "subtype": "حرف ناسخ"},
    "لعلّ": {"type": "حرف", "subtype": "حرف ناسخ"},
    "لعل": {"type": "حرف", "subtype": "حرف ناسخ"},
    "لمّا": {"type": "حرف", "subtype": "حرف جزم"},
    "لما": {"type": "حرف", "subtype": "حرف جزم"},
    "كي": {"type": "حرف", "subtype": "حرف نصب"},
    "إذن": {"type": "حرف", "subtype": "حرف نصب"},
    "هل": {"type": "حرف", "subtype": "حرف استفهام"},
    "قد": {"type": "حرف", "subtype": "حرف"},
    "سوف": {"type": "حرف", "subtype": "حرف استقبال"},
    "بل": {"type": "حرف", "subtype": "حرف إضراب"},
    "ثم": {"type": "حرف", "subtype": "حرف عطف"},
    "ثمّ": {"type": "حرف", "subtype": "حرف عطف"},
    "أو": {"type": "حرف", "subtype": "حرف عطف"},
    "أم": {"type": "حرف", "subtype": "حرف عطف"},
    "لولا": {"type": "حرف", "subtype": "حرف امتناع"},
    "إلا": {"type": "حرف", "subtype": "أداة استثناء"},
    "الا": {"type": "حرف", "subtype": "أداة استثناء"},
    "يا": {"type": "حرف", "subtype": "حرف نداء"},
    "و": {"type": "حرف", "subtype": "حرف عطف"},  # refined by Layer 2
    "ف": {"type": "حرف", "subtype": "حرف عطف"},  # refined by Layer 2
}

# الأسماء الخمسة roots (without suffix)
FIVE_NOUNS_ROOTS: frozenset[str] = frozenset({
    "أب", "اب", "أخ", "اخ", "حم", "فو", "ذو",
    "أبو", "أخو", "حمو", "فو", "ذو",
    "أبا", "أخا", "حما", "فا", "ذا",
    "أبي", "أخي", "حمي", "في", "ذي",
})


# ---------------------------------------------------------------------------
# Section 3: Layer 1 — Context-Based Rule Elimination
# ---------------------------------------------------------------------------


def _strip(word: str) -> str:
    """Strip diacritics for matching."""
    return DIACRITICS_RE.sub("", word)


def _is_verb_reading(reading: dict) -> bool:
    return reading.get("type") == "فعل"


def _is_noun_reading(reading: dict) -> bool:
    return reading.get("type") == "اسم"


def _is_particle_reading(reading: dict) -> bool:
    return reading.get("type") in ("حرف", "أداة")


def _is_mudari_reading(reading: dict) -> bool:
    return reading.get("type") == "فعل" and reading.get("tense") == "مضارع"


def _apply_context_rules(
    words_data: list[tuple[str, list[dict]]],
    classified: list[WordClassification],
    idx: int,
) -> tuple[list[dict], str | None]:
    """Filter Buckwalter readings using context rules.

    Returns (filtered_readings, rule_name) where rule_name is the rule
    that applied, or None if no filtering was done.
    """
    word, analyses = words_data[idx]
    if not analyses:
        return analyses, None

    stripped = _strip(word)

    # Rule: known function word — override Buckwalter's type=None
    # These are common particles that Buckwalter doesn't tag properly.
    if stripped in KNOWN_FUNCTION_WORDS:
        override = KNOWN_FUNCTION_WORDS[stripped]
        # Build a synthetic reading from the first Buckwalter reading + override
        base = analyses[0].copy()
        base["type"] = override["type"]
        base["subtype"] = override["subtype"]
        # Clear verb-specific fields
        base["tense"] = None
        base["voice"] = None
        base["mood"] = None
        return [base], "known_function_word"

    # Rule: single reading — no disambiguation needed
    if len(analyses) == 1:
        return analyses, "single_reading"

    # Get previous classified word (if any)
    prev: WordClassification | None = classified[idx - 1] if idx > 0 else None
    prev_stripped = _strip(prev.word) if prev else ""

    # Rule: after حرف جر → must be اسم
    if prev and (
        prev_stripped in STANDALONE_PREPOSITIONS
        or prev.subtype == "حرف جر"
    ):
        nouns = [a for a in analyses if _is_noun_reading(a)]
        if nouns:
            return nouns, "after_preposition"

    # Rule: after لم / لمّا → must be فعل مضارع
    if prev and prev.subtype == "حرف جزم":
        mudari = [a for a in analyses if _is_mudari_reading(a)]
        if mudari:
            return mudari, "after_jazm_particle"

    # Rule: after أن/لن/كي/إذن → must be فعل مضارع
    if prev and prev.subtype == "حرف نصب":
        mudari = [a for a in analyses if _is_mudari_reading(a)]
        if mudari:
            return mudari, "after_nasb_particle"

    # Rule: after ناسخ (كان/إنّ) → prefer noun readings
    if prev and (
        prev_stripped in KANA_SISTERS
        or prev.subtype == "حرف ناسخ"
    ):
        nouns = [a for a in analyses if _is_noun_reading(a)]
        if nouns:
            return nouns, "after_nasikh"

    # Rule: after a verb → prefer noun readings (subject/object position)
    if prev and prev.word_type == "فعل":
        nouns = [a for a in analyses if _is_noun_reading(a)]
        if nouns:
            return nouns, "after_verb"

    # Rule: after لا النافية للجنس / لا + potential → prefer noun
    if prev and prev_stripped == "لا" and prev.word_type == "حرف":
        nouns = [a for a in analyses if _is_noun_reading(a)]
        if nouns:
            return nouns, "after_laa"

    # Rule: nominal sentence continuation — after a noun with no verb
    # before it, prefer noun readings (predicate of nominal sentence).
    # Skip if this word has a clear particle reading (preposition, etc.)
    if prev and prev.word_type == "اسم":
        has_verb = any(c.word_type == "فعل" for c in classified)
        if not has_verb:
            # Don't apply if the word has a حرف reading (like في, من, etc.)
            has_particle = any(_is_particle_reading(a) for a in analyses)
            if not has_particle:
                nouns = [a for a in analyses if _is_noun_reading(a)]
                if nouns:
                    return nouns, "nominal_continuation"

    # Rule: sentence-initial verb preference
    if idx == 0:
        verbs = [a for a in analyses if _is_verb_reading(a)]
        if verbs:
            nouns = [a for a in analyses if _is_noun_reading(a)]
            if nouns and verbs:
                return verbs, "verb_initial_preference"

    return analyses, None


def _select_best_reading(analyses: list[dict]) -> tuple[dict, int]:
    """Pick the best reading from filtered analyses.

    Buckwalter orders readings roughly by frequency, so the first
    reading is usually the most common. We prefer active voice over
    passive as a tiebreaker.
    """
    if not analyses:
        return {}, 0

    # Prefer active voice when multiple verb readings exist
    active = [a for a in analyses if a.get("voice") != "مبني للمجهول"]
    if active and any(_is_verb_reading(a) for a in active):
        return active[0], 0

    return analyses[0], 0


def _build_word_classification(
    word: str,
    reading: dict,
    reading_index: int,
    total_readings: int,
    rule: str | None,
) -> WordClassification:
    """Build a WordClassification from a selected Buckwalter reading."""
    # Determine verb form if it's a verb
    verb_form = None
    if reading.get("type") == "فعل" and reading.get("vocalized"):
        try:
            buck = pyaramorph.buckwalter.uni2buck(reading["vocalized"])
            verb_form = detect_verb_form(buck)
        except Exception:
            pass

    return WordClassification(
        word=word,
        vocalized=reading.get("vocalized"),
        lemma=reading.get("lemma"),
        root=reading.get("root"),
        pattern=reading.get("pattern"),
        word_type=reading.get("type"),
        subtype=reading.get("subtype"),
        tense=reading.get("tense"),
        voice=reading.get("voice"),
        mood=reading.get("mood"),
        gender=reading.get("gender"),
        number=reading.get("number"),
        definiteness=reading.get("definiteness"),
        noun_class=reading.get("noun_class"),
        diptote=reading.get("diptote", False),
        prefixes=reading.get("prefixes", []),
        suffixes=reading.get("suffixes", []),
        subject_suffix=reading.get("subject_suffix"),
        verb_form=verb_form,
        reading_index=reading_index,
        total_readings=total_readings,
        disambiguation_rule=rule,
    )


# ---------------------------------------------------------------------------
# Section 4: Layer 2 — Particle Decision Trees
# ---------------------------------------------------------------------------


@dataclass
class ParticleContext:
    """Full sentence context for particle disambiguation."""

    particle: str
    idx: int
    words: list[WordClassification]
    raw_analyses: list[list[dict]]

    @property
    def before(self) -> WordClassification | None:
        return self.words[self.idx - 1] if self.idx > 0 else None

    @property
    def after(self) -> WordClassification | None:
        return self.words[self.idx + 1] if self.idx + 1 < len(self.words) else None

    @property
    def two_before(self) -> WordClassification | None:
        return self.words[self.idx - 2] if self.idx > 1 else None

    @property
    def two_after(self) -> WordClassification | None:
        return self.words[self.idx + 2] if self.idx + 2 < len(self.words) else None

    def is_sentence_initial(self) -> bool:
        for i in range(self.idx):
            if self.words[i].word_type not in ("حرف", "أداة", None):
                return False
        return True


def _classify_maa(ctx: ParticleContext) -> dict:
    """Disambiguate ما — 9 types (disambiguation.md § ما)."""
    before = ctx.before
    after = ctx.after
    before_s = _strip(before.word) if before else ""

    # 1. After إنّ sisters / ربّ / حيث / بعد → ما الكافة
    kaffa_triggers = {
        "إن", "إنّ", "أن", "أنّ", "كأن", "كأنّ", "لكن", "لكنّ",
        "ليت", "لعل", "لعلّ", "رب", "ربّ", "حيث", "بعد",
    }
    if before_s in kaffa_triggers:
        return {"type": "ما الكافة (زائدة)", "effect": "كفّت العامل عن العمل"}

    # 2. Before أفعلَ pattern → ما التعجبية
    if after and after.word_type == "فعل" and after.tense == "ماضٍ":
        if after.verb_form == "IV" or (after.vocalized and (
            after.vocalized.startswith("أَ") or after.vocalized.startswith("أ")
        )):
            # Check if there's an object after (accusative) — exclamation pattern
            return {"type": "ما التعجبية", "effect": "مبتدأ في محل رفع"}

    # 3. Before verb (مضارع مجزوم) with both verbs jussive → ما الشرطية
    # (Hard to fully detect without case info; check if after-verb looks conditional)
    if after and after.word_type == "فعل" and after.tense == "مضارع":
        # Check if there's a second verb that could be jawab al-shart
        if ctx.two_after and ctx.two_after.word_type == "فعل":
            return {"type": "ما الشرطية", "effect": "اسم شرط جازم مبني"}

    # 4. Sentence-initial + interrogative context → ما الاستفهامية
    if ctx.is_sentence_initial() and after and after.word_type in ("اسم", "حرف", None):
        # "ما هذا" / "ما الذي" patterns
        if after.subtype in ("اسم إشارة", "اسم موصول"):
            return {"type": "ما الاستفهامية", "effect": "اسم استفهام مبني"}

    # 5. Before verb + can be masdar → ما المصدرية
    if after and after.word_type == "فعل" and after.tense == "ماضٍ":
        # Special: ما دام → مصدرية ظرفية
        after_s = _strip(after.word)
        if after_s in ("دام", "دمت", "دمنا"):
            return {"type": "ما المصدرية الظرفية", "effect": "مصدر مؤول في محل نصب ظرف"}
        # If not تعجبية (already checked above), consider مصدرية or نافية
        # Default to نافية for past verb (more common)

    # 6. Before nominal sentence + negation → ما الحجازية or النافية المهملة
    if after and after.word_type == "اسم":
        # Check if followed by noun + predicate (اسمية pattern)
        if ctx.two_after and ctx.two_after.word_type == "اسم":
            # Could be ما الحجازية — check conditions
            # Conditions: no إنْ الزائدة, خبر doesn't precede اسم, no repetition, no إلا
            return {"type": "ما النافية (حجازية/تميمية)", "effect": "قد تعمل عمل ليس"}

    # 7. Before verb → ما النافية
    if after and after.word_type == "فعل":
        return {"type": "ما النافية", "effect": "لا عمل لها مع الأفعال"}

    # 8. Can be replaced by الذي → ما الموصولة
    # Heuristic: if after a preposition or in a position where a noun is expected
    if before and before.subtype == "حرف جر":
        return {"type": "ما الموصولة", "effect": "اسم موصول بمعنى الذي"}

    # 9. Default → ما الزائدة
    return {"type": "ما الزائدة", "effect": "لا عمل لها"}


def _classify_laa(ctx: ParticleContext) -> dict:
    """Disambiguate لا — 7 types (disambiguation.md § لا)."""
    after = ctx.after
    before = ctx.before

    # 1. Before مضارع + command/prohibition context → لا الناهية
    if after and after.word_type == "فعل" and after.tense == "مضارع":
        # If sentence starts with لا + مضارع, likely ناهية
        if ctx.is_sentence_initial() or (before and before.word_type == "حرف"):
            return {"type": "لا الناهية", "effect": "حرف جزم — تجزم المضارع"}
        # Otherwise could be just negation
        return {"type": "لا النافية", "effect": "لا عمل لها"}

    # 2. Between two nouns (conjunction context) → لا العاطفة
    # Must check before نافية للجنس because both have noun-after
    if before and before.word_type in ("اسم", "فعل") and after and after.word_type == "اسم":
        # عاطفة: the before word is a noun (or there's a verb+subject before)
        if before.word_type == "اسم":
            return {"type": "لا العاطفة", "effect": "حرف عطف"}

    # 3. Before indefinite noun → لا النافية للجنس
    if after and after.word_type == "اسم" and after.definiteness != "معرفة":
        # Check conditions: اسمها نكرة, لم تُفصل عنه, لم تُسبق بحرف جر
        if not (before and before.subtype == "حرف جر"):
            return {"type": "لا النافية للجنس", "effect": "تعمل عمل إنّ"}

    # 4. Before noun (definite or other) → لا النافية
    if after and after.word_type == "اسم":
        return {"type": "لا النافية", "effect": "لا عمل لها"}

    # 5. Before past verb → لا النافية
    if after and after.word_type == "فعل" and after.tense == "ماضٍ":
        return {"type": "لا النافية", "effect": "لا عمل لها"}

    # 6. Default
    return {"type": "لا النافية", "effect": "لا عمل لها"}


def _classify_an_open(ctx: ParticleContext) -> dict:
    """Disambiguate أنْ (open hamza) — 4 types (disambiguation.md § أنْ)."""
    after = ctx.after

    # 1. Before مضارع → أنْ المصدرية الناصبة
    if after and after.word_type == "فعل" and after.tense == "مضارع":
        return {"type": "أنْ المصدرية الناصبة", "effect": "تنصب المضارع + مصدر مؤول"}

    # 2. After meaning-of-speech (without its letters) + before أمر → تفسيرية
    before = ctx.before
    if before and before.word_type == "فعل":
        # Verbs like أشار, أومأ, كتب (implying speech without using قال)
        # تفسيرية only with أمر or ماضٍ after, NOT مضارع
        if after and after.word_type == "فعل" and after.tense == "أمر":
            return {"type": "أنْ التفسيرية", "effect": "حرف لا محل له من الإعراب"}

    # 3. Before قد/سوف/السين/لا/لم or جامد verb → مخففة من أنّ
    if after:
        after_s = _strip(after.word)
        if after_s in ("قد", "سوف", "سـ", "لا", "لم"):
            return {"type": "أنْ المخففة من أنّ", "effect": "حرف مشبه بالفعل مخفف"}
        if after.word_type == "اسم":
            # After verb of knowledge/certainty → مخففة
            if before and _strip(before.word) in ("علم", "ظن", "حسب", "رأى"):
                return {"type": "أنْ المخففة من أنّ", "effect": "حرف مشبه بالفعل مخفف"}

    # 4. Default → زائدة
    return {"type": "أنْ الزائدة", "effect": "لا عمل لها"}


def _classify_in_broken(ctx: ParticleContext) -> dict:
    """Disambiguate إنْ (broken hamza) — 4 types (disambiguation.md § إنْ)."""
    after = ctx.after

    # 1. Before verb (مضارع or ماضٍ in conditional) → إنْ الشرطية
    if after and after.word_type == "فعل":
        return {"type": "إنْ الشرطية الجازمة", "effect": "أداة شرط جازمة — تجزم فعلين"}

    # 2. Negation context (+ إلا) → إنْ النافية
    # Check if إلا appears later
    for i in range(ctx.idx + 1, len(ctx.words)):
        if _strip(ctx.words[i].word) == "إلا" or _strip(ctx.words[i].word) == "الا":
            return {"type": "إنْ النافية", "effect": "بمعنى ما — لا عمل لها"}

    # 3. With لام الفارقة in predicate → إنْ المخففة من إنّ
    for i in range(ctx.idx + 1, min(ctx.idx + 5, len(ctx.words))):
        w = ctx.words[i]
        # Look for لام prefix on a word (لَـ at start)
        if w.vocalized and "لَ" in (w.vocalized[:2] if w.vocalized else ""):
            return {"type": "إنْ المخففة من إنّ", "effect": "حرف توكيد مخفف"}

    # 4. Default: if before noun, likely نافية; if ambiguous, شرطية
    if after and after.word_type == "اسم":
        return {"type": "إنْ النافية", "effect": "بمعنى ما — لا عمل لها"}

    return {"type": "إنْ الشرطية الجازمة", "effect": "أداة شرط جازمة — تجزم فعلين"}


def _classify_waw(ctx: ParticleContext) -> dict:
    """Disambiguate الواو — 6 types (disambiguation.md § الواو)."""
    after = ctx.after
    before = ctx.before

    # 1. Before مجرور + oath context → واو القسم
    if after and after.word_type == "اسم" and after.subtype == "علم":
        # واللهِ pattern
        return {"type": "واو القسم", "effect": "حرف جر"}
    # Also: والله with لفظ الجلالة
    if after and _strip(after.word) in ("الله", "اللّه", "الرحمن", "ربّ", "رب"):
        return {"type": "واو القسم", "effect": "حرف جر"}

    # 2. After verb + before pronoun/nominal sentence → واو الحال
    if before and before.word_type == "فعل" and after:
        if after.subtype == "ضمير" or (after.word_type == "اسم" and after.subtype != "علم"):
            # Check if it looks like a حالية clause (pronoun + verb/adj)
            if after.subtype == "ضمير":
                return {"type": "واو الحال", "effect": "حرف لا محل له من الإعراب"}

    # 3. Sentence-initial + before indefinite → واو ربّ
    if ctx.is_sentence_initial() and after and after.word_type == "اسم" and after.definiteness != "معرفة":
        return {"type": "واو ربّ", "effect": "حرف جر (ربّ محذوفة)"}

    # 4. Between independent sentences → واو الاستئناف
    # Heuristic: if before is a complete clause (verb+subject already done)
    if before and before.word_type in ("اسم", "فعل"):
        # Check if what follows starts a new clause
        if after and (after.word_type == "فعل" or (
            after.word_type == "اسم" and after.subtype not in ("صفة", None)
        )):
            # Could be عطف or استئناف — default to عطف (more common)
            pass

    # 5. Default → واو العطف (most common)
    return {"type": "واو العطف", "effect": "حرف عطف"}


def _classify_faa(ctx: ParticleContext) -> dict:
    """Disambiguate الفاء — 5 types (disambiguation.md § الفاء)."""
    after = ctx.after
    before = ctx.before

    # 1. After شرط condition → فاء الجزاء
    # Check if there's a conditional particle before
    for i in range(ctx.idx):
        w_s = _strip(ctx.words[i].word)
        if w_s in ("إن", "ان", "من", "ما", "مهما", "متى", "أين", "حيثما",
                    "كيفما", "إذا", "اذا", "لو"):
            return {"type": "فاء الجزاء", "effect": "رابطة لجواب الشرط"}

    # 2. After نفي/طلب + before مضارع → فاء السببية
    if before and before.word_type == "فعل" and before.tense == "أمر":
        if after and after.word_type == "فعل" and after.tense == "مضارع":
            return {"type": "فاء السببية", "effect": "ينتصب المضارع بعدها بأنْ مضمرة"}
    # After لا الناهية
    if before and _strip(before.word) == "لا":
        if after and after.word_type == "فعل" and after.tense == "مضارع":
            return {"type": "فاء السببية", "effect": "ينتصب المضارع بعدها بأنْ مضمرة"}

    # 3. Between مفردين or جملتين (ordering) → فاء العطف
    if before and after:
        if before.word_type == after.word_type:
            return {"type": "فاء العطف", "effect": "حرف عطف (ترتيب وتعقيب)"}

    # 4. Default → فاء العطف or استئنافية
    if after and after.word_type == "فعل":
        return {"type": "فاء العطف", "effect": "حرف عطف (ترتيب وتعقيب)"}

    return {"type": "فاء الاستئنافية", "effect": "حرف استئناف لا محل له"}


def _classify_min_man(ctx: ParticleContext) -> dict:
    """Disambiguate مِن/مَن (disambiguation.md § من)."""
    after = ctx.after
    before = ctx.before

    # Use Buckwalter POS to distinguish: PREP = مِن, INTERROG/REL_PRON = مَن
    # Check raw analyses for the word
    if ctx.idx < len(ctx.raw_analyses):
        readings = ctx.raw_analyses[ctx.idx]
        has_prep = any(r.get("subtype") == "حرف جر" or r.get("type") == "حرف" for r in readings)
        has_noun = any(r.get("type") == "اسم" for r in readings)

        if has_prep and not has_noun:
            # Definitely مِن (preposition)
            return _classify_min_prep(ctx)
        if has_noun and not has_prep:
            # Definitely مَن (noun)
            return _classify_man_noun(ctx)

    # Ambiguous: use context
    if after and after.word_type == "فعل":
        # من يدرس → مَن الشرطية/الموصولة
        return _classify_man_noun(ctx)
    # Default: preposition (more common)
    return _classify_min_prep(ctx)


def _classify_min_prep(ctx: ParticleContext) -> dict:
    """مِن as preposition — زائدة or أصلية."""
    after = ctx.after
    before = ctx.before

    # After نفي/استفهام/نهي + before نكرة → مِن الزائدة
    if before and _strip(before.word) in NEGATION_PARTICLES | {"هل", "أ"}:
        if after and after.word_type == "اسم" and after.definiteness != "معرفة":
            return {"type": "مِن الزائدة", "effect": "حرف جر زائد — ما بعدها مجرور لفظاً"}

    return {"type": "مِن حرف جر", "effect": "حرف جر أصلي"}


def _classify_man_noun(ctx: ParticleContext) -> dict:
    """مَن as noun — استفهامية, شرطية, or موصولة."""
    after = ctx.after

    # Interrogative context (sentence-initial, question)
    if ctx.is_sentence_initial():
        if after and after.word_type == "فعل":
            # Could be شرطية or استفهامية
            # If followed by two verbs → شرطية
            if ctx.two_after and ctx.two_after.word_type == "فعل":
                return {"type": "مَن الشرطية", "effect": "اسم شرط جازم مبني"}
            return {"type": "مَن الاستفهامية", "effect": "اسم استفهام مبني"}
        return {"type": "مَن الاستفهامية", "effect": "اسم استفهام مبني"}

    # After preposition or in non-initial position → موصولة
    return {"type": "مَن الموصولة", "effect": "اسم موصول بمعنى الذي"}


def _classify_baa(ctx: ParticleContext) -> dict:
    """Disambiguate الباء — detected from Buckwalter prefix."""
    before = ctx.before

    # After ليس / ما الحجازية → باء زائدة
    if before:
        before_s = _strip(before.word)
        if before_s == "ليس":
            return {"type": "الباء الزائدة", "effect": "حرف جر زائد — ما بعدها مجرور لفظاً"}
        if before_s == "ما" and before.particle_type and "حجازية" in before.particle_type:
            return {"type": "الباء الزائدة", "effect": "حرف جر زائد — ما بعدها مجرور لفظاً"}

    # كفى بالله → باء زائدة
    if before and _strip(before.word) in ("كفى", "يكفي"):
        return {"type": "الباء الزائدة", "effect": "حرف جر زائد — فاعل كفى مجرور لفظاً"}

    # Oath context → باء القسم
    after = ctx.after
    if after and _strip(after.word) in ("الله", "اللّه", "ربّ", "رب"):
        return {"type": "باء القسم", "effect": "حرف جر وقسم"}

    return {"type": "الباء حرف جر", "effect": "حرف جر أصلي"}


def _classify_lam(ctx: ParticleContext) -> dict:
    """Disambiguate اللام — detected from Buckwalter prefix."""
    after = ctx.after
    before = ctx.before

    # Before مجزوم + command → لام الأمر
    if after and after.word_type == "فعل" and after.tense == "مضارع":
        if after.mood == "مجزوم":
            return {"type": "لام الأمر", "effect": "حرف جزم"}

    # After ما كان / لم يكن → لام الجحود
    if before:
        b_s = _strip(before.word)
        if b_s in ("يكن", "يكون", "كان") and ctx.two_before:
            tb_s = _strip(ctx.two_before.word)
            if tb_s in ("ما", "لم"):
                return {"type": "لام الجحود", "effect": "حرف جر + نصب بأنْ مضمرة"}

    # With إنّ in sentence → check if this is لام مزحلقة
    for i in range(ctx.idx):
        if _strip(ctx.words[i].word) in ("إنّ", "إن") and ctx.words[i].word_type == "حرف":
            return {"type": "اللام المزحلقة", "effect": "لام الابتداء زُحلقت إلى الخبر"}

    # Before مضارع → لام التعليل
    if after and after.word_type == "فعل" and after.tense == "مضارع":
        return {"type": "لام التعليل", "effect": "حرف جر + نصب بأنْ مضمرة"}

    # Sentence-initial on مبتدأ → لام الابتداء
    if ctx.is_sentence_initial() and after and after.word_type == "اسم":
        return {"type": "لام الابتداء", "effect": "حرف توكيد لا عمل له"}

    return {"type": "اللام حرف جر", "effect": "حرف جر أصلي"}


def _classify_al(ctx: ParticleContext) -> dict:
    """Disambiguate أل — detected from Buckwalter DET prefix."""
    wc = ctx.words[ctx.idx]

    # On active/passive participle working as relative → أل الموصولة
    if wc.noun_class in ("اسم فاعل", "اسم مفعول"):
        # If participle has an object after it → working participle → أل الموصولة
        after = ctx.after
        if after and after.word_type == "اسم" and after.definiteness != "معرفة":
            return {"type": "أل الموصولة", "effect": "اسم موصول بمعنى الذي"}

    # Default → أل التعريف (covers عهدية, جنسية, استغراقية — hard to distinguish without semantics)
    return {"type": "أل التعريف", "effect": "حرف تعريف"}


def _classify_anna_inna(ctx: ParticleContext) -> dict:
    """Disambiguate أنّ/إنّ المشددتان (disambiguation.md § أنّ وإنّ)."""
    before = ctx.before

    # Sentence-initial or after قال → إنّ بالكسر
    if ctx.is_sentence_initial():
        return {"type": "إنّ", "effect": "حرف توكيد — تنصب الاسم وترفع الخبر"}

    if before and _strip(before.word) in ("قال", "قالت", "قالوا", "يقول", "تقول"):
        return {"type": "إنّ", "effect": "حرف توكيد — تنصب الاسم وترفع الخبر"}

    # After ألا الاستفتاحية → إنّ
    if before and _strip(before.word) in ("ألا", "الا"):
        return {"type": "إنّ", "effect": "حرف توكيد — تنصب الاسم وترفع الخبر"}

    # Otherwise → أنّ بالفتح (مصدر مؤول)
    return {"type": "أنّ", "effect": "حرف توكيد — مصدر مؤول مع معموليها"}


def _classify_jaala(ctx: ParticleContext) -> dict:
    """Disambiguate جعل — 3 types (disambiguation.md § جعل)."""
    after = ctx.after

    # Before مضارع without أن → أفعال الشروع
    if after and after.word_type == "فعل" and after.tense == "مضارع":
        return {"type": "جعل من أفعال الشروع", "effect": "تعمل عمل كاد — ترفع الاسم وتنصب الخبر جملة فعلية"}

    # Before two accusatives (noun + adjective/noun) → تحويل
    if after and ctx.two_after:
        if after.word_type == "اسم" and ctx.two_after.word_type == "اسم":
            return {"type": "جعل بمعنى صيّر", "effect": "تنصب مفعولين"}

    # Before single object → خلق
    if after and after.word_type == "اسم":
        return {"type": "جعل بمعنى خلق", "effect": "فعل متعدٍّ لمفعول واحد"}

    return {"type": "جعل", "effect": "فعل"}


def _classify_hatta(ctx: ParticleContext) -> dict:
    """Disambiguate حتى — 3 types (جارة / ناصبة-ابتدائية / عاطفة)."""
    after = ctx.after
    if not after:
        return {"type": "حتى الجارة", "effect": "حرف جر — انتهاء الغاية"}

    # Before مضارع → ناصبة (بأنْ مضمرة) or ابتدائية (رفع = حال)
    if after.word_type == "فعل" and after.tense in ("مضارع", "مضارع مرفوع", "مضارع منصوب"):
        if after.mood == "منصوب" or after.tense == "مضارع منصوب":
            return {"type": "حتى الناصبة", "effect": "حرف نصب — غاية أو تعليل (بأنْ مضمرة)"}
        return {"type": "حتى الابتدائية", "effect": "حرف ابتداء — الفعل بعدها مرفوع (حال)"}

    # Before اسم → جارة
    if after.word_type == "اسم":
        return {"type": "حتى الجارة", "effect": "حرف جر — انتهاء الغاية (لا تجرّ إلا آخراً أو متصلاً بالآخر)"}

    # Before جملة (ماضٍ / اسمية) → ابتدائية
    return {"type": "حتى الابتدائية", "effect": "حرف ابتداء لا عمل لها"}


def _classify_qad(ctx: ParticleContext) -> dict:
    """Disambiguate قد — different meaning with ماضٍ vs مضارع."""
    after = ctx.after
    if not after:
        return {"type": "قد", "effect": "حرف"}

    if after.word_type == "فعل":
        if after.tense == "ماضٍ":
            return {"type": "قد التحقيقية", "effect": "حرف تحقيق — أو تقريب الماضي من الحال"}
        if after.tense in ("مضارع", "مضارع مرفوع"):
            return {"type": "قد مع المضارع", "effect": "حرف — تقليل أو تكثير أو توقع"}

    return {"type": "قد", "effect": "حرف"}


def _classify_law(ctx: ParticleContext) -> dict:
    """Disambiguate لو — 5 meanings (شرطية / مصدرية / تمنٍّ / عرض / تقليل)."""
    before = ctx.before
    after = ctx.after

    # After وددت / يودّ / تمنّى → لو المصدرية (= أنْ)
    if before and _strip(before.word) in ("ودّ", "ود", "وددت", "يودّ", "يود", "تودّ", "تمنّى"):
        return {"type": "لو المصدرية", "effect": "حرف مصدري (= أنْ)"}

    # لو + أنّ → شرطية (typically)
    if after and _strip(after.word) in ("أنّ", "أن", "أنّه", "أنه"):
        return {"type": "لو الشرطية", "effect": "حرف شرط للماضي — لما كان سيقع لوقوع غيره"}

    # Default with فعل → شرطية
    if after and after.word_type == "فعل":
        return {"type": "لو الشرطية", "effect": "حرف شرط للماضي — لما كان سيقع لوقوع غيره"}

    # لو + اسم (no verb context) → could be تمنٍّ
    return {"type": "لو الشرطية", "effect": "حرف شرط للماضي"}


def _classify_idha(ctx: ParticleContext) -> dict:
    """Disambiguate إذا — فجائية vs شرطية ظرفية."""
    before = ctx.before
    after = ctx.after

    # After فاء + before اسمية → فجائية
    if before and _strip(before.word) in ("ف", "فـ"):
        return {"type": "إذا الفجائية", "effect": "حرف مفاجأة — تدخل على الجملة الاسمية"}

    # After فعل (خرجت فإذا) → فجائية
    if before and before.word_type == "فعل":
        return {"type": "إذا الفجائية", "effect": "حرف مفاجأة — تدخل على الجملة الاسمية"}

    # Default → شرطية ظرفية
    return {"type": "إذا الشرطية", "effect": "ظرف للمستقبل مضمّن معنى الشرط — خافض لشرطه منصوب بجوابه"}


def _classify_hal(ctx: ParticleContext) -> dict:
    """Disambiguate هل — استفهامية (الأصل) vs نافية."""
    after = ctx.after

    # هل + استثناء مفرّغ → نافية
    if after and _strip(after.word) in ("جزاء", "يجزى"):
        return {"type": "هل النافية", "effect": "حرف نفي (= ما)"}

    return {"type": "هل الاستفهامية", "effect": "حرف استفهام — للتصديق فقط (تجعل المضارع مستقبلاً)"}


def _classify_aw(ctx: ParticleContext) -> dict:
    """Disambiguate أو — 12 meanings. Simplified to most impactful branches."""
    before = ctx.before
    after = ctx.after

    # After طلب → تخيير or إباحة
    if before and before.word_type == "فعل" and before.tense in ("أمر", "فعل أمر"):
        return {"type": "أو للتخيير/الإباحة", "effect": "حرف عطف — تخيير (لا جمع) أو إباحة (يجوز الجمع)"}

    # Before مضارع منصوب → بمعنى إلى أن / إلا أن
    if after and after.word_type == "فعل" and after.mood == "منصوب":
        return {"type": "أو الناصبة", "effect": "حرف — بمعنى إلى أن أو إلا أن (المضارع منصوب بأنْ مضمرة)"}

    # Default → عطف (شك / إبهام / تقسيم / إضراب)
    return {"type": "أو العاطفة", "effect": "حرف عطف — لأحد الشيئين (شك/إبهام/تقسيم/إضراب)"}


def _classify_fi(ctx: ParticleContext) -> dict:
    """Disambiguate في — default ظرفية, with other meanings."""
    # في is almost always ظرفية — the 9 other meanings are hard to detect without semantics
    return {"type": "في الظرفية", "effect": "حرف جر — ظرفية (مكانية/زمانية/مجازية)"}


def _classify_an(ctx: ParticleContext) -> dict:
    """Disambiguate عن — default مجاوزة."""
    return {"type": "عن المجاوزة", "effect": "حرف جر — مجاوزة وبُعد"}


def _classify_ala(ctx: ParticleContext) -> dict:
    """Disambiguate على — default استعلاء."""
    return {"type": "على الاستعلاء", "effect": "حرف جر — استعلاء (حقيقي أو مجازي)"}


def _classify_ila(ctx: ParticleContext) -> dict:
    """Disambiguate إلى — default انتهاء الغاية."""
    return {"type": "إلى لانتهاء الغاية", "effect": "حرف جر — انتهاء الغاية"}


def _classify_thumma(ctx: ParticleContext) -> dict:
    """ثمّ — always عاطفة (ترتيب + تراخي)."""
    return {"type": "ثمّ العاطفة", "effect": "حرف عطف — ترتيب وتراخي"}


def _classify_ka(ctx: ParticleContext) -> dict:
    """الكاف — default تشبيه."""
    return {"type": "الكاف للتشبيه", "effect": "حرف جر — تشبيه"}


def _disambiguate_particle(particle: str, ctx: ParticleContext) -> dict:
    """Top-level particle disambiguation router."""
    stripped = _strip(particle)

    dispatch: dict[str, type] = {
        # Original 9 particles
        "ما": _classify_maa,
        "لا": _classify_laa,
        "أن": _classify_an_open,
        "ان": _classify_an_open,
        "إن": _classify_in_broken,
        "و": _classify_waw,
        "ف": _classify_faa,
        "من": _classify_min_man,
        "جعل": _classify_jaala,
        # New particles from مغني اللبيب audit
        "حتى": _classify_hatta,
        "قد": _classify_qad,
        "لقد": _classify_qad,
        "لو": _classify_law,
        "إذا": _classify_idha,
        "اذا": _classify_idha,
        "هل": _classify_hal,
        "أو": _classify_aw,
        "او": _classify_aw,
        "في": _classify_fi,
        "عن": _classify_an,
        "على": _classify_ala,
        "إلى": _classify_ila,
        "الى": _classify_ila,
        "ثم": _classify_thumma,
        "ثمّ": _classify_thumma,
    }

    fn = dispatch.get(stripped)
    if fn:
        return fn(ctx)

    # Handle إنّ/أنّ (shadda variants)
    if stripped in ("إنّ", "أنّ"):
        return _classify_anna_inna(ctx)

    return {"type": stripped, "effect": ""}


def _needs_particle_disambiguation(wc: WordClassification) -> bool:
    """Check if a word needs particle disambiguation."""
    stripped = _strip(wc.word)
    if stripped in AMBIGUOUS_PARTICLES:
        return True
    # Also check words classified as حرف that could be multi-function
    if wc.word_type == "حرف" and stripped in (
        "إنّ", "أنّ", "إن", "أن", "ما", "لا", "من", "و", "ف",
        # New from مغني اللبيب audit
        "حتى", "قد", "لقد", "لو", "إذا", "اذا", "هل",
        "أو", "او", "في", "عن", "على", "إلى", "الى",
        "ثم", "ثمّ",
    ):
        return True
    return False


# ---------------------------------------------------------------------------
# Section 5: Layer 3 — Post-Processing
# ---------------------------------------------------------------------------


def _determine_declinability(wc: WordClassification) -> tuple[str, str | None]:
    """Determine if a word is مبني or مُعرب, and what it's built on."""
    # --- Particles: always مبني ---
    if wc.word_type in ("حرف", "أداة"):
        return "مبني", "السكون"

    # --- Verbs ---
    if wc.word_type == "فعل":
        if wc.tense == "ماضٍ":
            # Check subject suffix for build vowel
            suffix = wc.subject_suffix
            if suffix:
                desc = suffix.get("desc", "")
                number = suffix.get("number", "")
                person = suffix.get("person")
                # واو الجماعة → مبني على الضم
                if number == "جمع" and person == 3 and suffix.get("gender") == "مذكر":
                    return "مبني", "الضم"
                # تاء الفاعل, نا, نون النسوة → مبني على السكون
                if person in (1, 2) or (person == 3 and number == "جمع" and suffix.get("gender") == "مؤنث"):
                    return "مبني", "السكون"
            # Default: مبني على الفتح
            return "مبني", "الفتح"

        if wc.tense == "أمر":
            return "مبني", "السكون"

        if wc.tense == "مضارع":
            # Check for نون النسوة or نون التوكيد
            pos_raw = ""
            # Normally معرب
            return "مُعرب", None

    # --- Nouns ---
    if wc.word_type == "اسم":
        stripped = _strip(wc.word)
        # Check MABNI_NOUNS
        if stripped in MABNI_NOUNS:
            return "مبني", "السكون"

        # Check subtype
        if wc.subtype in ("ضمير", "اسم إشارة", "اسم موصول", "اسم استفهام"):
            return "مبني", "السكون"

        # Default: مُعرب
        return "مُعرب", None

    # Default
    return "مُعرب", None


def _determine_sentence_type(words: list[WordClassification]) -> str:
    """Determine sentence type (اسمية / فعلية)."""
    for wc in words:
        stripped = _strip(wc.word)

        # Skip leading particles
        if wc.word_type in ("حرف", "أداة"):
            # إنّ sisters make it اسمية
            if wc.subtype == "حرف ناسخ" or stripped in INNA_UNAMBIGUOUS:
                return "جملة اسمية"
            # ما التعجبية is مبتدأ → اسمية
            if wc.particle_type and "تعجبية" in wc.particle_type:
                return "جملة اسمية"
            # ما الشرطية/الاستفهامية are اسم → depends on what follows
            if wc.particle_type and any(k in wc.particle_type for k in ("شرطية", "استفهامية", "موصولة")):
                return "جملة اسمية"
            continue

        if wc.word_type == "فعل":
            return "جملة فعلية"
        if wc.word_type == "اسم":
            return "جملة اسمية"

    return "جملة اسمية"  # Default


def _identify_nawasikh(words: list[WordClassification]) -> list[dict]:
    """Identify النواسخ in the sentence."""
    result = []
    for idx, wc in enumerate(words):
        stripped = _strip(wc.word)

        # كان وأخواتها
        if stripped in KANA_SISTERS and wc.word_type == "فعل":
            result.append({"word": wc.word, "index": idx, "type": "كان وأخواتها"})
            continue

        # كان sisters requiring negation
        if stripped in KANA_NEGATION_SISTERS and wc.word_type == "فعل":
            # Check if preceded by negation
            if idx > 0:
                prev_s = _strip(words[idx - 1].word)
                if prev_s in NEGATION_PARTICLES:
                    result.append({"word": wc.word, "index": idx, "type": "كان وأخواتها"})
            continue

        # إنّ وأخواتها — check subtype or unambiguous set
        if wc.subtype == "حرف ناسخ" or stripped in INNA_UNAMBIGUOUS:
            if wc.word_type in ("حرف", "أداة", None):
                result.append({"word": wc.word, "index": idx, "type": "إنّ وأخواتها"})
                continue

        # كاد وأخواتها
        if stripped in KAAD_ALL and wc.word_type == "فعل":
            if stripped in KAAD_MUQARABA:
                result.append({"word": wc.word, "index": idx, "type": "كاد وأخواتها (مقاربة)"})
            elif stripped in KAAD_RAJAA:
                result.append({"word": wc.word, "index": idx, "type": "كاد وأخواتها (رجاء)"})
            elif stripped in KAAD_SHUROO:
                # Distinguish from regular verb use — شروع only if followed by مضارع
                if idx + 1 < len(words) and words[idx + 1].word_type == "فعل" and words[idx + 1].tense == "مضارع":
                    result.append({"word": wc.word, "index": idx, "type": "كاد وأخواتها (شروع)"})
            continue

        # ظنّ وأخواتها
        if stripped in ZANNA_ALL and wc.word_type == "فعل":
            if stripped in ZANNA_YAQEEN:
                result.append({"word": wc.word, "index": idx, "type": "ظنّ وأخواتها (يقين)"})
            elif stripped in ZANNA_RUJHAN:
                result.append({"word": wc.word, "index": idx, "type": "ظنّ وأخواتها (رجحان)"})
            elif stripped in ZANNA_TAHWEEL:
                result.append({"word": wc.word, "index": idx, "type": "ظنّ وأخواتها (تحويل)"})
            continue

    return result


def _determine_morph_class(wc: WordClassification) -> str | None:
    """Determine morphological class for case-sign selection."""
    if wc.word_type != "اسم":
        return None

    # ممنوع من الصرف
    if wc.diptote:
        return "ممنوع من الصرف"

    # Check vocalized form for مقصور/منقوص
    voc = wc.vocalized or ""
    if voc:
        try:
            buck = pyaramorph.buckwalter.uni2buck(voc)
        except Exception:
            buck = ""
        if buck:
            # مقصور: ends in ألف (Y or A at end)
            # But NOT if the A is just the tanwin carrier (ألف التنوين)
            # — tanwin fatha is "F" in Buckwalter, and the alif before it is not مقصور
            has_tanwin_alif = buck.endswith("AF") or buck.endswith("aAF")
            stripped_buck = buck.rstrip("FNK")  # Remove tanwin
            if not has_tanwin_alif and stripped_buck.endswith(("Y", "aY", "A")) and len(stripped_buck) > 2:
                return "مقصور"
            # منقوص: ends in ياء (y at end with kasra before)
            if stripped_buck.endswith(("iy", "iy~")):
                return "منقوص"

    # الأسماء الخمسة
    stripped = _strip(wc.word)
    if stripped in FIVE_NOUNS_ROOTS:
        return "الأسماء الخمسة"

    # Check number for sound plurals
    if wc.number == "جمع مذكر سالم":
        return "جمع مذكر سالم"
    if wc.number == "جمع مؤنث سالم":
        return "جمع مؤنث سالم"
    if wc.number == "مثنى":
        return "مثنى"

    return "صحيح"


def _fill_transitivity(wc: WordClassification) -> None:
    """Fill in transitivity for a verb WordClassification."""
    if wc.transitivity:
        return

    # Try Qabas lookup
    if wc.vocalized:
        result = lookup_transitivity(wc.vocalized)
        if result:
            wc.transitivity, wc.transitivity_source = result
            return

    # Heuristic by form
    intransitive_forms = {"V", "VI", "VII", "IX"}
    if wc.verb_form in intransitive_forms:
        wc.transitivity = "لازم"
        wc.transitivity_source = "heuristic"
    elif wc.voice == "مبني للمجهول":
        wc.transitivity = "مبني للمجهول (أصله متعدٍّ)"
        wc.transitivity_source = "heuristic"
    else:
        wc.transitivity = "متعدٍّ"
        wc.transitivity_source = "heuristic"


# ---------------------------------------------------------------------------
# Section 6: Orchestrator
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(r"analysis for:\s+(\S+)")


def _extract_word(header: str) -> str:
    """Extract original word from pyaramorph header."""
    m = _HEADER_RE.match(header)
    return m.group(1) if m else header


def classify_sentence(text: str) -> SentenceClassification:
    """Perform deterministic Pass 1 classification on an Arabic sentence.

    Returns a SentenceClassification with per-word type, subtype, tense,
    voice, gender, number, definiteness, مبني/معرب, particle disambiguation,
    tashkeel, sentence type, and النواسخ identification.
    """
    if not text or not text.strip():
        return SentenceClassification(original_text=text)

    # Step 1: Raw Buckwalter analysis
    raw_results = analyzer.analyze_text(text)
    if not raw_results:
        return SentenceClassification(original_text=text)

    words_data: list[tuple[str, list[dict]]] = []
    for entry in raw_results:
        header = entry[0]
        word = _extract_word(header)
        solutions = entry[1:]
        parsed = [parse_solution(sol) for sol in solutions]
        words_data.append((word, parsed))

    # Step 2: Left-to-right Layer 1 — context rules to select readings
    classified: list[WordClassification] = []
    for idx, (word, analyses) in enumerate(words_data):
        if not analyses:
            # Unknown word — not in Buckwalter DB
            wc = WordClassification(
                word=word,
                total_readings=0,
                disambiguation_rule="unknown_word",
            )
            classified.append(wc)
            continue

        filtered, rule = _apply_context_rules(words_data, classified, idx)
        if not filtered:
            filtered = analyses  # Fallback to all readings

        selected, reading_idx = _select_best_reading(filtered)
        wc = _build_word_classification(word, selected, reading_idx, len(analyses), rule)
        classified.append(wc)

    # Step 3: Second pass — Layer 2 particle disambiguation with full context
    all_raw = [analyses for _, analyses in words_data]
    for idx, wc in enumerate(classified):
        if _needs_particle_disambiguation(wc):
            ctx = ParticleContext(
                particle=wc.word,
                idx=idx,
                words=classified,
                raw_analyses=all_raw,
            )
            result = _disambiguate_particle(wc.word, ctx)
            wc.particle_type = result.get("type")
            wc.particle_effect = result.get("effect")

    # Step 4: Layer 3 post-processing
    for wc in classified:
        wc.declinable, wc.build_on = _determine_declinability(wc)
        if wc.word_type == "اسم":
            wc.morph_class = _determine_morph_class(wc)
        if wc.word_type == "فعل":
            _fill_transitivity(wc)

    # Step 5: Sentence-level classification
    sentence_type = _determine_sentence_type(classified)
    nawasikh = _identify_nawasikh(classified)
    vocalized = " ".join(wc.vocalized or wc.word for wc in classified)

    # Collect ambiguities
    ambiguities = []
    for wc in classified:
        if wc.total_readings > 3 and wc.disambiguation_rule is None:
            ambiguities.append({
                "word": wc.word,
                "total_readings": wc.total_readings,
                "selected_type": wc.word_type,
            })

    return SentenceClassification(
        original_text=text,
        vocalized_text=vocalized,
        sentence_type=sentence_type,
        nawasikh=nawasikh,
        words=classified,
        ambiguities=ambiguities,
    )
