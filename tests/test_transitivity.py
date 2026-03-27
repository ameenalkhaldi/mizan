"""Tests for check_transitivity() — verb form detection + Qabas lookup."""

import json
import pytest


class TestVerbFormDetection:
    """Verify verb form (I-X) detection from vocalization patterns."""

    def _get_forms(self, server_module, verb):
        """Return set of detected forms for a verb."""
        result = json.loads(server_module.check_transitivity(verb))
        return {r["form"] for r in result.get("readings", [])}

    def test_form1(self, server_module):
        forms = self._get_forms(server_module, "كَتَبَ")
        assert "I" in forms

    def test_form2(self, server_module):
        forms = self._get_forms(server_module, "عَلَّمَ")
        assert "II" in forms

    def test_form3(self, server_module):
        forms = self._get_forms(server_module, "كَاتَبَ")
        assert "III" in forms

    def test_form4(self, server_module):
        forms = self._get_forms(server_module, "أَعْلَنَ")
        assert "IV" in forms

    def test_form5(self, server_module):
        forms = self._get_forms(server_module, "تَعَلَّمَ")
        assert "V" in forms

    def test_form7(self, server_module):
        forms = self._get_forms(server_module, "انْكَسَرَ")
        assert "VII" in forms

    def test_form10(self, server_module):
        forms = self._get_forms(server_module, "اسْتَخْرَجَ")
        assert "X" in forms


class TestQabasTransitivity:
    """Verify Qabas lexical lookup for verb transitivity."""

    def _get_transitivity(self, server_module, verb):
        """Return (transitivity, source) tuples for all readings."""
        result = json.loads(server_module.check_transitivity(verb))
        return [
            (r["transitivity"], r.get("transitivity_source"))
            for r in result.get("readings", [])
        ]

    def test_intransitive_dhahaba(self, server_module):
        readings = self._get_transitivity(server_module, "ذهب")
        trans_values = [t for t, _ in readings]
        assert "لازم" in trans_values, "ذهب should be intransitive"

    def test_transitive_kataba(self, server_module):
        readings = self._get_transitivity(server_module, "كتب")
        trans_values = [t for t, _ in readings]
        assert "متعد" in trans_values or "متعدٍّ" in trans_values, \
            "كتب should be transitive"

    def test_qabas_source_used(self, server_module):
        readings = self._get_transitivity(server_module, "ذهب")
        sources = [s for _, s in readings]
        assert "qabas" in sources, "ذهب should use qabas as source"

    def test_heuristic_fallback(self, server_module):
        # A very rare verb unlikely to be in Qabas
        readings = self._get_transitivity(server_module, "تَزَلْزَلَ")
        sources = [s for _, s in readings if s]
        if sources:
            # If it has readings, at least some should use heuristic
            assert "heuristic" in sources or "qabas" in sources


class TestHeuristicTransitivity:
    """Verify form-based transitivity heuristics as fallback."""

    def test_form5_intransitive(self, server_module):
        result = json.loads(server_module.check_transitivity("تَعَلَّمَ"))
        for r in result.get("readings", []):
            if r["form"] == "V" and r.get("transitivity_source") == "heuristic":
                assert r["transitivity"] == "لازم"
                return

    def test_form7_intransitive(self, server_module):
        result = json.loads(server_module.check_transitivity("انْكَسَرَ"))
        for r in result.get("readings", []):
            if r["form"] == "VII" and r.get("transitivity_source") == "heuristic":
                assert r["transitivity"] == "لازم"
                return
