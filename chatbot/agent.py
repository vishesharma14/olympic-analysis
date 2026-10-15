"""
agent.py
--------
The "Ask the data" agent: one question in, one answer computed from the data out.

    answer(question, history=None) -> AgentResult

For each question the agent checks the input, retrieves the most relevant knowledge notes, and
lets Gemini call the run_sql tool (db.run_select) until it can answer. The SDK's automatic function
calling is off, so every tool call is executed here and recorded in AgentResult.sql_runs. A question
gets at most MAX_SQL_RUNS queries and MAX_GENERATE_CALLS Gemini calls; the last call has tools
disabled so the model answers from what it already has.

The numbers in the final answer are then checked against this question's SQL results and notes
(AgentResult.grounding). The check only flags an answer; it never blocks one.

answer() never raises: quota problems return status "quota", other failures status "error", each
with a message that is safe to show.
"""

import csv
import io
import logging
import math
import numbers
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import NamedTuple

import pandas as pd
from google.genai import types

from chatbot import llm, prompts
from chatbot.db import SQLGuardError, run_select
from chatbot.retrieval import retrieve

RETRIEVAL_K = 4
MAX_SQL_RUNS = 3  # run_sql executions per question, failed queries included
MAX_GENERATE_CALLS = 5  # Gemini calls per question, the final tool-less call included
MAX_HISTORY_TURNS = 2
HISTORY_MAX_CHARS = 1_000  # per earlier question or answer
MAX_OUTPUT_TOKENS = 1_024
# Google's default for Gemini 3, which may loop or degrade below 1.0. Chosen in the Step 6 evaluation:
# on the dev split 1.0 passed 22/23 against 20/23 at 0, with similar latency, and at 0 one answer
# came back as the bare token "_not_in_database".
TEMPERATURE = 1.0

SQL_MAX_ROWS = 200  # rows kept per query for the result and the UI
TOOL_MAX_ROWS = 50  # rows sent back to the model
TOOL_MAX_CHARS = 4_000  # CSV characters sent back to the model
TOOL_MAX_CELL_CHARS = 200

log = logging.getLogger(__name__)


@dataclass
class SqlRun:
    sql: str
    columns: list[str]
    rows: pd.DataFrame  # at most SQL_MAX_ROWS rows
    row_count: int  # rows in `rows`
    truncated: bool  # the query had more than SQL_MAX_ROWS rows
    error: str | None = None  # why the query was rejected or failed (the SQLGuardError message)


class Source(NamedTuple):
    id: str  # knowledge chunk id, e.g. "counting_rules#team-medals-count-once"
    heading: str


@dataclass
class AgentResult:
    text: str
    status: str  # "ok", "quota" or "error"
    sql_runs: list[SqlRun] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    retrieval_method: str | None = None  # "embeddings" or "keywords"
    model: str | None = None  # the model that produced the final answer
    llm_calls: int = 0  # generate() calls for this question
    elapsed_s: float = 0.0
    grounding: dict = field(default_factory=lambda: {"verified": True, "unverified_numbers": []})


RUN_SQL = types.FunctionDeclaration(
    name="run_sql",
    description=prompts.RUN_SQL_DESCRIPTION,
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={"query": types.Schema(type=types.Type.STRING, description=prompts.RUN_SQL_QUERY_DESCRIPTION)},
        required=["query"],
    ),
)


def _config(mode: types.FunctionCallingConfigMode, temperature: float = TEMPERATURE) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=prompts.SYSTEM_INSTRUCTION,
        temperature=temperature,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        # The lowest thinking level; llm.generate raises it for a model that rejects it (llm.THINKING_LEVELS).
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
        tools=[types.Tool(function_declarations=[RUN_SQL])],
        tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode=mode)),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


TOOLS_CONFIG = _config(types.FunctionCallingConfigMode.AUTO)
FINAL_CONFIG = _config(types.FunctionCallingConfigMode.NONE)  # the last call: answer, no more tools


def answer(question: str, history: Sequence[tuple[str, str]] | None = None) -> AgentResult:
    """Answers one question; history holds earlier (question, answer text) pairs, oldest first."""
    start = time.perf_counter()
    result = AgentResult(text=prompts.ERROR_MESSAGE, status="error")
    try:
        _answer(question, history, result)
    except llm.QuotaExceeded:
        result.text, result.status = prompts.QUOTA_MESSAGE, "quota"
    except llm.GeminiError as error:  # its message is safe to log: no key, no request body
        log.warning("The agent's Gemini call failed: %s", error)
        result.text, result.status = prompts.ERROR_MESSAGE, "error"
    except Exception as error:
        log.error("The agent failed with %s", type(error).__name__)
        result.text, result.status = prompts.ERROR_MESSAGE, "error"
    result.elapsed_s = time.perf_counter() - start
    return result


