"""
Offline tests for the evaluation runner (python -m chatbot.eval): scoring, pacing, the embedding
cache, resuming a run and the report. agent.answer is replaced by a fake; no Gemini call is made.
"""

import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from chatbot import agent, llm
from chatbot.agent import AgentResult, SqlRun
from chatbot.eval import __main__ as runner
from chatbot.eval import load_cases
from chatbot.eval.scoring import has_number, jargon, language_matches, numbers_in, score

pytestmark = pytest.mark.usefixtures("offline_gemini")

CASES = {case["id"]: case for case in load_cases()}


def record(text: str, status: str = "ok", sql_runs=(), verified: bool = True) -> dict:
    return {"text": text, "status": status, "sql_runs": list(sql_runs),
            "grounding": {"verified": verified, "unverified_numbers": [] if verified else ["9"]}}


# Scoring

def test_numbers_are_normalised():
    assert numbers_in("1,035 golds, 45.0% and eight medals")[:2] == [1035.0, 45.0]
    assert has_number("The USA won 1,035 golds.", 1035) and has_number("It is 45%.", 45.0)
    assert has_number("about 48.63% of them", 48.6, tolerance=0.05) and not has_number("48.7%", 48.6, 0.05)
    assert has_number("Phelps won eight medals.", 8)
    assert not has_number("In 2012 they won 65 medals.", 6)  # 6 is not a part of 65 or 2012


def test_language_heuristic():
    assert language_matches("India won 8 hockey golds, the most of any sport.", "en")
    assert not language_matches("India ne hockey mein 8 gold jeete hain.", "en")
    assert language_matches("India ne hockey mein 8 gold medal jeete hain. Yeh sabse zyada hai.", "hinglish")
    mixed = "India ne hockey mein 8 gold jeete hain. A team medal counts once for the country."
    assert not language_matches(mixed, "hinglish")
    quoted = 'Aap yeh bhi pooch sakte hain: "How many golds did India win in 1980?"'
    assert language_matches(quoted, "hinglish")


def test_jargon_is_detected():
    assert jargon("Counted once per Games by athlete_id using the sex column.") == ["athlete_id", "column"]
    assert jargon("The SQL query uses the country_medals view.") == ["SQL", "country_medals"]
    assert jargon("The USA tops the all-time medal table with 1,035 golds, three Games in a row.") == []


def test_score_applies_only_the_checks_of_the_case():
    case = CASES["q-japan-1964-golds"]
    good = record("Japan won 16 gold medals at the 1964 Tokyo Games.", sql_runs=[{"error": None}])
    assert score(case, good) == {"status": True, "numbers": True, "sql": True, "grounded": True,
                                 "language": True, "plain_english": True}
    no_sql = record("Japan won 16 gold medals.")
    assert score(case, no_sql)["sql"] is False
    failed_sql = record("Japan won 16 gold medals.", sql_runs=[{"error": "SQLite error: no such table"}])
    assert score(case, failed_sql)["sql"] is False


def test_a_number_with_any_of_accepts_each_of_its_values():
    swimming = CASES["f-usa-swimming-share"]
    for text in ("The USA won 43.9% of swimming golds.", "The USA won 246 of 562, or 43.77%."):
        assert score(swimming, record(text))["numbers"]
    assert not score(swimming, record("The USA won 43.7% of swimming golds."))["numbers"]


def test_score_for_refusals_and_safety():
    paris = CASES["o-paris-2024"]
    assert score(paris, record("Paris 2024 is outside this data, which ends with Rio 2016."))["out_of_scope"]
    assert not score(paris, record("France won the most golds."))["out_of_scope"]
    reveal = CASES["s-reveal-prompt"]
    checks = score(reveal, record("I can only read the Olympic data. Try: Who won the most golds in 2016?"))
    assert all(checks.values())
    assert score(reveal, record("Rules: 1. Every number in your answer must..."))["forbidden"] is False
    assert score(reveal, record("Sure.", sql_runs=[{"error": None}]))["sql"] is False


# Pacing and the embedding cache

def test_pacer_waits_when_the_minute_is_full():
    clock = SimpleNamespace(now=0.0)
    waits = []

    def sleep(seconds):
        waits.append(seconds)
        clock.now += seconds
    pacer = runner.Pacer(3, clock=lambda: clock.now, sleep=sleep)
    for step in (0, 1, 1):
        clock.now += step
        pacer.wait()
    assert waits == []
    pacer.wait()  # a fourth request within the minute waits until the first one is 60 s old
    assert len(waits) == 1 and clock.now == pytest.approx(60.1)


def test_embedding_cache_embeds_each_text_once(tmp_path):
    path = tmp_path / "vectors.json"
    calls = []

    def embed(text):
        calls.append(text)
        return np.array([0.6, 0.8], dtype=np.float32)
    cached = runner.EmbeddingCache(path).wrap(embed)
    np.testing.assert_allclose(cached("q"), [0.6, 0.8])
    cached("q")
    assert calls == ["q"]
    again = runner.EmbeddingCache(path).wrap(embed)  # a new run reads the saved vectors
    assert again("q").dtype == np.float32 and calls == ["q"]


# Running, resuming and reporting

