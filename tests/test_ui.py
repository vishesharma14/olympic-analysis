"""
Offline tests for the "Ask the data" page (chatbot/ui.py) and its place in app.py, with Streamlit's
AppTest. agent.answer is replaced by a fake and the key by a dummy value, so nothing calls Gemini.
"""

import json
import subprocess
import sys
import threading
import time
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import matplotlib
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import AppTestError

from chatbot import agent, db, llm, prompts, ui
from chatbot.agent import AgentResult, Source, SqlRun

matplotlib.use("Agg")  # app.py's pages draw with pyplot

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app.py"
PAGES = ("Medal Tally", "Overall Analysis", "Country-Wise Analysis", "Athlete Wise Analysis", "Ask the data")
PAGE_SCRIPT = "from chatbot import ui\nui.render()\n"
TIMEOUT_S = 30
APP_TIMEOUT_S = 180  # app.py loads the full CSV and draws large heatmaps
REAL_SLEEP = time.sleep  # captured before offline_gemini replaces it with a no-op

GOLD_SQL = ("SELECT country, COUNT(*) AS golds FROM country_medals WHERE medal = 'Gold' "
            "GROUP BY country ORDER BY golds DESC LIMIT 1")
GOLD_ROWS = pd.DataFrame({"country": ["USA"], "golds": [1035]})
GOLD_ANSWER = "The USA has won the most gold medals: 1,035."


def ok_result(text: str = GOLD_ANSWER, grounding: dict | None = None) -> AgentResult:
    return AgentResult(
        text=text, status="ok",
        sql_runs=[SqlRun(sql=GOLD_SQL, columns=list(GOLD_ROWS.columns), rows=GOLD_ROWS, row_count=1, truncated=False),
                  SqlRun(sql="SELECT nope FROM country_medals", columns=[], rows=pd.DataFrame(), row_count=0,
                         truncated=False, error="no such column: nope")],
        sources=[Source("counting_rules#team-medals-count-once", "Team medals count once")],
        retrieval_method="keywords", model="fake-gemini", llm_calls=3, elapsed_s=2.0,
        grounding=grounding or {"verified": True, "unverified_numbers": []})


@pytest.fixture(autouse=True)
def page_settings(offline_gemini, monkeypatch):
    """A dummy key, no wait between questions, a fake database build and a fresh daily counter."""
    monkeypatch.setattr(time, "sleep", REAL_SLEEP)  # AppTest polls with time.sleep; nothing here calls Gemini
    monkeypatch.setenv("GEMINI_API_KEY", "offline-test-key")
    monkeypatch.setenv("CHAT_MIN_INTERVAL_S", "0")
    builds = []
    monkeypatch.setattr(db, "ensure_database", lambda: builds.append(1) or ROOT / "unused.db")
    ui.daily_counter.clear()
    ui._database.clear()
    yield builds
    ui.daily_counter.clear()
    ui._database.clear()


@pytest.fixture
def fake_answer(monkeypatch):
    """Replaces agent.answer; set .result to change the reply; .calls records (question, history)."""
    fake = SimpleNamespace(result=ok_result(), calls=[])

    def answer(question, history=None):
        fake.calls.append((question, list(history or [])))
        return fake.result

    monkeypatch.setattr(agent, "answer", answer)
    return fake


def open_page() -> AppTest:
    return AppTest.from_string(PAGE_SCRIPT, default_timeout=TIMEOUT_S).run()


def ask(page: AppTest, question: str) -> AppTest:
    return page.chat_input(key="chat_question").set_value(question).run()


def example_buttons(page: AppTest) -> list:
    return [button for button in page.button if (button.key or "").startswith("chat_example_")]


def has_button(page: AppTest, key: str) -> bool:
    return any(button.key == key for button in page.button)


def captions(page: AppTest) -> list[str]:
    return [caption.value for caption in page.caption]


# The page


def test_empty_chat_shows_the_examples_and_the_chat_input(page_settings, fake_answer):
    page = open_page()
    assert not page.exception
    assert page.title[0].value == "Ask the data"
    assert page.markdown[0].value == ui.INTRO
    assert [button.label for button in example_buttons(page)] == list(ui.EXAMPLES)
    chat_input = page.chat_input(key="chat_question")
    assert chat_input.placeholder == ui.PLACEHOLDER
    assert chat_input.proto.max_chars == 300
    assert not chat_input.disabled
    assert not page.chat_message
    assert not has_button(page, "chat_clear")
    assert captions(page)[-1] == ui.FOOTER
    assert page_settings == [1]  # the database was prepared
    assert fake_answer.calls == []


