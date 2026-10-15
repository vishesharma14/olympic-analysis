"""
ui.py
-----
The Streamlit "Ask the data" page. app.py imports this module only when the page is selected, so
the dashboard's other pages never load google-genai or build the chatbot database.

    render()   the page: example questions, the chat, and how each answer was found

Usage limits protect the free Gemini quota. Each one can be overridden with an environment variable
or a Streamlit secret of the same name (read through llm.get_setting):

    CHAT_SESSION_LIMIT    questions per browser session (default 15)
    CHAT_DAILY_LIMIT      questions per UTC day for the whole app (default 200)
    CHAT_MIN_INTERVAL_S   seconds between two questions of one session (default 3)

Questions live only in st.session_state; they are never logged or stored anywhere else.
"""

import logging
import math
import re
import threading
import time
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import NamedTuple

import streamlit as st

from chatbot import agent, db, llm, prompts
from chatbot.agent import AgentResult, SqlRun

INTRO = ("Ask about the Summer Olympics 1896–2016. Every number comes from a SQL query on the same "
         "data as this dashboard, and you can see the query.")
NOT_CONFIGURED_MESSAGE = "The assistant isn't configured on this deployment."
DATABASE_ERROR_MESSAGE = "The assistant's database couldn't be prepared. Please reload the page in a minute."
FOOTER = ("Powered by Google Gemini (free tier). Questions are sent to Google Gemini — don't enter "
          "personal information. Answers can be wrong — check the SQL. Covers the Summer Games 1896–2016 only.")
PLACEHOLDER = "Ask a question about the Summer Olympics…"
SPINNER = "Looking it up in the data…"
DATABASE_SPINNER = "Preparing the database (first visit only, about 20 seconds)"
# Short enough to fit a button on one line: 2 columns of about 440 px on a 1366 px laptop with the
# sidebar open, one full-width column on a phone.
EXAMPLES = (
    "Which country has the most gold medals?",
    "How did India do at London 2012?",
    "Who is the most decorated Olympian?",
    "How are relay medals counted?",
    "Which sport has the tallest medallists?",
    "India ne hockey mein kitne gold jeete?",
)
EXAMPLE_COLUMNS = 2  # Streamlit stacks the columns on narrow screens
HISTORY_PAIRS = 2  # earlier (question, answer) pairs sent with each question

VERIFIED_LINE = "✓ Numbers checked against the query results"
UNVERIFIED_LINE = "⚠ Couldn't verify: {numbers}"
SESSION_LIMIT_MESSAGE = ("You've reached this demo's limit of {limit} questions per session. "
                         "Thanks for trying it!")
DAILY_LIMIT_MESSAGE = ("The assistant has used today's share of its free quota. "
                       "Please come back tomorrow.")
RATE_LIMIT_MESSAGE = "Please wait a few seconds between questions, then ask again."

DEFAULT_SESSION_LIMIT = 15
DEFAULT_DAILY_LIMIT = 200
DEFAULT_MIN_INTERVAL_S = 3.0

# st.session_state keys
TURNS = "chat_turns"  # list[Turn], oldest first
ASKED = "chat_questions_asked"  # questions sent to the agent this session; Clear chat keeps it
LAST_ASKED_AT = "chat_last_asked_at"  # time.monotonic() of the last question sent

log = logging.getLogger(__name__)


class Turn(NamedTuple):
    question: str
    result: AgentResult


class Limits(NamedTuple):
    session: int
    daily: int
    min_interval_s: float


def limits() -> Limits:
    return Limits(session=_number_setting("CHAT_SESSION_LIMIT", DEFAULT_SESSION_LIMIT, int),
                  daily=_number_setting("CHAT_DAILY_LIMIT", DEFAULT_DAILY_LIMIT, int),
                  min_interval_s=_number_setting("CHAT_MIN_INTERVAL_S", DEFAULT_MIN_INTERVAL_S, float))


def _number_setting(name: str, default, kind: Callable):
    value = llm.get_setting(name)
    try:
        number = kind(value) if value is not None else default
    except ValueError:
        log.warning("Ignoring %s: not a number", name)
        return default
    return number if number >= 0 else default


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


class DailyCounter:
    """Questions asked today (UTC) by every session of this app process; safe to share between threads."""

    def __init__(self, today: Callable[[], date] = _utc_today):
        self._today = today
        self._lock = threading.Lock()
        self._day: date | None = None
        self._count = 0

    def reached(self, limit: int) -> bool:
        with self._lock:
            self._roll_over()
            return self._count >= limit

    def try_add(self, limit: int) -> bool:
        """Counts one question unless today's limit is reached; returns whether it was counted."""
        with self._lock:
            self._roll_over()
            if self._count >= limit:
                return False
            self._count += 1
            return True

    def _roll_over(self) -> None:
        today = self._today()
        if today != self._day:
            self._day, self._count = today, 0


@st.cache_resource(show_spinner=False)
def daily_counter() -> DailyCounter:
    """One counter for the whole app: st.cache_resource shares it across sessions."""
    return DailyCounter()


