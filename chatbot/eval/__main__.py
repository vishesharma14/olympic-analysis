"""
python -m chatbot.eval
----------------------
Asks the evaluation cases to the real agent (Gemini free tier), scores the answers and writes
chatbot/eval/results/<tag>.json and chatbot/eval/REPORT.md.

    python -m chatbot.eval                                  every case, tag "latest"
    python -m chatbot.eval --split dev --tag tuning         the dev split only
    python -m chatbot.eval --only f-phelps,q-events-1896 --tag tuning
    python -m chatbot.eval --split dev --temperature 1.0 --tag temperature-1
    python -m chatbot.eval --rescore --tag tuning           re-score a saved run, no API calls
    python -m chatbot.eval --report final,final-test2       REPORT.md for saved runs together, no API calls

Questions start QUESTION_INTERVAL_S seconds after the previous answer, and chat requests are kept
under MAX_CHAT_PER_MINUTE. Each case is saved as soon as it is answered, so a run that was
interrupted resumes where it stopped when started again with the same tag; cases that ended in a
quota error are asked again. The run stops after QUOTA_STOP quota errors in a row.

Question embeddings are cached in the system temp directory (keyed by embedding model, dimensions
and text), so each question is embedded once across runs and every run retrieves the same notes.
"""

import argparse
import hashlib
import json
import logging
import math
import re
import sys
import tempfile
import time
from collections import Counter, deque
from contextlib import contextmanager
from pathlib import Path

import numpy as np
from google.genai import types

from chatbot import agent, llm
from chatbot.eval import REPORT_PATH, RESULTS_DIR, SPLITS, load_cases
from chatbot.eval.report import load_all_results, now, summarize, write_report
from chatbot.eval.scoring import score

QUESTION_INTERVAL_S = 5.0
MAX_CHAT_PER_MINUTE = 12  # the free tier allows 15 requests a minute per model
EMBED_INTERVAL_S = 1.0
QUOTA_STOP = 2
PREVIEW_ROWS = 5
EMBED_CACHE_PATH = Path(tempfile.gettempdir()) / "olympics_eval_query_vectors.json"

log = logging.getLogger("chatbot.eval")


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    all_cases = load_cases()
    if args.report:
        runs = [load_results(tag) for tag in args.report]
        case_ids = [case_id for results in runs for case_id in results["records"]]
        if len(case_ids) != len(set(case_ids)):
            sys.exit("These runs share cases; report them one at a time.")
        write_report(runs, REPORT_PATH, load_all_results(RESULTS_DIR))
        print("\n".join(summary_text(results) for results in runs))
        return
    path = RESULTS_DIR / f"{args.tag}.json"
    if args.rescore:
        results = load_results(args.tag)
        rescore(results, all_cases)
    else:
        cases = select(all_cases, args.split, args.only)
        results = run(cases, all_cases, path, args)
    save(results, path, all_cases)
    write_report([results], REPORT_PATH, load_all_results(RESULTS_DIR))
    print(summary_text(results))


def load_results(tag: str) -> dict:
    path = RESULTS_DIR / f"{tag}.json"
    if not path.exists():
        sys.exit(f"No results file for tag {tag!r}.")
    return json.loads(path.read_text(encoding="utf-8"))


