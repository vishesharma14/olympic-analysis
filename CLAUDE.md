# CLAUDE.md

Guidance for working in this repository.

## Project

Analysis of the Kaggle "120 years of Olympic history" dataset, limited to the Summer Games 1896–2016.

| Path | What it is |
| --- | --- |
| `app.py` | Streamlit dashboard: navigation, layout and charts |
| `helper.py` | Analysis functions for the dashboard: medal tallies, trends, facts, map and race data, top athletes |
| `preprocessor.py` | Loads the CSVs, keeps Summer rows, merges regions, drops duplicate rows (cached) |
| `athlete_events.csv`, `noc_regions.csv` | Source data |
| `sql/` | Schema, SQLite and MySQL loaders, ten analysis queries; `sql/README.md` lists the verified findings |
| `tableau/` | Data preparation and CSVs for the Tableau Public dashboard |
| `chatbot/` | The "Ask the data" chatbot (being built, see the roadmap) |
| `tests/` | pytest tests |

Counting rules shared by the dashboard, `sql/`, `tableau/` and the chatbot views:

- Summer Games only.
- The 1,385 exact duplicate rows in `athlete_events.csv` are removed.
- A team medal counts once per country: `DISTINCT (Team, NOC, Year, City, Sport, Event, Medal)`.
- Countries follow `noc_regions.csv` (the Soviet Union counts as Russia, East and West Germany as Germany).

## Chatbot phase

Goal: an "Ask the data" page in the Streamlit app where a visitor asks a question in plain English and gets an answer computed from the Olympic data. The design is fixed:

- **RAG:** short curated markdown notes (dataset scope, counting rules, findings, glossary), embedded with Gemini and searched by cosine similarity.
- **One tool-using agent:** Gemini receives the retrieved notes plus a `run_sql` tool, writes SQLite SELECT queries against two views that encode the counting rules, and answers with numbers from the result.
- **Sandboxed SQL runner:** read-only, so nothing the model writes can change data or run forever.
- **Evaluation set:** questions with SQL-verified expected answers (the 10 findings in `sql/README.md` plus new questions), scored automatically, with a held-out split.

Built so far in `chatbot/`:

- `views.sql`: `summer_entries` (one row per athlete per event per Games) and `country_medals` (one row per medal won by a country; a relay gold counts once).
- `db.py`:
  - `ensure_database()` builds the database once, at `OLYMPICS_DB_PATH` or `<system temp dir>/olympics_chatbot.db`, and rebuilds it when `sql/schema.sql`, `sql/load_sqlite.py` or `chatbot/views.sql` changes.
  - `run_select()` is the sandboxed SQL runner; it raises `SQLGuardError` with a user-safe message.
  - `SCHEMA_DESCRIPTION` describes both views for the model prompt.
- `knowledge/`: five markdown notes (dataset, counting rules, findings, glossary, project); each `## ` section is one retrieval chunk of 30–200 words, and every statistic is checked against SQL in `tests/test_knowledge.py`. The notes are plain English for a general reader, with no table, view, column or file names (the model copies their wording into answers); SQL hints belong in `SCHEMA_DESCRIPTION`.
- `knowledge.py`: `load_chunks()` splits the notes into `Chunk`s (id `<file>#<heading-slug>`, text `<title> — <heading>` plus the section, HTML comments removed).
- `llm.py`: the only module that talks to Gemini (google-genai SDK): `get_api_key()`, `embed_documents()` / `embed_query()` (768-dim, L2-normalised), and `generate()`, which retries each model once and falls back along `gemini-3.5-flash-lite` -> `gemini-3.1-flash-lite` -> `gemini-3.8-flash`, raising `QuotaExceeded` when all fail; models can be overridden with `GEMINI_CHAT_MODELS` / `GEMINI_EMBED_MODEL`.
  - `gemini-3.8-flash` rejects MINIMAL thinking, so `THINKING_LEVELS` gives it LOW; `generate()` applies a model's level to a copy of the caller's config.
  - A model still failing with 429/503 after its retry is skipped by the process for 5 minutes; a 404 skips it for the rest of the process. The skip list is thread-safe (Streamlit serves sessions on threads).
  - Not in the chain: `gemini-2.5-flash-lite` (404 for this key) and `gemini-3.7-flash` (400 with MINIMAL thinking, not probed with LOW).
