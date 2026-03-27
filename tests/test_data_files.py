"""Tests for data file integrity."""

import json
import os
import pytest

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


class TestVerbTransitivity:
    """Verify verb_transitivity.json integrity."""

    @pytest.fixture(scope="class")
    def verb_data(self):
        path = os.path.join(DATA_DIR, "verb_transitivity.json")
        assert os.path.exists(path), "verb_transitivity.json not found"
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_has_meta(self, verb_data):
        assert "_meta" in verb_data
        assert "source" in verb_data["_meta"]

    def test_has_verbs(self, verb_data):
        assert "verbs" in verb_data
        assert len(verb_data["verbs"]) > 7000

    def test_verb_entry_structure(self, verb_data):
        for key, val in list(verb_data["verbs"].items())[:10]:
            assert "transitivity" in val
            assert val["transitivity"] in ("متعد", "لازم", "لازم ومتعد")

    @pytest.mark.parametrize("verb,expected", [
        ("ذهب", "لازم"),
        ("كتب", "متعد"),
        ("جلس", "متعد"),
        ("مات", "لازم"),
        ("سمع", "متعد"),
    ])
    def test_key_verbs(self, verb_data, verb, expected):
        assert verb in verb_data["verbs"], f"{verb} missing from lookup"
        assert verb_data["verbs"][verb]["transitivity"] == expected


class TestFeminineNouns:
    """Verify feminine_nouns.json integrity."""

    @pytest.fixture(scope="class")
    def noun_data(self):
        path = os.path.join(DATA_DIR, "feminine_nouns.json")
        assert os.path.exists(path), "feminine_nouns.json not found"
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_has_meta(self, noun_data):
        assert "_meta" in noun_data

    def test_has_nouns(self, noun_data):
        assert "nouns" in noun_data
        assert len(noun_data["nouns"]) > 50

    @pytest.mark.parametrize("noun", [
        "شمس", "أرض", "نار", "حرب", "عين", "يد", "دار", "نفس", "ريح",
    ])
    def test_key_feminine_nouns(self, noun_data, noun):
        assert noun in noun_data["nouns"], f"{noun} missing from feminine nouns"
        assert noun_data["nouns"][noun] == "مؤنث"

    def test_no_masculine_in_file(self, noun_data):
        for key, val in noun_data["nouns"].items():
            assert val == "مؤنث", f"{key} has value {val}, expected مؤنث"