def run(cases: list[dict], all_cases: list[dict], path: Path, args) -> dict:
    results = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if results is None:
        temperature = agent.TEMPERATURE if args.temperature is None else args.temperature
        results = {"run": {"tag": args.tag, "started": now(), "updated": now(), "temperature": temperature,
                           "models": list(llm.chat_models()), "api_requests": {}}, "records": {}}
    elif args.temperature is not None and args.temperature != results["run"]["temperature"]:
        sys.exit(f"Tag {args.tag!r} was run at temperature {results['run']['temperature']:g}; use a new tag.")
    temperature = results["run"]["temperature"]

    todo = [case for case in cases if results["records"].get(case["id"], {}).get("status") in (None, "quota")]
    print(f"Run {args.tag!r}: {len(todo)} of {len(cases)} cases to ask, temperature {temperature:g}, "
          f"models {' -> '.join(llm.chat_models())}")
    if not todo:
        return results

    usage_before = Counter(llm.usage)
    embeddings = EmbeddingCache(EMBED_CACHE_PATH)
    with eval_settings(temperature, embeddings):
        embeddings.warm([case["question"] for case in todo])
        quota_streak, last_end = 0, -math.inf
        for number, case in enumerate(todo, 1):
            time.sleep(max(0.0, last_end + QUESTION_INTERVAL_S - time.monotonic()))
            result = agent.answer(case["question"], history=[tuple(turn) for turn in case["history"]])
            last_end = time.monotonic()
            record = to_record(case, result)
            results["records"][case["id"]] = record
            results["run"].update(updated=now(), models=list(llm.chat_models()),
                                  api_requests=_add_usage(results["run"]["api_requests"], usage_before))
            usage_before = Counter(llm.usage)
            save(results, path, all_cases)
            failed = [check for check, passed in record["checks"].items() if not passed]
            print(f"[{number}/{len(todo)}] {case['id']:<26} "
                  f"{'PASS' if record['passed'] else 'FAIL ' + ','.join(failed):<30} "
                  f"{result.llm_calls} calls {result.elapsed_s:5.1f} s  {result.model or '-'}")
            quota_streak = quota_streak + 1 if result.status == "quota" else 0
            if quota_streak >= QUOTA_STOP:
                print(f"Stopped after {QUOTA_STOP} quota errors in a row; run the same command later to resume.")
                break
    return results


def select(cases: list[dict], split: str, only: str | None) -> list[dict]:
    selected = [case for case in cases if split == "all" or case["split"] == split]
    if only:
        wanted = [name.strip() for name in only.split(",") if name.strip()]
        unknown = set(wanted) - {case["id"] for case in cases}
        if unknown:
            sys.exit(f"Unknown case ids: {', '.join(sorted(unknown))}")
        selected = [case for case in selected if case["id"] in wanted]
    return selected


@contextmanager
def eval_settings(temperature: float, embeddings: "EmbeddingCache"):
    """For the duration of a run: the given temperature, paced chat requests and cached question
    embeddings. Everything is restored afterwards."""
    saved = llm.generate, llm.embed_query, agent.TOOLS_CONFIG, agent.FINAL_CONFIG
    llm.generate = paced(llm.generate, Pacer(MAX_CHAT_PER_MINUTE))
    llm.embed_query = embeddings.wrap(llm.embed_query)
    agent.TOOLS_CONFIG = agent._config(types.FunctionCallingConfigMode.AUTO, temperature)
    agent.FINAL_CONFIG = agent._config(types.FunctionCallingConfigMode.NONE, temperature)
    try:
        yield
    finally:
        llm.generate, llm.embed_query, agent.TOOLS_CONFIG, agent.FINAL_CONFIG = saved


def to_record(case: dict, result: agent.AgentResult) -> dict:
    record = {
        "id": case["id"], "question": case["question"], "category": case["category"], "split": case["split"],
        "status": result.status, "text": result.text,
        "sql_runs": [{"sql": run.sql, "row_count": run.row_count, "truncated": run.truncated, "error": run.error,
                      "preview": json.loads(run.rows.head(PREVIEW_ROWS).to_json(orient="values"))}
                     for run in result.sql_runs],
        "sources": [source.id for source in result.sources], "retrieval_method": result.retrieval_method,
        "model": result.model, "llm_calls": result.llm_calls, "elapsed_s": round(result.elapsed_s, 2),
        "grounding": result.grounding,
    }
    record["checks"] = score(case, record)
    record["passed"] = all(record["checks"].values())
    return record


def rescore(results: dict, cases: list[dict]) -> None:
    """Scores the saved answers again with the current cases and checks."""
    by_id = {case["id"]: case for case in cases}
    for case_id, record in list(results["records"].items()):
        case = by_id.get(case_id)
        if case is None:
            del results["records"][case_id]
            continue
        record.update(category=case["category"], split=case["split"], checks=score(case, record))
        record["passed"] = all(record["checks"].values())