- `list_models.py`: lists the models the key can use and their supported actions.
- `build_index.py` + `index/`: embeds every chunk with `gemini-embedding-001` into the committed `index/knowledge_index.npz` (vectors, ids, text hashes, model, dimensions); rerun after editing any note.
- `retrieval.py`: `retrieve(question, k)` ranks chunks by cosine similarity against the index, falling back to BM25 keyword scoring when the question cannot be embedded or the index is out of date.
- `prompts.py`: every text the agent sends to Gemini or shows to users: the system instruction (rules + `SCHEMA_DESCRIPTION`), the `run_sql` tool description, the user turn with its delimited "Reference notes" block, `READ_ONLY_REPLY` (the literal reply rule 6 gives to requests to change data or see the instructions; describing the reply made the model repeat the rule) and the fixed messages for rejected input, quota and errors.
- `agent.py`: `answer(question, history)` -> `AgentResult` (text, status `ok`/`quota`/`error`, `sql_runs`, sources, retrieval method, model, `llm_calls`, elapsed time, grounding). It never raises.
  - Flow: validate (non-empty, at most 300 characters, no model call otherwise) -> `retrieve(question, k=4)` -> Gemini with the `run_sql` tool -> answer. Function calling is manual, so every query is recorded; the model gets a compact result (up to 50 rows as CSV, about 4,000 characters) or the `SQLGuardError` message.
  - Limits: 3 `run_sql` executions and 5 `generate()` calls per question; the last call has tools disabled. MINIMAL thinking, the last 2 turns of history (text only).
  - `TEMPERATURE = 1.0`: Google's default for Gemini 3 (lower may loop or degrade). Chosen on the dev split in Step 6: 22/23 at 1.0 against 20/23 at 0, with similar latency; at 0 one answer came back as the bare token `_not_in_database`.
  - Grounding check (a flag, never blocks): numbers in the answer must appear in this question's SQL results or retrieved notes; years 1896–2016, numbers from the question, list markers ("1.", "2)") and rank positions ("No. 1", "top 10") are ignored.
- `ask.py`: `python -m chatbot.ask "question"` prints the answer, each SQL with its row count, the sources, model, calls, time and grounding.
- `ui.py`: `render()` draws the "Ask the data" page: example questions while the chat is empty, chat bubbles (history in `st.session_state`, the last 2 turns passed to `answer()`), a grounding line under each answer, and a "How this was answered" expander with each SQL, its rows, the note headings, retrieval method, model, Gemini calls and time. No key -> an info box and no chat input; the database is built through `st.cache_resource`.
  - Usage limits, overridable with an env var or Streamlit secret of the same name (`llm.get_setting`, which also accepts TOML numbers): `CHAT_SESSION_LIMIT` (15 questions per browser session; Clear chat does not reset it), `CHAT_DAILY_LIMIT` (200 per UTC day for the whole app, a thread-safe counter in `st.cache_resource`) and `CHAT_MIN_INTERVAL_S` (3 s between questions of a session). Questions are kept only in `st.session_state`.
