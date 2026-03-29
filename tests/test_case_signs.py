"""Tests for Pass 3 (case signs) and Pass 4 (verification)."""



# ---------------------------------------------------------------------------
# Pass 3: Case Sign Assignment
# ---------------------------------------------------------------------------


class TestPrimarySigns:
    """Primary (أصلية) case signs."""

    def test_rafa_damma(self, governor_module):
        r = governor_module.full_irab("العلم نور")
        # العلم: مبتدأ/رفع → الضمة
        assert r.case_signs[0] is not None
        assert r.case_signs[0].sign == "الضمة"
        assert r.case_signs[0].sign_type == "أصلية"

    def test_nasb_fatha(self, governor_module):
        r = governor_module.full_irab("كتب الطالب الرسالة")
        # الرسالة: مفعول به/نصب → الفتحة
        assert r.case_signs[2] is not None
        assert r.case_signs[2].sign == "الفتحة"

    def test_jarr_kasra(self, governor_module):
        r = governor_module.full_irab("ذهب إلى المدرسة")
        # المدرسة: مجرور/جر → الكسرة
        school_idx = next(i for i, a in enumerate(r.governor_map.words) if "مجرور" in a.role)
        assert r.case_signs[school_idx].sign == "الكسرة"

    def test_jazm_sukun(self, governor_module):
        r = governor_module.full_irab("لم يكتب")
        # يكتب: مجزوم → السكون
        verb_idx = next(i for i, a in enumerate(r.governor_map.words) if a.case == "جزم")
        assert r.case_signs[verb_idx].sign == "السكون"


class TestSubsidiarySigns:
    """Subsidiary (فرعية) case signs."""

    def test_diptote_jarr_fatha(self, governor_module):
        r = governor_module.full_irab("ذهبت إلى أحمد")
        # أحمد: ممنوع من الصرف/جر → الفتحة نيابة عن الكسرة
        ahmad_idx = next(
            (i for i, a in enumerate(r.governor_map.words) if "مجرور" in a.role and "حمد" in a.word),
            None,
        )
        if ahmad_idx is not None:
            sign = r.case_signs[ahmad_idx]
            assert sign is not None
            assert sign.sign == "الفتحة"
            assert sign.sign_type == "فرعية"
            assert sign.note is not None and "نيابة" in sign.note


class TestNoSignForMabni:
    """مبني words should not get case signs."""

    def test_past_verb_no_sign(self, governor_module):
        r = governor_module.full_irab("كتب الطالب")
        # كتب is مبني → no sign
        assert r.case_signs[0] is None

    def test_particle_no_sign(self, governor_module):
        r = governor_module.full_irab("في المدرسة")
        # في is مبني → no sign
        assert r.case_signs[0] is None

    def test_known_particle_no_sign(self, governor_module):
        r = governor_module.full_irab("لم يكتب")
        # لم is مبني → no sign
        assert r.case_signs[0] is None


class TestEstimatedCase:
    """إعراب تقديري (estimated case)."""

    def test_regular_noun_not_estimated(self, governor_module):
        r = governor_module.full_irab("كتب الطالب")
        # الطالب is regular noun → not estimated
        sign = r.case_signs[1]
        assert sign is not None
        assert sign.estimated is False


# ---------------------------------------------------------------------------
# Pass 4: Verification
# ---------------------------------------------------------------------------


class TestVerification:
    def test_simple_sentence_passes(self, governor_module):
        r = governor_module.full_irab("كتب الطالب الرسالة")
        assert r.passed_verification is True
        assert len(r.verification) == 0

    def test_nominal_passes(self, governor_module):
        r = governor_module.full_irab("العلم نور")
        assert r.passed_verification is True

    def test_kana_passes(self, governor_module):
        r = governor_module.full_irab("كان الجو جميلا")
        assert r.passed_verification is True

    def test_inna_passes(self, governor_module):
        r = governor_module.full_irab("إن العلم نافع")
        assert r.passed_verification is True

    def test_jazm_passes(self, governor_module):
        r = governor_module.full_irab("لم يكتب الطالب")
        assert r.passed_verification is True


# ---------------------------------------------------------------------------
# Full i'rab Integration
# ---------------------------------------------------------------------------


class TestFullIrab:
    def test_empty_input(self, governor_module):
        r = governor_module.full_irab("")
        assert r.original_text == ""

    def test_returns_all_components(self, governor_module):
        r = governor_module.full_irab("كتب الطالب")
        assert r.governor_map is not None
        assert r.case_signs is not None
        assert r.verification is not None
        assert r.passed_verification is not None

    def test_signs_parallel_to_words(self, governor_module):
        r = governor_module.full_irab("كتب الطالب الرسالة")
        assert len(r.case_signs) == len(r.governor_map.words)

    def test_complete_analysis(self, governor_module):
        """Full pipeline test: Pass 1 → Pass 2 → Pass 3 → Pass 4."""
        r = governor_module.full_irab("كتب الطالب الرسالة")

        # Pass 1+2: governor map
        assert r.governor_map.clause_type == "جملة فعلية"
        assert r.governor_map.words[0].role == "فعل"
        assert r.governor_map.words[1].role == "فاعل"
        assert r.governor_map.words[1].case == "رفع"
        assert r.governor_map.words[2].role == "مفعول به"
        assert r.governor_map.words[2].case == "نصب"

        # Pass 3: signs
        assert r.case_signs[0] is None  # verb is مبني
        assert r.case_signs[1].sign == "الضمة"
        assert r.case_signs[2].sign == "الفتحة"

        # Pass 4: verification
        assert r.passed_verification is True
