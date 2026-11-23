# Step Log

One entry per build step, written for interview preparation.

## Step 0: Setup
**What it built:** The empty skeleton of the project. A Python 3.12 virtual environment with the
five libraries from the plan installed, a `pyproject.toml` that describes the project, and a
Streamlit page with five empty tabs (Add, Library, Paper, Glossary, Compare) and a footer note
saying records are AI-generated.

**Code to know:**
- `pyproject.toml`: lists the project's dependencies (streamlit, pandas, scikit-learn, pydantic,
  anthropic), plus pytest as a dev-only extra, and tells pytest to look in `tests/`.
- `.gitignore`: keeps the virtual environment, the database folder, caches and build leftovers
  out of git.
- `research_engine/__init__.py`: an empty file that makes `research_engine/` a Python package,
  so the rest of the code can be imported from anywhere.
- `app/app.py`: the whole UI. `main()` sets up the page and tabs and calls one small function per
  tab; each function is a placeholder for now.

**Concepts:**
- **Virtual environment:** a private copy of Python and its packages inside `.venv/`, so this
  project's libraries don't mix with other projects or the system Python.
- **Editable install (`pip install -e`):** instead of copying the code into the environment, pip
  links to it. Edits apply immediately and `import research_engine` works from the app, the tests
  and scripts.
- **Streamlit reruns:** Streamlit runs the script top to bottom on every click. `st.tabs` only
  changes layout, so every tab's code runs on every rerun.

**Design choices:**
- Package `research_engine/` separate from `app/`, installed editably. Simpler alternative:
  everything inside `app/`. `streamlit run` only puts `app/` on the import path, so tests and
  scripts would need path hacks.
- One `app.py` with `st.tabs`. Simpler alternative: a multipage app. One file is easier to read
  and the footer and setup are written once.
- Dependencies left unpinned for now. Simpler alternative: pin exact versions. I'd pin them only
  if a version change breaks something.

**Why it matters (interview):** It shows I set up a project properly (isolated environment,
declared dependencies, importable package) before writing features, so anyone can reproduce it.

**Likely interview questions:**
- *Why a virtual environment?* So this project's libraries are isolated from every other project.
  I can delete `.venv/` and rebuild it from `pyproject.toml` at any time.
- *Why keep the logic out of the Streamlit file?* Streamlit code is awkward to test. Plain
  functions in `research_engine/` can be tested with pytest, and the UI stays thin.
- *What does `pip install -e` do?* It links the project into the environment rather than copying
  it, so edits take effect right away and imports work everywhere.

## Step 1: Pydantic models
**What it built:** The data shapes the whole app uses: the paper's metadata from arXiv, a study
record (the structured summary Claude will write for each paper), and a `Paper` that combines
the two. Seven tests check that good data loads, bad data is rejected and everything survives a
round trip to JSON.

**Code to know:**
- `PaperMetadata`: title, authors, date, category and abstract from the arXiv API. Has an
  `arxiv_url` property that builds the link to the paper.
- `KeyConcept`: a term and a plain explanation.
- `StudyRecord`: the schema for Claude's output: plain summary, key concepts, background,
  research question, methods, data, key results, limitations and keywords.
- `Paper`: metadata + record + the time it was added.
- `tests/test_models.py`: checks valid data, a missing field, a wrong type, JSON round trips,
  the URL property and that field descriptions reach the JSON schema.

**Concepts:**
- **Pydantic `BaseModel`:** a class whose fields have types. Creating an instance validates the
  data and raises `ValidationError` if something is missing or the wrong type.
- **`Field(description=...)`:** text attached to a field. It becomes part of the JSON schema,
  which in step 4 is sent to Claude, so the descriptions act as instructions.
- **JSON round trip:** `model_dump_json()` turns a model into text and `model_validate_json()`
  rebuilds it. That is how a record will be stored in one SQLite column.

**Design choices:**
- Metadata comes from the arXiv API, not from Claude. Simpler alternative: ask Claude for the
  title and authors. The API is exact, and the filters depend on exact values.
- "3 to 6 concepts" is only in the description, not enforced. Simpler alternative:
  `min_length`/`max_length`. A hard limit would make a whole paper fail if Claude returned 7.
  This is listed as a known limitation.
- Lists for methods, results and limitations; plain strings for data and research question.
  Simpler alternative: strings everywhere. Lists display as bullets and compare well side by side.

**Why it matters (interview):** It shows I define the data contract first and validate it, rather
than passing loose dictionaries around. That makes the Claude output checkable.

**Likely interview questions:**
- *Why Pydantic instead of a dict or a dataclass?* It validates types when the object is created,
  and it generates the JSON schema I give to Claude. A dict does neither, and a dataclass only
  does the typing.
- *What happens if Claude returns something that doesn't fit the schema?* Validation fails with
  an error. The paper is reported as failed in the Add tab and the rest of the batch continues.
- *Why does the metadata not come from Claude?* arXiv already has the exact title, authors and
  date. Asking a model risks invented details, and the filters need exact values.