def test_clicking_an_example_asks_it_and_shows_how_it_was_answered(page_settings, fake_answer):
    page = open_page()
    page.button(key="chat_example_0").click().run()

    assert not page.exception
    assert fake_answer.calls == [(ui.EXAMPLES[0], [])]
    assert [message.name for message in page.chat_message] == ["user", "assistant"]
    assistant = page.chat_message[1]
    assert assistant.markdown[0].value == GOLD_ANSWER
    assert assistant.caption[0].value == ui.VERIFIED_LINE

    expander = page.expander[0]
    assert expander.label == "How this was answered"
    assert [(code.value, code.language) for code in expander.code] == [
        (GOLD_SQL, "sql"), ("SELECT nope FROM country_medals", "sql")]
    details = [markdown.value for markdown in expander.markdown]
    assert details[0] == "**Query 1** · 1 row"
    assert details[1].startswith("**Query 2** · error") and "no such column" in details[1]
    assert details[2] == "**Sources:** Team medals count once"
    assert len(expander.dataframe) == 1  # the failed query has no table
    pd.testing.assert_frame_equal(expander.dataframe[0].value, GOLD_ROWS)
    assert expander.caption[0].value == ("Retrieval: keywords · Model: fake-gemini · "
                                         "Gemini calls: 3 · 2.0 s")

    assert example_buttons(page) == []  # the examples go once the chat has started
    assert has_button(page, "chat_clear")
    assert page_settings == [1]  # cached: the reruns did not prepare the database again


def test_unverified_numbers_are_listed(fake_answer):
    fake_answer.result = ok_result(grounding={"verified": False, "unverified_numbers": ["1,036", "48.6%"]})
    page = ask(open_page(), "Which country has won the most gold medals?")
    assert page.chat_message[1].caption[0].value == "⚠ Couldn't verify: 1,036, 48.6%"


def test_typed_questions_are_answered_with_the_last_two_turns(fake_answer):
    page = open_page()
    for question in ("first?", "second?", "third?"):
        page = ask(page, question)
    assert not page.exception
    assert [message.name for message in page.chat_message] == ["user", "assistant"] * 3
    assert page.chat_message[4].markdown[0].value == "third?"
    assert fake_answer.calls[-1] == ("third?", [("first?", GOLD_ANSWER), ("second?", GOLD_ANSWER)])


def test_a_typed_question_is_shown_as_written(fake_answer):
    page = ask(open_page(), "What about *USA* [link](http://x)?")
    assert page.chat_message[0].markdown[0].value == r"What about \*USA\* \[link\]\(http\://x\)?"


@pytest.mark.parametrize("status, message, element", [
    ("quota", prompts.QUOTA_MESSAGE, "warning"),
    ("error", prompts.ERROR_MESSAGE, "error"),
])
def test_quota_and_error_replies_are_a_warning_and_an_error(fake_answer, status, message, element):
    fake_answer.result = AgentResult(text=message, status=status)
    page = ask(open_page(), "Which country has won the most gold medals?")
    assistant = page.chat_message[1]
    assert [box.value for box in getattr(assistant, element)] == [message]
    assert not assistant.markdown and not assistant.caption  # no answer text, no grounding line
    assert not page.expander  # nothing was retrieved or queried


def test_clear_chat_empties_the_history(fake_answer):
    page = ask(open_page(), "first?")
    page.button(key="chat_clear").click().run()
    assert not page.exception
    assert not page.chat_message
    assert len(example_buttons(page)) == len(ui.EXAMPLES)
    assert page.session_state[ui.TURNS] == []
    assert page.session_state[ui.ASKED] == 1  # clearing does not reset the session limit


