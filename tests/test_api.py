"""Integration tests for the REST API endpoints."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Create a test client for the FastAPI app."""
    import api
    return TestClient(api.app)


# --- Health ---


class TestHealth:
    def test_returns_ok(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "data" in data

    def test_has_stem_count(self, client):
        data = client.get("/health").json()
        assert data["data"]["stems"] > 40000


# --- Serve index ---


class TestIndex:
    def test_serves_html(self, client):
        res = client.get("/")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        assert "<!DOCTYPE html>" in res.text


# --- Input validation ---


class TestValidation:
    def test_empty_word(self, client):
        res = client.get("/analyze/word", params={"word": ""})
        assert "error" in res.json()

    def test_english_word(self, client):
        res = client.get("/analyze/word", params={"word": "hello"})
        assert "error" in res.json()
        assert "Arabic" in res.json()["error"]

    def test_empty_sentence(self, client):
        res = client.get("/analyze/sentence", params={"text": "  "})
        assert "error" in res.json()

    def test_empty_verb_transitivity(self, client):
        res = client.get("/check/transitivity", params={"verb": "abc"})
        assert "error" in res.json()

    def test_empty_verb_tasrif(self, client):
        res = client.get("/tasrif", params={"verb": ""})
        assert "error" in res.json()

    def test_irab_empty(self, client):
        res = client.post("/irab", json={"text": ""})
        assert "error" in res.json()

    def test_irab_english(self, client):
        res = client.post("/irab", json={"text": "hello world"})
        assert "error" in res.json()


# --- Analyze word ---


class TestAnalyzeWord:
    def test_known_word(self, client):
        res = client.get("/analyze/word", params={"word": "كتب"})
        assert res.status_code == 200
        data = res.json()
        assert data["word"] == "كتب"
        assert data["total_analyses"] > 0
        assert len(data["analyses"]) > 0

    def test_analysis_structure(self, client):
        data = client.get("/analyze/word", params={"word": "كتب"}).json()
        a = data["analyses"][0]
        assert "vocalized" in a
        assert "type" in a
        assert "lemma" in a
        assert "root" in a
        assert a["type"] == "فعل"

    def test_unknown_word(self, client):
        res = client.get("/analyze/word", params={"word": "ططططط"})
        data = res.json()
        assert data["analyses"] == [] or "error" in data

    def test_noun_has_new_fields(self, client):
        data = client.get("/analyze/word", params={"word": "مكتوب"}).json()
        a = data["analyses"][0]
        assert a["root"] is not None
        assert a["pattern"] is not None
        assert a["noun_class"] is not None


# --- Analyze sentence ---


class TestAnalyzeSentence:
    def test_basic_sentence(self, client):
        res = client.get("/analyze/sentence", params={"text": "كتب الطالب الرسالة"})
        assert res.status_code == 200
        data = res.json()
        assert len(data["words"]) == 3

    def test_word_structure(self, client):
        data = client.get("/analyze/sentence", params={"text": "ذهب"}).json()
        w = data["words"][0]
        assert "word" in w
        assert "total_readings" in w
        assert "top_analyses" in w
        assert len(w["top_analyses"]) > 0


# --- Transitivity ---


class TestTransitivity:
    def test_transitive_verb(self, client):
        data = client.get("/check/transitivity", params={"verb": "كتب"}).json()
        assert "readings" in data
        assert len(data["readings"]) > 0
        r = data["readings"][0]
        assert "form" in r
        assert "transitivity" in r
        assert "vocalized" in r

    def test_intransitive_verb(self, client):
        data = client.get("/check/transitivity", params={"verb": "ذهب"}).json()
        readings = data["readings"]
        assert any("لازم" in r["transitivity"] for r in readings)

    def test_unknown_verb(self, client):
        data = client.get("/check/transitivity", params={"verb": "ططططط"}).json()
        assert "error" in data or data.get("readings") == []


# --- Tasrif (conjugation) ---


class TestTasrif:
    def test_basic_conjugation(self, client):
        data = client.get("/tasrif", params={"verb": "كتب"}).json()
        assert data["form"] == "I"
        assert data["lemma_id"] == "katab-u_1"

    def test_past_active(self, client):
        data = client.get("/tasrif", params={"verb": "كتب"}).json()
        pa = data["past"]["active"]
        assert len(pa) == 13
        assert pa[0]["person"] == "3MS"
        assert pa[0]["arabic"] == "كَتَبَ"

    def test_imperfect_active(self, client):
        data = client.get("/tasrif", params={"verb": "كتب"}).json()
        ia = data["imperfect"]["active"]
        assert len(ia) == 13
        assert ia[0]["arabic"] == "يَكْتُبُ"

    def test_subjunctive(self, client):
        data = client.get("/tasrif", params={"verb": "كتب"}).json()
        subj = data["subjunctive"]["active"]
        assert len(subj) == 13
        assert subj[0]["arabic"] == "يَكْتُبَ"

    def test_jussive(self, client):
        data = client.get("/tasrif", params={"verb": "كتب"}).json()
        juss = data["jussive"]["active"]
        assert len(juss) == 13
        assert juss[0]["arabic"] == "يَكْتُب"

    def test_imperative(self, client):
        data = client.get("/tasrif", params={"verb": "كتب"}).json()
        imp = data["imperative"]
        assert len(imp) == 5
        assert imp[0]["person"] == "2MS"

    def test_passive_forms(self, client):
        data = client.get("/tasrif", params={"verb": "كتب"}).json()
        pp = data["past"]["passive"]
        assert len(pp) == 13
        assert pp[0]["arabic"] == "كُتِبَ"

    def test_participles(self, client):
        data = client.get("/tasrif", params={"verb": "كتب"}).json()
        assert data["active_participle"] == "كاتِب"
        assert data["passive_participle"] == "مَكْتُوب"

    def test_masdar_form_i_is_none(self, client):
        data = client.get("/tasrif", params={"verb": "كتب"}).json()
        assert data["masdar"] is None  # Form I masdars are irregular

    def test_masdar_form_v(self, client):
        data = client.get("/tasrif", params={"verb": "تعلّم"}).json()
        assert data["masdar"] is not None

    def test_unknown_verb(self, client):
        data = client.get("/tasrif", params={"verb": "ططططط"}).json()
        assert "error" in data


# --- I'rab ---


class TestIrab:
    def test_no_credentials_no_cli(self, client, monkeypatch):
        """Without API key or claude CLI, should return error."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setattr("shutil.which", lambda x: None)
        res = client.post("/irab", json={"text": "كتب الطالب"})
        data = res.json()
        assert "error" in data

    def test_invalid_json(self, client):
        res = client.post("/irab", content="not json", headers={"content-type": "application/json"})
        assert res.status_code == 422
