"""
Offline checks of the evaluation set, chatbot/eval/cases.json: its shape and mix, and every expected
number and name against the data. Each reference SQL runs through run_select() and must return the
expected value, so the eval set itself is verified without any Gemini call.
"""

import math
from collections import Counter

import pytest

from chatbot.db import run_select
from chatbot.eval import CATEGORIES, LANGUAGES, SPLITS, alternatives, load_cases
from chatbot.prompts import MAX_QUESTION_CHARS

CASES = load_cases()
NUMBERS = [(case["id"], value) for case in CASES for number in case["numbers"] + case["history_numbers"]
           for value in alternatives(number)]
NAMED = [case for case in CASES if case["name_sql"]]
ALLOWED_FIELDS = {"id", "question", "category", "split", "language", "history", "numbers", "names", "name_sql",
                  "must_not_contain", "history_numbers", "expect_sql", "expect_out_of_scope"}


def scalar(sql: str):
    result = run_select(sql)
    assert result.rows.shape == (1, 1), f"the reference SQL must return one value: {sql}"
    return result.rows.iloc[0, 0]


def test_every_case_is_well_formed():
    assert len({case["id"] for case in CASES}) == len(CASES)
    for case in CASES:
        assert set(case) <= ALLOWED_FIELDS, case["id"]
        assert case["category"] in CATEGORIES and case["split"] in SPLITS and case["language"] in LANGUAGES
        assert 0 < len(case["question"]) <= MAX_QUESTION_CHARS
        assert case["expect_sql"] in (True, False, None) and case["expect_out_of_scope"] in (True, False)
        assert all(len(turn) == 2 and all(isinstance(text, str) for text in turn) for turn in case["history"])
        for number in case["numbers"] + case["history_numbers"]:
            if "any_of" in number:  # several defensible values, with the reason in why
                assert set(number) == {"any_of", "why"} and len(number["any_of"]) >= 2 and number["why"].strip()
            for value in alternatives(number):
                assert set(value) <= {"value", "sql", "tolerance"} and value["sql"].strip()


def test_the_mix_of_categories_and_splits():
    assert Counter(case["category"] for case in CASES) == {
        "findings": 10, "new_sql": 15, "notes": 5, "out_of_scope": 4, "safety": 2, "hinglish": 3, "follow_up": 2}
    splits = Counter(case["split"] for case in CASES)
    assert 20 <= splits["dev"] <= 24 and splits["test"] == 10 and splits["test2"] == 8
    test = {case["category"] for case in CASES if case["split"] == "test"}
    assert test == set(CATEGORIES) - {"follow_up"}  # the follow-up pair stays together in dev
    test2 = Counter(case["category"] for case in CASES if case["split"] == "test2")
    assert test2 == {"new_sql": 5, "notes": 1, "out_of_scope": 1, "hinglish": 1}
    assert Counter(case["language"] for case in CASES)["hinglish"] == 3


def test_no_question_is_asked_twice():
    questions = [" ".join(case["question"].lower().split()) for case in CASES]
    assert len(questions) == len(set(questions))


def test_refusals_expect_no_numbers_and_no_sql_for_unsafe_requests():
    for case in CASES:
        if case["expect_out_of_scope"]:
            assert case["numbers"] == []
        if case["category"] == "safety":
            assert case["expect_out_of_scope"] and case["expect_sql"] is False


def test_only_a_follow_up_has_history_and_its_numbers_are_in_it():
    with_history = [case for case in CASES if case["history"]]
    assert [case["category"] for case in with_history] == ["follow_up"]
    (case,) = with_history
    earlier_answer = case["history"][-1][1]
    for number in case["history_numbers"]:
        assert f"{number['value']:g}" in earlier_answer.replace(",", "")


@pytest.mark.parametrize("case_id, number", NUMBERS, ids=[f"{case_id}={n['value']:g}" for case_id, n in NUMBERS])
def test_reference_sql_returns_the_expected_number(case_id, number):
    assert math.isclose(float(scalar(number["sql"])), number["value"], abs_tol=1e-9)


@pytest.mark.parametrize("case", NAMED, ids=[case["id"] for case in NAMED])
def test_reference_sql_returns_one_of_the_names(case):
    value = str(scalar(case["name_sql"])).lower()
    assert any(name.lower() in value for name in case["names"]), value
