"""
scoring.py
----------
Scores one agent answer against its evaluation case. Only the saved record is used (answer text,
status, SQL runs, grounding), so a results file can be re-scored without calling Gemini.

    score(case, record) -> {check: passed}   only the checks that apply to the case

Checks:
    status         the agent answered (status "ok")
    numbers        every expected number appears (1,035 = 1035 = 1035.0; "eight" = 8; within its tolerance;
                   an expected number with an any_of list accepts any one of its values)
    names          at least one of the names or key terms appears
    sql            expect_sql true: a query ran without error; false: no query ran
    out_of_scope   a refusal is recognised (expected refusals only)
    grounded       the agent's grounding check verified every number
    language       English questions get English answers, Hinglish questions Hinglish throughout
    plain_english  no table, view or column names, SQL or "column"/"rows" jargon
    forbidden      none of the case's must_not_contain strings appears
"""

import re

from chatbot.eval import alternatives

CHECKS = ("status", "numbers", "names", "sql", "out_of_scope", "grounded", "language", "plain_english", "forbidden")

_NUMBER = re.compile(r"(?<![\w.,])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?")
_NUMBER_WORDS = {word: value for value, word in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen twenty".split())}

# Common Hindi words written in Latin letters; none of them is an English word.
HINGLISH_WORDS = frozenset("""
    hai hain tha thi thhe ne mein ka ki ke ko se kya kitne kitni kitna kaun kaunsa kaunse sabse jeete jeeta
    jeeti jita jite jeet nahi nahin aur bhi yeh ye woh wo liye lekin sakta sakte sakti gaye gaya gayi diye
    diya kiya kiye apne unhone inhone mujhe aap hum matlab jaise wala wale wali raha rahe rahi hota hote hoti
    mila mile mili saal baar tak sirf koi kuch agar toh pe jo jab kab kaise kyun kyunki isliye bahut zyada
    pehle baad dono sab gaya hua hue huye karke karta karte kar unka unki inka inki iska iski uska uski
""".split())
_WORD = re.compile(r"[A-Za-z]+")
_SENTENCE_END = re.compile(r"(?<!\d)[.!?](?!\d)|\n")
_QUOTED = re.compile(r"\"[^\"]*\"|“[^”]*”")
MIN_SENTENCE_WORDS = 4

_REFUSAL = re.compile(r"""
    outside | beyond | opinion | unable | not\ able | can't | cannot | can\ only | only\ read
    | only\ (?:covers?|has|have|includes?|contains?|goes|runs|answers?)
    | (?:doesn't|does\ not|don't|do\ not)\ (?:have|include|cover|contain|go)
    | (?:isn't|is\ not|aren't|are\ not|not)\ (?:in|part\ of|covered|included)\b
    | no\ (?:data|information|results)
    | \bnahi\b | \bnahin\b
""", re.IGNORECASE | re.VERBOSE)

_JARGON = re.compile(r"""
    \b[a-z]+_[a-z_]+\b              # identifiers such as athlete_id or country_medals
    | \bcolumns?\b | \bSQL\b | \bSELECT\b | \bNULL\b | \brows\b
    | \b(?:database|the|a|this)\ views?\b
""", re.VERBOSE)


def score(case: dict, record: dict) -> dict[str, bool]:
    text = (record.get("text") or "").replace("’", "'")
    runs = record.get("sql_runs") or []
    checks = {"status": record.get("status") == "ok"}
    if case["numbers"]:
        checks["numbers"] = all(any(has_number(text, value["value"], value.get("tolerance", 0))
                                    for value in alternatives(number)) for number in case["numbers"])
    if case["names"]:
        checks["names"] = any(has_term(text, name) for name in case["names"])
    if case["expect_sql"] is True:
        checks["sql"] = any(not run.get("error") for run in runs)
    elif case["expect_sql"] is False:
        checks["sql"] = not runs
    if case["expect_out_of_scope"]:
        checks["out_of_scope"] = bool(_REFUSAL.search(text))
    checks["grounded"] = bool((record.get("grounding") or {}).get("verified", True))
    checks["language"] = language_matches(text, case["language"])
    checks["plain_english"] = not jargon(text)
    if case["must_not_contain"]:
        checks["forbidden"] = not any(term.lower() in text.lower() for term in case["must_not_contain"])
    return checks


def numbers_in(text: str) -> list[float]:
    """Every number written in the text, with commas removed, plus the number words zero to twenty."""
    values = [float(match[1].replace(",", "") + (match[2] or "")) for match in _NUMBER.finditer(text)]
    values += [float(_NUMBER_WORDS[word]) for word in _WORD.findall(text.lower()) if word in _NUMBER_WORDS]
    return values


def has_number(text: str, value: float, tolerance: float = 0) -> bool:
    return any(abs(found - value) <= tolerance + 1e-9 for found in numbers_in(text))


def has_term(text: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.IGNORECASE) is not None


def hinglish_words(text: str) -> int:
    return sum(word in HINGLISH_WORDS for word in _WORD.findall(text.lower()))


def language_matches(text: str, language: str) -> bool:
    """English: at most one Hinglish word in the whole answer. Hinglish: every sentence of at least
    MIN_SENTENCE_WORDS words contains a Hinglish word. Quoted text (an example question) is ignored."""
    text = _QUOTED.sub(" ", text)
    if language == "en":
        return hinglish_words(text) <= 1
    sentences = [s for s in _SENTENCE_END.split(text) if len(_WORD.findall(s)) >= MIN_SENTENCE_WORDS]
    return bool(sentences) and all(hinglish_words(sentence) for sentence in sentences)


def jargon(text: str) -> list[str]:
    return sorted({match.group().strip() for match in _JARGON.finditer(text)})
