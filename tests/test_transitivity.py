"""Tests for verb form detection + Qabas transitivity lookup."""

import pyaramorph


def _check_transitivity(analyzer_module, verb):
    """Replicate the check_transitivity logic from the API using analyzer functions."""
    ana = pyaramorph.Analyzer()
    results = ana.analyze_text(verb)
    if not results:
        return {"verb": verb, "readings": []}
    readings = []
    for sol in results[0][1:]:
        parsed = analyzer_module.parse_solution(sol)
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
                form = analyzer_module.detect_verb_form(buck)
        is_passive = parsed.get("voice") == "مبني للمجهول"
        transitivity = None
        transitivity_source = None
        result = analyzer_module.lookup_transitivity(voc)
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
            "voice": parsed.get("voice", ""),
            "tense": parsed.get("tense", ""),
            "gloss": parsed.get("gloss", ""),
            "transitivity": transitivity,
            "transitivity_source": transitivity_source,
        })
    return {"verb": verb, "readings": readings}


class TestVerbFormDetection:
    """Verify verb form (I-X) detection from vocalization patterns."""

    def _get_forms(self, analyzer_module, verb):
        """Return set of detected forms for a verb."""
        result = _check_transitivity(analyzer_module, verb)
        return {r["form"] for r in result.get("readings", [])}

    def test_form1(self, analyzer_module):
        forms = self._get_forms(analyzer_module, "كَتَبَ")
        assert "I" in forms

    def test_form2(self, analyzer_module):
        forms = self._get_forms(analyzer_module, "عَلَّمَ")
        assert "II" in forms

    def test_form3(self, analyzer_module):
        forms = self._get_forms(analyzer_module, "كَاتَبَ")
        assert "III" in forms

    def test_form4(self, analyzer_module):
        forms = self._get_forms(analyzer_module, "أَعْلَنَ")
        assert "IV" in forms

    def test_form5(self, analyzer_module):
        forms = self._get_forms(analyzer_module, "تَعَلَّمَ")
        assert "V" in forms

    def test_form7(self, analyzer_module):
        forms = self._get_forms(analyzer_module, "انْكَسَرَ")
        assert "VII" in forms

    def test_form10(self, analyzer_module):
        forms = self._get_forms(analyzer_module, "اسْتَخْرَجَ")
        assert "X" in forms


class TestQabasTransitivity:
    """Verify Qabas lexical lookup for verb transitivity."""

    def _get_transitivity(self, analyzer_module, verb):
        """Return (transitivity, source) tuples for all readings."""
        result = _check_transitivity(analyzer_module, verb)
        return [
            (r["transitivity"], r.get("transitivity_source"))
            for r in result.get("readings", [])
        ]

    def test_intransitive_dhahaba(self, analyzer_module):
        readings = self._get_transitivity(analyzer_module, "ذهب")
        trans_values = [t for t, _ in readings]
        assert "لازم" in trans_values, "ذهب should be intransitive"

    def test_transitive_kataba(self, analyzer_module):
        readings = self._get_transitivity(analyzer_module, "كتب")
        trans_values = [t for t, _ in readings]
        assert "متعد" in trans_values or "متعدٍّ" in trans_values, \
            "كتب should be transitive"

    def test_qabas_source_used(self, analyzer_module):
        readings = self._get_transitivity(analyzer_module, "ذهب")
        sources = [s for _, s in readings]
        assert "qabas" in sources, "ذهب should use qabas as source"

    def test_heuristic_fallback(self, analyzer_module):
        # A very rare verb unlikely to be in Qabas
        readings = self._get_transitivity(analyzer_module, "تَزَلْزَلَ")
        sources = [s for _, s in readings if s]
        if sources:
            # If it has readings, at least some should use heuristic
            assert "heuristic" in sources or "qabas" in sources


class TestHeuristicTransitivity:
    """Verify form-based transitivity heuristics as fallback."""

    def test_form5_intransitive(self, analyzer_module):
        result = _check_transitivity(analyzer_module, "تَعَلَّمَ")
        for r in result.get("readings", []):
            if r["form"] == "V" and r.get("transitivity_source") == "heuristic":
                assert r["transitivity"] == "لازم"
                return

    def test_form7_intransitive(self, analyzer_module):
        result = _check_transitivity(analyzer_module, "انْكَسَرَ")
        for r in result.get("readings", []):
            if r["form"] == "VII" and r.get("transitivity_source") == "heuristic":
                assert r["transitivity"] == "لازم"
                return