def save(results: dict, path: Path, cases: list[dict]) -> None:
    """Writes the results in case-file order, through a temporary file so a crash never leaves half a file."""
    order = {case["id"]: number for number, case in enumerate(cases)}
    results["records"] = dict(sorted(results["records"].items(), key=lambda item: order.get(item[0], len(order))))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def summary_text(results: dict) -> str:
    records = list(results["records"].values())
    lines = [f"\nRun {results['run']['tag']!r}:"]
    for name in (*SPLITS, "all"):
        group = records if name == "all" else [r for r in records if r["split"] == name]
        if group:
            s = summarize(group)
            lines.append(f"  {name:<4} {s['passed']}/{s['cases']} passed, grounded {s['grounded']}/{s['answered']}, "
                         f"median {s['median_s'] or 0:.1f} s, p90 {s['p90_s'] or 0:.1f} s, "
                         f"{s['avg_calls']:.1f} Gemini calls per question")
    lines.append(f"  API requests (all sessions of this tag): {results['run']['api_requests']}")
    return "\n".join(lines)


def _add_usage(total: dict, before: Counter) -> dict:
    merged = Counter(total)
    merged.update(Counter(llm.usage) - before)
    return dict(merged)


# Rate limits and the embedding cache

class Pacer:
    """Keeps requests under per_minute in any 60-second window by waiting before each one."""

    def __init__(self, per_minute: int, clock=time.monotonic, sleep=time.sleep):
        self.per_minute, self.clock, self.sleep = per_minute, clock, sleep
        self.sent: deque[float] = deque()

    def wait(self) -> None:
        while True:
            current = self.clock()
            while self.sent and current - self.sent[0] >= 60:
                self.sent.popleft()
            if len(self.sent) < self.per_minute:
                self.sent.append(current)
                return
            self.sleep(60 - (current - self.sent[0]) + 0.1)


def paced(generate, pacer: Pacer):
    def paced_generate(*args, **kwargs):
        pacer.wait()
        return generate(*args, **kwargs)
    return paced_generate


class EmbeddingCache:
    """Question vectors saved as JSON, keyed by a hash of the embedding model, dimensions and text."""

    def __init__(self, path: Path):
        self.path = path
        try:
            self.vectors = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.vectors = {}

    def key(self, text: str) -> str:
        return hashlib.sha256(f"{llm.embed_model()}|{llm.EMBED_DIMENSIONS}|{text}".encode()).hexdigest()

    def wrap(self, embed_query):
        def cached_embed_query(text: str) -> np.ndarray:
            key = self.key(text)
            if key not in self.vectors:
                self.vectors[key] = [float(x) for x in embed_query(text)]
                self.path.write_text(json.dumps(self.vectors), encoding="utf-8")
            return np.array(self.vectors[key], dtype=np.float32)
        self.embed_query = cached_embed_query
        return cached_embed_query

    def warm(self, questions: list[str]) -> None:
        """Embeds the questions that are not cached yet, EMBED_INTERVAL_S apart (as retrieval normalises them)."""
        missing = list(dict.fromkeys(q for q in (" ".join(q.split()) for q in questions)
                                     if self.key(q) not in self.vectors))
        for number, question in enumerate(missing):
            if number:
                time.sleep(EMBED_INTERVAL_S)
            try:
                self.embed_query(question)
            except Exception as error:  # as in retrieval: quota, network or no key
                log.warning("Could not embed a question (%s); it will use keyword retrieval.", type(error).__name__)


def _parse_args(argv):
    parser = argparse.ArgumentParser(description="Evaluate the Ask the data agent on chatbot/eval/cases.json.")
    parser.add_argument("--split", choices=(*SPLITS, "all"), default="all")
    parser.add_argument("--only", help="comma-separated case ids")
    parser.add_argument("--tag", default="latest", help="results/<tag>.json; the same tag resumes a run")
    parser.add_argument("--temperature", type=float, help=f"default {agent.TEMPERATURE:g}")
    parser.add_argument("--rescore", action="store_true", help="re-score the saved run of --tag without API calls")
    parser.add_argument("--report", metavar="TAGS",
                        help="comma-separated tags: write REPORT.md for these saved runs together, without API calls")
    args = parser.parse_args(argv)
    args.report = [tag.strip() for tag in args.report.split(",") if tag.strip()] if args.report else None
    for tag in [args.tag, *(args.report or [])]:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,60}", tag):
            parser.error("tags may contain only letters, digits, '.', '_' and '-'")
    return args


if __name__ == "__main__":
    main()
