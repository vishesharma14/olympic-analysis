"""
chatbot.eval
------------
Evaluation of the "Ask the data" agent.

    cases.json     the evaluation set: questions, expected numbers with reference SQL, expectations
    scoring.py     scores one answer against its case (no API calls)
    report.py      writes REPORT.md from a results file
    __main__.py    python -m chatbot.eval: runs the cases against Gemini and writes the results

Results go to results/<tag>.json and the report to REPORT.md.
"""

import json
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
CASES_PATH = EVAL_DIR / "cases.json"
RESULTS_DIR = EVAL_DIR / "results"
REPORT_PATH = EVAL_DIR / "REPORT.md"

SPLITS = ("dev", "test", "test2")
# Whether each split's score is held out, and why: the report states it next to every score.
SPLIT_ROLES = {
    "dev": ("tuned on", "used to tune the prompts, the notes and the temperature"),
    "test": ("tuned on", "written as held out, but a failure in it led to a change of the notes in Step 6"),
    "test2": ("held out", "written after the last change to the code, prompts and notes, and run once"),
}
CATEGORIES = ("findings", "new_sql", "notes", "out_of_scope", "safety", "hinglish", "follow_up")
LANGUAGES = ("en", "hinglish")

_DEFAULTS = {"history": [], "numbers": [], "names": [], "name_sql": None, "must_not_contain": [],
             "history_numbers": [], "expect_sql": None, "expect_out_of_scope": False}


def load_cases(path: Path = CASES_PATH) -> list[dict]:
    """The evaluation cases in file order, with every optional field filled in."""
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    return [{**_DEFAULTS, **case} for case in cases]


def alternatives(number: dict) -> list[dict]:
    """The accepted values of an expected number: itself, or each entry of its any_of list."""
    return number.get("any_of", [number])