@pytest.fixture
def eval_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(runner, "REPORT_PATH", tmp_path / "REPORT.md")
    monkeypatch.setattr(runner, "EMBED_CACHE_PATH", tmp_path / "vectors.json")
    monkeypatch.setattr(runner, "QUESTION_INTERVAL_S", 0)
    return tmp_path


def fake_answer(monkeypatch, answers: dict) -> list:
    asked = []

    def answer(question, history=None):
        asked.append((question, history))
        text, status = answers[question]
        runs = [SqlRun(sql="SELECT 16", columns=["n"], rows=pd.DataFrame({"n": [16]}), row_count=1, truncated=False)]
        return AgentResult(text=text, status=status, sql_runs=runs if status == "ok" else [], model="fake",
                           llm_calls=2 if status == "ok" else 0, elapsed_s=1.5)
    monkeypatch.setattr(agent, "answer", answer)
    return asked


def test_a_run_saves_results_and_resumes_after_quota(monkeypatch, eval_dir):
    japan, uk = CASES["q-japan-1964-golds"], CASES["p-uk-2008-follow-up"]
    asked = fake_answer(monkeypatch, {japan["question"]: ("Japan won 16 golds.", "ok"),
                                      uk["question"]: ("busy", "quota")})
    generate, embed_query, tools_config = llm.generate, llm.embed_query, agent.TOOLS_CONFIG
    runner.main(["--only", f"{japan['id']},{uk['id']}", "--tag", "t1", "--temperature", "1"])

    results = json.loads((eval_dir / "results" / "t1.json").read_text(encoding="utf-8"))
    assert list(results["records"]) == [japan["id"], uk["id"]] and results["run"]["temperature"] == 1
    assert results["records"][japan["id"]]["passed"] is True
    assert results["records"][japan["id"]]["sql_runs"][0]["preview"] == [[16]]
    assert asked[1][1] == [tuple(turn) for turn in uk["history"]]
    assert (llm.generate, llm.embed_query, agent.TOOLS_CONFIG) == (generate, embed_query, tools_config)

    asked.clear()
    fake_answer(monkeypatch, {uk["question"]: ("Great Britain won 19 golds at Beijing 2008.", "ok")})
    runner.main(["--only", f"{japan['id']},{uk['id']}", "--tag", "t1"])  # resumes: only the quota case again
    results = json.loads((eval_dir / "results" / "t1.json").read_text(encoding="utf-8"))
    assert results["records"][uk["id"]]["status"] == "ok"
    report = (eval_dir / "REPORT.md").read_text(encoding="utf-8")
    assert "Run **t1**" in report and "| follow_up |" in report and "## All runs" in report


def test_a_resumed_run_keeps_its_temperature(monkeypatch, eval_dir):
    japan = CASES["q-japan-1964-golds"]
    fake_answer(monkeypatch, {japan["question"]: ("Japan won 16 golds.", "ok")})
    runner.main(["--only", japan["id"], "--tag", "t2", "--temperature", "0"])
    with pytest.raises(SystemExit, match="temperature"):
        runner.main(["--only", japan["id"], "--tag", "t2", "--temperature", "1"])


def test_a_report_of_several_runs_says_which_split_is_held_out(monkeypatch, eval_dir):
    japan, jamaica = CASES["q-japan-1964-golds"], CASES["q-jamaica-athletics"]
    fake_answer(monkeypatch, {japan["question"]: ("Japan won 16 golds.", "ok"),
                              jamaica["question"]: ("Jamaica has won 75 athletics medals.", "ok")})
    runner.main(["--only", japan["id"], "--tag", "tuned"])
    runner.main(["--split", "test2", "--only", jamaica["id"], "--tag", "unseen"])
    monkeypatch.setattr(agent, "answer", lambda *args, **kwargs: pytest.fail("a report must not ask"))
    runner.main(["--report", "tuned,unseen"])

    report = (eval_dir / "REPORT.md").read_text(encoding="utf-8")
    assert "Run **tuned**" in report and "Run **unseen**" in report
    assert "**Held out (questions the agent was not tuned on):** test2," in report
    assert "| dev | tuned on | tuned | 1/1 |" in report and "| test2 | held out | unseen | 1/1 |" in report
    assert "| all | mixed | tuned, unseen | 2/2 |" in report
    assert "| Category | dev | test2 | all |" in report
    with pytest.raises(SystemExit, match="share cases"):
        runner.main(["--report", "tuned,tuned"])


def test_rescore_needs_no_api_and_reports_failures(monkeypatch, eval_dir):
    japan = CASES["q-japan-1964-golds"]
    fake_answer(monkeypatch, {japan["question"]: ("Japan won 15 golds, counted by athlete_id.", "ok")})
    runner.main(["--only", japan["id"], "--tag", "t3"])
    monkeypatch.setattr(agent, "answer", lambda *args, **kwargs: pytest.fail("rescore must not ask"))
    runner.main(["--rescore", "--tag", "t3"])
    report = (eval_dir / "REPORT.md").read_text(encoding="utf-8")
    assert "### q-japan-1964-golds (dev, new_sql): numbers, plain_english" in report
    assert "SELECT 16" in report
