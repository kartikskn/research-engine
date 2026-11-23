# Research Learning Library

## What this is
A simple learning library: I add research papers from arXiv and it helps me understand,
connect and compare them. A humble student project that I must be able to explain end
to end in an interview.

## Who it's for
Me, and other maths, stats and quant-finance students reading papers for a dissertation
or literature review.

## What it does (v1)
1. Add papers by pasting arXiv links (one per line); processed one by one with a progress
   bar; papers already saved are skipped.
2. Metadata (title, authors, date, category, abstract) from the arXiv API; text from the
   LaTeX source (common cases only).
3. One Claude call per paper creates a study record (Pydantic): plain_summary,
   key_concepts, background, research_question, methods, data, key_results, limitations,
   keywords.
4. Each paper is one row in SQLite.
5. Library: TF-IDF search plus filters (category, year, author); paper page; CSV export.
6. Concept glossary built from stored records (no extra Claude calls).
7. Compare 2–4 papers side by side, plus one Claude call for a short written comparison
   based on the stored records only.

Out of scope for now: chat/Q&A, chunking, quote checking, PDF upload, deployment, accounts.

## Layout
- `app/app.py`: the whole Streamlit UI, using st.tabs (Add, Library, Paper, Glossary,
  Compare) with one small function per tab
- `research_engine/`: models.py, arxiv.py, llm.py, storage.py, library.py, ingest.py
  (no Streamlit code here)
- `tests/`, `scripts/try_paper.py`

## Stack
- Python 3.12
- Streamlit (UI), SQLite via stdlib `sqlite3` (storage), pandas (tables, filters, CSV)
- scikit-learn (TF-IDF + cosine similarity search)
- Pydantic (paper schema), Claude API via the `anthropic` SDK, model `claude-sonnet-5-5`
- pytest (tests only)
No other frameworks or services. Before adding any library or service, explain why it's
needed and what the simpler alternative would be.

## Commands
- Install: `pip install -e ".[dev]"` (inside `.venv`)
- Run app: `streamlit run app/app.py`
- Run tests: `pytest`

## Conventions
- Python only; type hints everywhere; Pydantic models for the paper schema
- Small modules and small functions with clear names
- Tests for parsing, LaTeX handling, storage, search and glossary logic; Claude calls are
  tested with a fake client
- Secrets (API keys) live in environment variables and are never committed

## Rules
- Claude may only use the paper's own text (for study records) or the stored records (for
  comparisons). Prompts tell it to write "Not stated in the paper" rather than guess.
- Each paper page links to the paper on arXiv. The app footer carries one note saying
  records are AI-generated summaries and should be checked against the paper.
- Don't change the StudyRecord schema without asking me first.
- If a Claude API call errors, check the anthropic SDK docs rather than guessing at a fix.
- Handle common cases only; list edge cases under "Known limitations" in PLAN.md.
- Explain any non-obvious design choice in a short comment.
- Follow PLAN.md one step at a time. I'm building this to learn, so after each step stop
  and explain what changed and why before moving on.
- Do one build step at a time. At the end of each step, stop and give me: (1) the files
  created or changed, one line each on what they do, (2) any commands you ran and what they
  did, (3) the exact check command for me to run myself. Don't start the next step until I
  say go.
- Never add a library, file or feature that isn't in PLAN.md without asking me first.
- Don't touch files outside this project folder.
- After each step, add an entry to STEP_LOG.md before asking me to run the check.
- After I confirm a step's check passes, make a git commit named
  "step N: <short description>".
- After each step's commit, push to GitHub.