- `app.py`: "Ask the data" is the last sidebar option; `chatbot.ui` is imported only on that page, so the dashboard pages never load google-genai or build the chatbot database.
- `ui.py` needs `streamlit>=1.64` (`st.chat_input(submit_mode=...)`, `st.button(width=...)`).
- `eval/`: the evaluation set and runner.
  - `cases.json`: 41 cases, each with a category (findings, new_sql, notes, out_of_scope, safety, hinglish, follow_up) and a split. Every expected number and name has a reference SQL that `tests/test_eval_cases.py` runs offline; an expected number with `any_of` accepts several defensible values and says why.
  - Splits: `dev` (23, tuned on), `test` (10; meant to be held out, but a test failure led to a notes change in Step 6, so it counts as tuned on) and `test2` (8, held out: written after the last change and run once). Write a fresh held-out split before claiming a new held-out score.
  - `scoring.py` checks status, numbers, names, SQL use, refusals, grounding, language (English vs Hinglish), plain English (no SQL or column jargon) and forbidden strings, from the saved answer only. `report.py` writes `REPORT.md`, which marks each split held out or tuned on (`SPLIT_ROLES`) and keeps a table of all runs.
  - `__main__.py` (`python -m chatbot.eval`) asks the real agent, paces requests under the free-tier limit, caches question embeddings in the temp dir, saves `results/<tag>.json` after every case (the same tag resumes) and stops after 2 quota errors in a row. The results files are the run history: keep them.
  - Step 6 results: baseline 18/33 (55%) at temperature 0 -> final at 1.0: dev 21/23, old test 8/10, held-out test2 8/8, every answer grounded. Seen in the final answers but not caught by the checks: the read-only reply was also given to an out-of-scope prediction question, one answer began with a stray "Preferences: none", and one added an unrelated counting rule.

`chatbot/db.py` imports `sql.load_sqlite`, so the repo root must be on `sys.path`. `streamlit run app.py` and `pytest.ini` both take care of this.

## Roadmap

1. Data foundation: views + read-only SQL runner + tests (**done**)
2. Knowledge notes for RAG (markdown, every number checked against SQL) (**done**)
3. Gemini client + embeddings index + retrieval (**done**)
4. Agent: retrieve -> Gemini with run_sql tool -> answer, with guardrails (**done**)
5. Streamlit "Ask the data" page (**done**)
6. Evaluation set + script + fixes (**done**)
7. Deploy to Streamlit Community Cloud with secrets, README, screenshots (**next**)

## Working rules

- One roadmap step per request.
- Run the tests before reporting a step.
- Stop and wait for approval after each step.
- Commit only when asked.
- Keep `app.py` changes minimal; chatbot code lives in `chatbot/`.
- The Gemini API key lives only in `.streamlit/secrets.toml` (gitignored) and in Streamlit Cloud Secrets. Never print, log, echo, copy or commit it, and never display the contents of `secrets.toml`.
- No README claims for anything that has not been built and tested.
- The chatbot covers the Summer Games 1896–2016 only, matching the dashboard.

## Commands

```bash
pip install -r requirements.txt       # app dependencies
pip install -r requirements-dev.txt   # app dependencies + pytest
streamlit run app.py                  # dashboard at http://localhost:8501
python sql/load_sqlite.py             # build sql/olympics.db
python sql/run_queries.py             # all ten SQL questions; add a number (e.g. 3) for one
python -m pytest -q                   # tests; the first run builds the chatbot database (about 20 s)
python -m chatbot.list_models         # Gemini models this key can use
python -m chatbot.build_index         # re-embed the knowledge notes (skips if the index is current)
python -m pytest -m live tests/test_live.py -q   # live Gemini retrieval tests; 8 embedding requests
python -m chatbot.ask "question"      # ask the agent one question; about 1 embedding + 2 chat requests
python -m pytest -m live tests/test_agent_live.py -q -s   # live agent smoke test; about 30 requests of free quota
python -m chatbot.eval --split dev|test|test2|all --tag NAME   # evaluate the agent; about 1.8 chat requests per case
python -m chatbot.eval --rescore --tag NAME              # re-score a saved run with the current checks, no API calls
python -m chatbot.eval --report final,final-test2        # REPORT.md for several saved runs together, no API calls
```