def test_missing_key_shows_an_info_box_and_no_chat_input(page_settings, fake_answer, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    page = open_page()
    assert not page.exception
    assert [box.value for box in page.info] == [ui.NOT_CONFIGURED_MESSAGE]
    assert not page.chat_input
    assert not page.button
    assert captions(page) == [ui.FOOTER]
    assert page_settings == []  # no database build for a page that cannot answer


def test_a_failed_database_build_shows_an_error(fake_answer, monkeypatch):
    def broken():
        raise OSError("disk full")

    monkeypatch.setattr(db, "ensure_database", broken)
    page = open_page()
    assert not page.exception
    assert [box.value for box in page.error] == [ui.DATABASE_ERROR_MESSAGE]
    assert not page.chat_input


# Usage limits


def test_session_limit_disables_the_chat(fake_answer, monkeypatch):
    monkeypatch.setenv("CHAT_SESSION_LIMIT", "2")
    page = ask(ask(open_page(), "first?"), "second?")
    message = ui.SESSION_LIMIT_MESSAGE.format(limit=2)
    assert [box.value for box in page.info] == [message]
    assert page.chat_input(key="chat_question").disabled
    with pytest.raises(AppTestError):
        ask(page, "third?")

    page.button(key="chat_clear").click().run()
    assert all(button.disabled for button in example_buttons(page))
    assert [box.value for box in page.info] == [message]
    assert len(fake_answer.calls) == 2


def test_daily_limit_is_shared_by_every_session(fake_answer, monkeypatch):
    monkeypatch.setenv("CHAT_DAILY_LIMIT", "2")
    first, second = open_page(), open_page()  # both open while questions are left
    first = ask(first, "one?")
    second = ask(second, "two?")  # the last question of the day
    first = ask(first, "three?")  # its input was still enabled: the server-side check blocks it
    assert [box.value for box in first.info] == [ui.DAILY_LIMIT_MESSAGE]
    assert [call[0] for call in fake_answer.calls] == ["one?", "two?"]

    third = open_page()
    assert [box.value for box in third.info] == [ui.DAILY_LIMIT_MESSAGE]
    assert third.chat_input(key="chat_question").disabled
    assert all(button.disabled for button in example_buttons(third))


def test_questions_less_than_the_interval_apart_are_refused(fake_answer, monkeypatch):
    monkeypatch.delenv("CHAT_MIN_INTERVAL_S")  # the default, 3 seconds
    page = ask(ask(open_page(), "first?"), "second?")
    assert [box.value for box in page.info] == [ui.RATE_LIMIT_MESSAGE]
    assert [call[0] for call in fake_answer.calls] == ["first?"]
    assert len(page.chat_message) == 2


def test_limits_come_from_settings(monkeypatch, tmp_path):
    secrets = tmp_path / "secrets.toml"
    secrets.write_text('CHAT_SESSION_LIMIT = 4\nCHAT_DAILY_LIMIT = "50"\n', encoding="utf-8")
    monkeypatch.setattr(llm, "SECRETS_PATH", secrets)
    monkeypatch.delenv("CHAT_MIN_INTERVAL_S")
    assert ui.limits() == ui.Limits(session=4, daily=50, min_interval_s=3.0)

    monkeypatch.setenv("CHAT_SESSION_LIMIT", "lots")
    monkeypatch.setenv("CHAT_DAILY_LIMIT", "-1")
    monkeypatch.setenv("CHAT_MIN_INTERVAL_S", "0.5")
    assert ui.limits() == ui.Limits(session=15, daily=200, min_interval_s=0.5)


def test_daily_counter_starts_again_each_utc_day():
    day = date(2026, 10, 14)
    counter = ui.DailyCounter(today=lambda: day)
    assert [counter.try_add(2) for _ in range(3)] == [True, True, False]
    assert counter.reached(2)
    day = date(2026, 10, 15)
    assert not counter.reached(2)
    assert counter.try_add(2)


def test_daily_counter_is_thread_safe():
    counter = ui.DailyCounter()
    counted = []

    def add_many():
        counted.extend(counter.try_add(500) for _ in range(200))

    threads = [threading.Thread(target=add_many) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert counted.count(True) == 500


# app.py

DASHBOARD_CHECK = """
import json, sys
import matplotlib
matplotlib.use("Agg")
from streamlit.testing.v1 import AppTest

app = AppTest.from_file(sys.argv[1], default_timeout=float(sys.argv[2])).run()
radio = app.sidebar.radio[0]
report = {"options": list(radio.options), "sidebar_captions": [c.value for c in app.sidebar.caption],
          "exceptions": {}}
for page in json.loads(sys.argv[3]):
    app.sidebar.radio[0].set_value(page).run()
    report["exceptions"][page] = [e.value for e in app.exception]
report["loaded"] = [name for name in ("chatbot", "chatbot.agent", "chatbot.ui", "chatbot.db", "google.genai")
                    if name in sys.modules]
print(json.dumps(report))
"""


def test_dashboard_pages_render_without_loading_the_chatbot():
    """In a fresh interpreter: the four dashboard pages render and never import the chatbot or google-genai."""
    pages = list(PAGES[:4])
    completed = subprocess.run(
        [sys.executable, "-c", DASHBOARD_CHECK, str(APP), str(APP_TIMEOUT_S), json.dumps(pages)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=600)
    assert completed.returncode == 0, completed.stderr[-2000:]
    report = json.loads(completed.stdout.strip().splitlines()[-1])
    assert report["options"] == list(PAGES)
    assert "New: ask questions in plain English" in report["sidebar_captions"]
    assert report["exceptions"] == {page: [] for page in pages}
    assert report["loaded"] == []


def test_ask_the_data_page_renders_in_the_app(fake_answer, monkeypatch):
    monkeypatch.chdir(ROOT)  # app.py reads the CSVs from the working directory
    app = AppTest.from_file(str(APP), default_timeout=APP_TIMEOUT_S).run()
    app.sidebar.radio[0].set_value("Ask the data").run()
    assert not app.exception
    assert app.title[0].value == "Ask the data"
    assert len(app.chat_input) == 1
    app = ask(app, "Which country has won the most gold medals?")
    assert not app.exception
    assert app.chat_message[1].markdown[0].value == GOLD_ANSWER