def _answer(question: str, history, result: AgentResult) -> None:
    question = question.strip() if isinstance(question, str) else ""
    if not question:
        result.text = prompts.EMPTY_QUESTION_MESSAGE
        return
    if len(question) > prompts.MAX_QUESTION_CHARS:
        result.text = prompts.TOO_LONG_MESSAGE
        return

    retrieval = retrieve(question, k=RETRIEVAL_K)
    result.sources = [Source(chunk.id, chunk.heading) for chunk, _ in retrieval.hits]
    result.retrieval_method = retrieval.method

    contents = _history_contents(history)
    contents.append(types.Content(role="user", parts=[types.Part(text=prompts.user_turn(question, retrieval.hits))]))
    while True:
        tools_allowed = result.llm_calls < MAX_GENERATE_CALLS - 1 and len(result.sql_runs) < MAX_SQL_RUNS
        response = llm.generate(contents, TOOLS_CONFIG if tools_allowed else FINAL_CONFIG)
        result.llm_calls += 1
        result.model = response.model_version or result.model
        content = response.candidates[0].content if response.candidates else None
        parts = (content.parts or []) if content else []
        calls = [part.function_call for part in parts if part.function_call]
        if calls and tools_allowed:
            contents.append(content)  # as returned, so Gemini 3 thought signatures go back with it
            contents.append(types.Content(role="user", parts=[_run_tool(call, result) for call in calls]))
            continue
        text = "".join(part.text for part in parts if part.text and not part.thought).strip()
        if text:
            result.text, result.status = text, "ok"
            notes = [chunk.text for chunk, _ in retrieval.hits]
            result.grounding = check_grounding(text, question, result.sql_runs, notes)
        else:
            result.text = prompts.GAVE_UP_MESSAGE
        return


def _history_contents(history) -> list[types.Content]:
    """The last MAX_HISTORY_TURNS (question, answer) pairs as user/model turns: text only, no tables."""
    contents = []
    for question, answer_text in list(history or [])[-MAX_HISTORY_TURNS:]:
        contents.append(types.Content(role="user", parts=[types.Part(text=str(question)[:HISTORY_MAX_CHARS])]))
        contents.append(types.Content(role="model", parts=[types.Part(text=str(answer_text)[:HISTORY_MAX_CHARS])]))
    return contents


# The run_sql tool

def _run_tool(call: types.FunctionCall, result: AgentResult) -> types.Part:
    """Executes one function call from the model and returns the function response part to send back."""
    query = (call.args or {}).get("query")
    if call.name != "run_sql":
        response = {"error": f"Unknown tool {call.name!r}. The only tool is run_sql."}
    elif not isinstance(query, str) or not query.strip():
        response = {"error": "run_sql needs a 'query' argument with one SQL SELECT statement."}
    elif len(result.sql_runs) >= MAX_SQL_RUNS:
        response = {"error": f"The limit of {MAX_SQL_RUNS} queries per question is reached. "
                             "Answer with the results you already have."}
    else:
        run = execute_sql(query)
        result.sql_runs.append(run)
        response = {"error": run.error} if run.error else tool_result(run)
    return types.Part(function_response=types.FunctionResponse(id=call.id, name=call.name or "run_sql",
                                                               response=response))


def execute_sql(sql: str) -> SqlRun:
    try:
        query = run_select(sql, max_rows=SQL_MAX_ROWS)
    except SQLGuardError as error:
        return SqlRun(sql=sql, columns=[], rows=pd.DataFrame(), row_count=0, truncated=False, error=str(error))
    return SqlRun(sql=sql, columns=query.columns, rows=query.rows, row_count=len(query.rows),
                  truncated=query.truncated)


