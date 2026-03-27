"""Tests for parse_solution() — the core Buckwalter output parser."""

import pytest


class TestBasicParsing:
    """Verify extraction of vocalized form, lemma, POS, type, tense."""

    def test_past_verb(self, analyzer_module, analyzer):
        results = analyzer.analyze_text("كَتَبَ")
        assert results
        for sol in results[0][1:]:
            parsed = analyzer_module.parse_solution(sol)
            if parsed["type"] == "فعل" and parsed["tense"] == "ماضٍ":
                assert parsed["vocalized"] is not None
                assert parsed["lemma"] is not None
                return
        pytest.fail("No past verb reading found for كَتَبَ")

    def test_imperfect_verb(self, analyzer_module, analyzer):
        results = analyzer.analyze_text("يَكْتُبُ")
        assert results
        for sol in results[0][1:]:
            parsed = analyzer_module.parse_solution(sol)
            if parsed["type"] == "فعل" and parsed["tense"] == "مضارع":
                assert parsed["vocalized"] is not None
                return
        pytest.fail("No imperfect verb reading found for يَكْتُبُ")

    def test_noun(self, analyzer_module, analyzer):
        results = analyzer.analyze_text("كتاب")
        assert results
        for sol in results[0][1:]:
            parsed = analyzer_module.parse_solution(sol)
            if parsed["type"] == "اسم":
                assert parsed["vocalized"] is not None
                assert parsed["gender"] is not None
                assert parsed["number"] is not None
                return
        pytest.fail("No noun reading found for كتاب")

    def test_particle(self, analyzer_module, analyzer):
        results = analyzer.analyze_text("في")
        assert results
        for sol in results[0][1:]:
            parsed = analyzer_module.parse_solution(sol)
            if parsed["type"] == "حرف":
                assert parsed["subtype"] == "حرف جر"
                return
        pytest.fail("No particle reading found for في")

    def test_definite_noun(self, analyzer_module, analyzer):
        results = analyzer.analyze_text("الكتاب")
        assert results
        for sol in results[0][1:]:
            parsed = analyzer_module.parse_solution(sol)
            if parsed["type"] == "اسم" and parsed["definiteness"] == "معرفة":
                assert "أل" in parsed["prefixes"]
                return
        pytest.fail("No definite noun reading found for الكتاب")


class TestVoiceDetection:
    """Verify passive voice detection across verb forms."""

    def _find_verb_with_voice(self, analyzer_module, analyzer, word, expected_voice):
        """Helper: find a verb reading with the expected voice."""
        results = analyzer.analyze_text(word)
        assert results, f"No results for {word}"
        for sol in results[0][1:]:
            parsed = analyzer_module.parse_solution(sol)
            if parsed["type"] == "فعل" and parsed["voice"] == expected_voice:
                return parsed
        return None

    def test_form1_passive_past(self, analyzer_module, analyzer):
        parsed = self._find_verb_with_voice(
            analyzer_module, analyzer, "كُتِبَ", "مبني للمجهول"
        )
        assert parsed is not None, "كُتِبَ should have a passive reading"

    def test_form1_active_past(self, analyzer_module, analyzer):
        parsed = self._find_verb_with_voice(
            analyzer_module, analyzer, "كَتَبَ", "مبني للمعلوم"
        )
        assert parsed is not None, "كَتَبَ should have an active reading"

    def test_form2_passive_past(self, analyzer_module, analyzer):
        parsed = self._find_verb_with_voice(
            analyzer_module, analyzer, "عُلِّمَ", "مبني للمجهول"
        )
        assert parsed is not None, "عُلِّمَ should have a passive reading"

    def test_passive_imperfect(self, analyzer_module, analyzer):
        parsed = self._find_verb_with_voice(
            analyzer_module, analyzer, "يُكتَب", "مبني للمجهول"
        )
        assert parsed is not None, "يُكتَب should have a passive imperfect reading"

    def test_active_imperfect(self, analyzer_module, analyzer):
        parsed = self._find_verb_with_voice(
            analyzer_module, analyzer, "يَكتُب", "مبني للمعلوم"
        )
        assert parsed is not None, "يَكتُب should have an active imperfect reading"

    def test_passive_stems_loaded(self, analyzer_module):
        assert len(analyzer_module.PV_PASS_STEMS) > 100
        assert len(analyzer_module.IV_PASS_STEMS) > 1000


class TestGenderDetection:
    """Verify feminine noun lookup for مؤنث سماعي."""

    def _get_noun_gender(self, analyzer_module, analyzer, word):
        results = analyzer.analyze_text(word)
        if not results:
            return None
        for sol in results[0][1:]:
            parsed = analyzer_module.parse_solution(sol)
            if parsed["type"] == "اسم":
                return parsed["gender"]
        return None

    @pytest.mark.parametrize("word", ["شمس", "أرض", "نار", "حرب", "عين", "يد", "دار"])
    def test_feminine_samawi(self, analyzer_module, analyzer, word):
        gender = self._get_noun_gender(analyzer_module, analyzer, word)
        assert gender == "مؤنث", f"{word} should be مؤنث but got {gender}"

    @pytest.mark.parametrize("word", ["كتاب", "قلم"])
    def test_masculine_default(self, analyzer_module, analyzer, word):
        gender = self._get_noun_gender(analyzer_module, analyzer, word)
        assert gender == "مذكر", f"{word} should be مذكر but got {gender}"

    def test_feminine_nouns_loaded(self, analyzer_module):
        assert len(analyzer_module.FEMININE_NOUNS) > 50


class TestSuffixMapping:
    """Verify subject suffix extraction."""

    def test_third_person_masculine(self, analyzer_module, analyzer):
        # كَتَبَ with 3MS suffix
        results = analyzer.analyze_text("كَتَبَ")
        assert results
        for sol in results[0][1:]:
            parsed = analyzer_module.parse_solution(sol)
            if parsed["type"] == "فعل" and parsed["subject_suffix"]:
                suffix = parsed["subject_suffix"]
                assert suffix["desc"] in ("هو", "هي", "هم", "هنّ", "هما")
                return
        pytest.fail("No verb with subject suffix found for كَتَبَ")

    def test_feminine_noun_suffix(self, analyzer_module, analyzer):
        # مدرسة has NSUFF_FEM_SG
        results = analyzer.analyze_text("مدرسة")
        assert results
        for sol in results[0][1:]:
            parsed = analyzer_module.parse_solution(sol)
            if parsed["type"] == "اسم" and parsed["gender"] == "مؤنث":
                return
        pytest.fail("مدرسة should have a feminine reading via suffix")
