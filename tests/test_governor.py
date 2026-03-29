"""Tests for the governor module — deterministic Pass 2 governor mapping."""



# ---------------------------------------------------------------------------
# Rule Group A: جملة فعلية
# ---------------------------------------------------------------------------


class TestVerbalSentence:
    def test_transitive_verb(self, governor_module):
        r = governor_module.map_governors("كتب الطالب الرسالة")
        assert r.words[0].role == "فعل"
        assert r.words[1].role == "فاعل"
        assert r.words[1].case == "رفع"
        assert r.words[2].role == "مفعول به"
        assert r.words[2].case == "نصب"

    def test_intransitive_verb(self, governor_module):
        r = governor_module.map_governors("ذهب الطالب")
        assert r.words[0].role == "فعل"
        assert r.words[1].role == "فاعل"
        assert r.words[1].case == "رفع"

    def test_verb_with_prep_phrase(self, governor_module):
        r = governor_module.map_governors("ذهب الطالب إلى المدرسة")
        assert r.words[1].role == "فاعل"
        assert r.words[2].role == "حرف جر"
        assert r.words[3].role == "اسم مجرور"
        assert r.words[3].case == "جر"

    def test_governor_is_verb(self, governor_module):
        r = governor_module.map_governors("كتب الطالب الرسالة")
        # فاعل and مفعول should point to the verb
        assert r.words[1].governor_index == 0
        assert r.words[2].governor_index == 0


# ---------------------------------------------------------------------------
# Rule Group B: جملة اسمية
# ---------------------------------------------------------------------------


class TestNominalSentence:
    def test_simple_nominal(self, governor_module):
        r = governor_module.map_governors("العلم نور")
        assert r.words[0].role == "مبتدأ"
        assert r.words[0].case == "رفع"
        assert r.words[0].governor == "الابتداء"
        assert r.words[1].role == "خبر"
        assert r.words[1].case == "رفع"


# ---------------------------------------------------------------------------
# Rule Group C: كان وأخواتها
# ---------------------------------------------------------------------------


class TestKana:
    def test_kana_basic(self, governor_module):
        r = governor_module.map_governors("كان الجو جميلا")
        assert r.words[0].role == "فعل ناسخ"
        assert "اسم" in r.words[1].role and "كان" in r.words[1].role
        assert r.words[1].case == "رفع"
        assert "خبر" in r.words[2].role and "كان" in r.words[2].role
        assert r.words[2].case == "نصب"

    def test_kana_governor_points_to_verb(self, governor_module):
        r = governor_module.map_governors("كان الجو جميلا")
        assert r.words[1].governor_index == 0
        assert r.words[2].governor_index == 0


# ---------------------------------------------------------------------------
# Rule Group D: إنّ وأخواتها
# ---------------------------------------------------------------------------


class TestInna:
    def test_inna_basic(self, governor_module):
        r = governor_module.map_governors("إن العلم نافع")
        assert r.words[0].role == "حرف ناسخ"
        assert "اسم" in r.words[1].role
        assert r.words[1].case == "نصب"
        assert "خبر" in r.words[2].role
        assert r.words[2].case == "رفع"


# ---------------------------------------------------------------------------
# Rule Group F: حرف الجر
# ---------------------------------------------------------------------------


class TestPrepositions:
    def test_preposition_governs_noun(self, governor_module):
        r = governor_module.map_governors("في المدرسة")
        assert r.words[1].role == "اسم مجرور"
        assert r.words[1].case == "جر"
        assert r.words[1].governor_index == 0

    def test_multiple_prepositions(self, governor_module):
        r = governor_module.map_governors("ذهب من البيت إلى المدرسة")
        # من البيت
        bait = [a for a in r.words if "بيت" in (a.word or "")][0]
        assert bait.case == "جر"
        # إلى المدرسة
        madrasa = [a for a in r.words if "مدرسة" in (a.word or "")][0]
        assert madrasa.case == "جر"


# ---------------------------------------------------------------------------
# Rule Group H: حروف النصب والجزم
# ---------------------------------------------------------------------------


class TestNasbJazm:
    def test_lam_jazm(self, governor_module):
        r = governor_module.map_governors("لم يكتب الطالب")
        assert r.words[0].role == "حرف جزم"
        assert r.words[1].case == "جزم"
        assert r.words[1].governor_index == 0

    def test_lan_nasb(self, governor_module):
        r = governor_module.map_governors("لن يذهب")
        assert r.words[0].role == "حرف نصب"
        assert r.words[1].case == "نصب"


# ---------------------------------------------------------------------------
# Rule Group I: لا النافية للجنس
# ---------------------------------------------------------------------------


class TestLaaNafiya:
    def test_laa_basic(self, governor_module):
        r = governor_module.map_governors("لا رجل في الدار")
        assert r.words[0].role == "لا النافية للجنس"
        assert "اسم لا" in r.words[1].role
        assert r.words[1].case == "نصب"
        assert r.words[3].role == "اسم مجرور"
        assert r.words[3].case == "جر"


# ---------------------------------------------------------------------------
# Hidden pronouns
# ---------------------------------------------------------------------------


class TestHiddenPronouns:
    def test_hidden_pronoun_past_3ms(self, governor_module):
        r = governor_module.map_governors("ذهب")
        verb = r.words[0]
        assert verb.hidden_pronoun is not None
        assert verb.hidden_pronoun["estimate"] == "هو"
        assert verb.hidden_pronoun["obligatory"] == "جوازاً"


# ---------------------------------------------------------------------------
# Confidence and ambiguities
# ---------------------------------------------------------------------------


class TestConfidence:
    def test_simple_sentence_all_high(self, governor_module):
        r = governor_module.map_governors("كتب الطالب الرسالة")
        for a in r.words:
            assert a.confidence == "high"
        assert len(r.ambiguities) == 0

    def test_no_ambiguities_simple(self, governor_module):
        r = governor_module.map_governors("العلم نور")
        assert len(r.ambiguities) == 0


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_includes_classification(self, governor_module):
        r = governor_module.map_governors("كتب الطالب")
        assert r.classification is not None
        assert r.classification.sentence_type == "جملة فعلية"

    def test_clause_type(self, governor_module):
        r = governor_module.map_governors("العلم نور")
        assert r.clause_type == "جملة اسمية"

    def test_empty_input(self, governor_module):
        r = governor_module.map_governors("")
        assert len(r.words) == 0


class TestEdgeCases:
    def test_single_noun(self, governor_module):
        r = governor_module.map_governors("كتاب")
        assert len(r.words) == 1

    def test_long_sentence(self, governor_module):
        r = governor_module.map_governors("ذهب الطالب إلى المدرسة في الصباح")
        assert r.clause_type == "جملة فعلية"
        assert len(r.words) >= 5
