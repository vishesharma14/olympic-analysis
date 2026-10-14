"""
ask.py
------
Asks the "Ask the data" agent one question from the command line and shows how it answered:
the answer, every SQL query with its row count, the notes used, the model, the number of Gemini
calls, the time taken and the grounding check. Uses free-tier quota (one embedding request and
usually two chat requests).

    python -m chatbot.ask "Which country has won the most gold medals?"
"""

import argparse
import logging
import sys
import textwrap

from chatbot.agent import AgentResult, answer


def format_result(result: AgentResult) -> str:
    lines = [f"Answer ({result.status}): {result.text}", ""]
    for number, run in enumerate(result.sql_runs, 1):
        if run.error:
            outcome = f"error: {run.error}"
        else:
            outcome = f"{run.row_count}{'+' if run.truncated else ''} row{'' if run.row_count == 1 else 's'}"
        lines.append(f"SQL {number} ({outcome}):")
        lines.append(textwrap.indent(run.sql.strip(), "    "))
    if not result.sql_runs:
        lines.append("SQL: none")
    sources = ", ".join(f"{source.id} ({source.heading})" for source in result.sources) or "none"
    lines.append(f"Sources ({result.retrieval_method or 'not retrieved'}): {sources}")
    lines.append(f"Model: {result.model or 'none'} | LLM calls: {result.llm_calls} | {result.elapsed_s:.1f} s")
    grounding = result.grounding
    lines.append("Grounding: verified" if grounding["verified"]
                 else f"Grounding: unverified numbers {', '.join(grounding['unverified_numbers'])}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ask the Olympic data assistant one question.")
    parser.add_argument("question", nargs="+", help="the question, quoted or as separate words")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # answers can contain "–" or "—"
    print(format_result(answer(" ".join(args.question))))


if __name__ == "__main__":
    main()
