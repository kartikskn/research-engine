# Research Learning Library

A simple learning library for research papers. You paste arXiv links, Claude writes a structured
study record for each paper, and the app helps you understand, connect and compare them:
search, a concept glossary, and a side-by-side comparison.

> **Work in progress.** This is a student project built one small step at a time. Most features
> are not built yet. See [PLAN.md](PLAN.md) for the plan and [STEP_LOG.md](STEP_LOG.md) for what
> each finished step added.

## Stack
- Python 3.12
- Streamlit for the UI
- SQLite (standard library `sqlite3`) for storage
- pandas and scikit-learn (TF-IDF + cosine similarity) for search
- Pydantic for the paper schema
- Claude API (`anthropic` SDK, model `claude-sonnet-5-5`)
- pytest for tests

## Install
```
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The Claude API key is read from an environment variable (never stored in the repo). It is needed
from build step 4 onwards:
```
export ANTHROPIC_API_KEY=your-key-here
```

## Run
```
streamlit run app/app.py
```

## Test
```
pytest
```
