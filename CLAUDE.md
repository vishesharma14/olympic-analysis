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
- **Evaluation set** built from the 10 verified SQL findings in `sql/README.md`.

Built so far in `chatbot/`:

- `views.sql`: `summer_entries` (one row per athlete per event per Games) and `country_medals` (one row per medal won by a country; a relay gold counts once).
- `db.py`:
  - `ensure_database()` builds the database once, at `OLYMPICS_DB_PATH` or `<system temp dir>/olympics_chatbot.db`, and rebuilds it when `sql/schema.sql`, `sql/load_sqlite.py` or `chatbot/views.sql` changes.
  - `run_select()` is the sandboxed SQL runner; it raises `SQLGuardError` with a user-safe message.
  - `SCHEMA_DESCRIPTION` describes both views for the model prompt.
- `knowledge/`: five markdown notes (dataset, counting rules, findings, glossary, project); each `## ` section is one retrieval chunk of 30–200 words, and every statistic is checked against SQL in `tests/test_knowledge.py`.
- `knowledge.py`: `load_chunks()` splits the notes into `Chunk`s (id `<file>#<heading-slug>`, text `<title> — <heading>` plus the section, HTML comments removed).
- `llm.py`: the only module that talks to Gemini (google-genai SDK): `get_api_key()`, `embed_documents()` / `embed_query()` (768-dim, L2-normalised), and `generate()`, which retries once and then falls back from `gemini-3.5-flash-lite` to `gemini-3.1-flash-lite`, raising `QuotaExceeded` when both fail; models can be overridden with `GEMINI_CHAT_MODELS` / `GEMINI_EMBED_MODEL`.
- `list_models.py`: lists the models the key can use and their supported actions.
- `build_index.py` + `index/`: embeds every chunk with `gemini-embedding-001` into the committed `index/knowledge_index.npz` (vectors, ids, text hashes, model, dimensions); rerun after editing any note.
- `retrieval.py`: `retrieve(question, k)` ranks chunks by cosine similarity against the index, falling back to BM25 keyword scoring when the question cannot be embedded or the index is out of date.

`chatbot/db.py` imports `sql.load_sqlite`, so the repo root must be on `sys.path`. `streamlit run app.py` and `pytest.ini` both take care of this.

## Roadmap

1. Data foundation: views + read-only SQL runner + tests (**done**)
2. Knowledge notes for RAG (markdown, every number checked against SQL) (**done**)
3. Gemini client + embeddings index + retrieval (**done**)
4. Agent: retrieve -> Gemini with run_sql tool -> answer, with guardrails (**next**)
5. Streamlit "Ask the data" page
6. Evaluation set + script + fixes
7. Deploy to Streamlit Community Cloud with secrets, README, screenshots

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
python -m pytest -m live -q           # live Gemini retrieval tests; uses free-tier quota
```
