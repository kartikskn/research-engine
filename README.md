# Research Learning Library

A simple learning library for research papers. You paste arXiv links, an LLM writes a structured
**study record** for each paper, and the app helps you understand, connect and compare them.

It's a student project built one small step at a time (see [PLAN.md](PLAN.md) for the plan and
[STEP_LOG.md](STEP_LOG.md) for what each step added and why).

## What it does
- **Add:** paste arXiv links, one per line. Papers are processed one at a time with a progress bar;
  papers already saved are skipped, and a paper that fails is reported without stopping the rest.
  Metadata (title, authors, date, category, abstract) comes from the arXiv API and the text from the
  paper's LaTeX source.
- **Study record:** one LLM call per paper produces a plain-language summary, 3-6 key concepts with
  explanations, the background you need first, the research question, methods, data, key results,
  limitations and keywords. Each paper is one row in SQLite.
- **Library:** TF-IDF search (scikit-learn) with filters for category, year and author, and a CSV export.
- **Paper:** the plain summary first, then key concepts, background and the detailed record, with a link to arXiv.
- **Glossary:** every key concept across your library with each paper's explanation (built from the stored
  records; no extra LLM calls).
- **Compare:** pick 2-4 papers to see their records side by side, and make one LLM call for a short written
  comparison based on the stored records only.

Records are AI-generated summaries. Always check them against the paper.

## Stack
- Python 3.12
- Streamlit for the UI
- SQLite (standard library `sqlite3`) for storage
- pandas and scikit-learn (TF-IDF + cosine similarity) for tables and search
- Pydantic for the study record schema
- OpenAI API (`openai` SDK), model `gpt-6-luna` (one constant in `research_engine/llm.py`)
- pytest for tests

## Install
```
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The API key is read from an environment variable and is never stored in the repo:
```
export OPENAI_API_KEY=your-key-here
```

## Run
```
streamlit run app/app.py
```
The database is created at `data/library.db` (set `LIBRARY_DB` to use another path).
A study record costs roughly $0.003-0.006 per paper on `gpt-6-luna`.

## Try the pieces from the command line
```
python scripts/try_paper.py meta   2611.27274    # fetch metadata
python scripts/try_paper.py source 2611.27274    # fetch and flatten the LaTeX
python scripts/try_paper.py record 2611.27274    # make a record and print it (one LLM call)
python scripts/try_paper.py add    2611.27274    # make a record and save it
```

## Test
```
pytest
```
The tests need no network or API key; the LLM and arXiv are replaced with fakes.

## Known limitations
- Only new-style arXiv ids (`2310.01234`); old ids like `math/0601001` aren't parsed.
- PDF-only papers (no LaTeX source) are reported as failed; there is no PDF upload.
- LaTeX handling is basic: custom macros stay unexpanded, missing `\input` files are skipped, and anything after
  the bibliography (such as appendices placed there) is cut.
- Very long papers are sent to the model whole (no truncation), so they cost more.
- Paper ids are stored without the version, so a newer version of a saved paper isn't re-fetched.
- "3 to 6 key concepts" is requested, not enforced.
- The glossary doesn't merge different spellings of one concept (e.g. "GARCH" vs "GARCH(1,1)").
- Search matches words, not meaning; a query made only of common words matches nothing.
- The Library tab can't jump to the Paper tab (`st.tabs` can't be switched from code).
- Papers can't be edited or deleted in the app, and comparisons aren't saved.
- The comparison only sees the records, and can over-link unrelated papers.
- Records can contain mistakes. They haven't been systematically checked yet (a hand spot-check of 10 records
  is planned; see PLAN.md).
- Out of scope for now: chat/Q&A, chunking, quote checking, PDF upload, deployment and accounts.