@st.cache_resource(show_spinner=DATABASE_SPINNER)
def _database():
    return db.ensure_database()


def render() -> None:
    st.title("Ask the data")
    st.markdown(INTRO)
    if llm.get_setting("GEMINI_API_KEY") is None:
        st.info(NOT_CONFIGURED_MESSAGE)
        st.caption(FOOTER)
        return
    try:
        _database()
    except Exception as error:
        log.error("The chatbot database could not be built: %s", type(error).__name__)
        st.error(DATABASE_ERROR_MESSAGE)
        st.caption(FOOTER)
        return

    state = st.session_state
    for key, initial in ((TURNS, []), (ASKED, 0), (LAST_ASKED_AT, -math.inf)):
        if key not in state:
            state[key] = initial
    turns = state[TURNS]
    current = limits()

    for turn in turns:
        _show_turn(turn)

    blocked = _blocked_message(current)
    example = None if turns else _example_buttons(disabled=blocked is not None)
    typed = st.chat_input(PLACEHOLDER, key="chat_question", max_chars=prompts.MAX_QUESTION_CHARS,
                          disabled=blocked is not None, submit_mode="disable")
    question = example or typed
    if blocked:
        st.info(blocked)
    elif question:
        _ask(question, current)
    if turns:
        st.button("Clear chat", key="chat_clear", on_click=_clear_chat)
    st.caption(FOOTER)


def _blocked_message(current: Limits) -> str | None:
    if st.session_state[ASKED] >= current.session:
        return SESSION_LIMIT_MESSAGE.format(limit=current.session)
    if daily_counter().reached(current.daily):
        return DAILY_LIMIT_MESSAGE
    return None


def _ask(question: str, current: Limits) -> None:
    state = st.session_state
    now = time.monotonic()
    if now - state[LAST_ASKED_AT] < current.min_interval_s:
        st.info(RATE_LIMIT_MESSAGE)
        return
    if not daily_counter().try_add(current.daily):  # another session may have used the last one
        st.info(DAILY_LIMIT_MESSAGE)
        return
    state[ASKED] += 1
    state[LAST_ASKED_AT] = now
    history = [(turn.question, turn.result.text) for turn in state[TURNS][-HISTORY_PAIRS:]]

    with st.chat_message("user"):
        st.markdown(_plain(question))
    with st.chat_message("assistant"), st.spinner(SPINNER):
        # Stored before the spinner closes: a rerun requested meanwhile must not lose the answer.
        state[TURNS].append(Turn(question, agent.answer(question, history)))
    st.rerun()  # redraw from the history: the examples go, Clear chat appears


def _example_buttons(disabled: bool) -> str | None:
    st.caption("Try one of these:")
    clicked = None
    for start in range(0, len(EXAMPLES), EXAMPLE_COLUMNS):
        row = EXAMPLES[start:start + EXAMPLE_COLUMNS]
        for number, (column, example) in enumerate(zip(st.columns(EXAMPLE_COLUMNS), row), start):
            if column.button(example, key=f"chat_example_{number}", width="stretch", disabled=disabled):
                clicked = example
    return clicked


def _clear_chat() -> None:
    st.session_state[TURNS] = []


def _show_turn(turn: Turn) -> None:
    result = turn.result
    with st.chat_message("user"):
        st.markdown(_plain(turn.question))
    with st.chat_message("assistant"):
        if result.status == "quota":
            st.warning(result.text)
        elif result.status == "error":
            st.error(result.text)
        else:
            st.markdown(result.text)
            st.caption(_grounding_line(result.grounding))
        if result.sql_runs or result.sources:
            with st.expander("How this was answered"):
                _show_details(result)


def _grounding_line(grounding: dict) -> str:
    if grounding.get("verified", True):
        return VERIFIED_LINE
    return UNVERIFIED_LINE.format(numbers=", ".join(grounding.get("unverified_numbers", [])))


def _show_details(result: AgentResult) -> None:
    for number, run in enumerate(result.sql_runs, 1):
        st.markdown(f"**Query {number}** · {_plain(_outcome(run))}")
        st.code(run.sql.strip(), language="sql")
        if not run.error:
            st.dataframe(run.rows, hide_index=True)
    if not result.sql_runs:
        st.caption("No SQL query was run for this answer.")
    sources = ", ".join(source.heading for source in result.sources) or "none"
    st.markdown(f"**Sources:** {sources}")
    st.caption(f"Retrieval: {result.retrieval_method or 'none'} · Model: {result.model or 'none'} · "
               f"Gemini calls: {result.llm_calls} · {result.elapsed_s:.1f} s")


def _outcome(run: SqlRun) -> str:
    if run.error:
        return f"error: {run.error}"
    rows = f"{run.row_count} row{'' if run.row_count == 1 else 's'}"
    return f"more than {rows}, the first {run.row_count} shown" if run.truncated else rows


_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~$:])")


def _plain(text: str) -> str:
    """Escapes Markdown, so a typed question or a SQLite error shows exactly as written."""
    return _MARKDOWN_SPECIAL.sub(r"\\\1", text)