def tool_result(run: SqlRun) -> dict:
    """The compact result sent to the model: at most TOOL_MAX_ROWS rows and TOOL_MAX_CHARS characters of CSV."""
    lines = [_csv_line(run.columns)]
    length = len(lines[0])
    for row in run.rows.head(TOOL_MAX_ROWS).itertuples(index=False, name=None):
        line = _csv_line([_cell(value) for value in row])
        if length + len(line) > TOOL_MAX_CHARS:
            break
        lines.append(line)
        length += len(line)
    shown = len(lines) - 1
    result = {"columns": run.columns, "row_count": run.row_count,
              "truncated": run.truncated or shown < run.row_count, "csv": "".join(lines)}
    if result["truncated"]:
        total = f"more than {run.row_count}" if run.truncated else str(run.row_count)
        result["note"] = (f"Only the first {shown} of {total} rows are shown. "
                          "Aggregate, filter or add LIMIT in SQL to see what matters.")
    return result


def _csv_line(values) -> str:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerow(values)
    return buffer.getvalue()


def _cell(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, float):
        return repr(round(value, 4))
    text = str(value)
    return text if len(text) <= TOOL_MAX_CELL_CHARS else text[:TOOL_MAX_CELL_CHARS] + "..."


# Grounding check

_NUMBER = re.compile(r"""
    (?<![\d.,])
    (?P<whole>\d{1,3}(?:,\d{3})+|\d+)   # 1,035 or 1035
    (?P<fraction>\.\d+)?                # .6
    (?P<percent>\s?%)?
    (?P<ordinal>(?:st|nd|rd|th)\b)?     # 1st, 4th: a rank, not a value
""", re.VERBOSE | re.IGNORECASE)
FIRST_YEAR, LAST_YEAR = 1896, 2016
# Positions, not values: ordered-list markers ("1." or "2)" starting a line, also "- 1." or "**1.**")
# and rank positions ("No. 1", "#2", "rank 3", "top 10"). A number with more digits after a comma or
# point ("number 5,034") is still checked.
_POSITION = re.compile(r"""
    ^[ \t]*[-*•]*[ \t]*\(?\d{1,3}[.)]\**(?=\s)
    | (?:\#|\bno\.[ \t]?|\b(?:rank|ranks|ranked|position|place|placed|number|top)[ \t]+)\d{1,3}(?![\d,.]?\d)
""", re.VERBOSE | re.MULTILINE | re.IGNORECASE)


class _Number(NamedTuple):
    token: str  # as written, e.g. "1,035" or "48.6%"
    value: float
    decimals: int
    percent: bool
    is_year: bool


def _numbers(text: str) -> list[_Number]:
    found = []
    for match in _NUMBER.finditer(text):
        if match["ordinal"]:
            continue
        whole, fraction = match["whole"], match["fraction"] or ""
        value = float(whole.replace(",", "") + fraction)
        is_year = (not fraction and "," not in whole and len(whole) == 4 and FIRST_YEAR <= value <= LAST_YEAR)
        found.append(_Number(match.group().strip(), value, max(len(fraction) - 1, 0), bool(match["percent"]), is_year))
    return found


def check_grounding(answer_text: str, question: str, sql_runs: Sequence[SqlRun], notes: Sequence[str]) -> dict:
    """Flags numbers in the answer that appear in neither this question's SQL results nor its notes.

    A number matches a value when the value, rounded to the number's decimals, is equal to it (192.1
    matches 192.07); a percentage also matches a fraction (48.6% matches 0.486). Years from 1896 to
    2016, numbers that appear in the question, list markers and rank positions are not checked.
    """
    known = _known_values(sql_runs, notes)
    asked = {number.value for number in _numbers(question)}
    unverified = []
    for number in _numbers(_POSITION.sub(" ", answer_text)):
        if number.is_year or number.value in asked or _matches(number, known):
            continue
        if number.token not in unverified:
            unverified.append(number.token)
    return {"verified": not unverified, "unverified_numbers": unverified}


def _known_values(sql_runs: Sequence[SqlRun], notes: Sequence[str]) -> set[float]:
    known = set()
    for run in sql_runs:
        if run.error:
            continue
        known.add(float(run.row_count))
        for value in run.rows.to_numpy().ravel():
            if isinstance(value, numbers.Real) and not isinstance(value, bool):
                if not math.isnan(value):
                    known.add(float(value))
            elif isinstance(value, str):
                known.update(number.value for number in _numbers(value))
    for note in notes:
        known.update(number.value for number in _numbers(note))
    return known


def _matches(number: _Number, known: set[float]) -> bool:
    for value in known:
        candidates = (value, value * 100) if number.percent else (value,)
        if any(math.isclose(round(candidate, number.decimals), number.value, abs_tol=1e-9) for candidate in candidates):
            return True
    return False
