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

## Step 2: arXiv links and metadata
**What it built:** The first half of `arxiv.py`: turning pasted text into arXiv ids, and turning an
id into a `PaperMetadata` by asking the arXiv API. A small command-line script lets me try it on a
real paper before any UI exists.

**Code to know:**
- `parse_links(text)`: reads one link per line and returns `(ids, bad_lines)`. A single regex finds
  an id like `2310.01234` in abs links, pdf links or bare ids, and drops any `v2` suffix and
  duplicates. Lines with no id are returned so the Add tab can report them as failed.
- `parse_metadata(xml_text)`: reads one entry from arXiv's Atom (XML) response into a
  `PaperMetadata`. Pure function with no network, so it is easy to test. Raises `ValueError`
  ("paper not found") when there is no entry.
- `fetch_metadata(id)`: builds the API URL, calls `_get`, and passes the XML to `parse_metadata`.
- `_get(url)`: one HTTP GET with `urllib`, a generic User-Agent, a timeout, then a 3 second sleep
  so a batch of papers stays within arXiv's rate limit.
- `scripts/try_paper.py meta <link>`: prints the title, authors, date, category and abstract.
- `tests/fixtures/atom_sample.xml`: a real saved API response, so tests don't need the internet.

**Concepts:**
- **Atom feed / `xml.etree`:** the arXiv API replies with XML. `ElementTree` is in the standard
  library; tags carry a namespace in curly braces (`{http://www.w3.org/2005/Atom}title`).
- **Regular expression lookarounds:** `(?<!\d)` and `(?!\d)` mean "not preceded or followed by a
  digit", so a too-long number such as `2310.012345` is rejected instead of half-matched.
- **Separating network from parsing:** only `_get` touches the internet. Everything else can be
  tested offline with the saved response.

**Design choices:**
- `urllib` from the standard library. Simpler alternative: the `requests` library. `urllib` is
  enough for two GET calls and keeps the dependency list as planned.
- Primary category from `arxiv:primary_category`, not the first `<category>`. The first listed
  category is not always the primary one (the fixture paper shows this), and filters need the
  right one.
- `parse_links` returns bad lines instead of raising. Simpler alternative: raise on the first bad
  line. One bad line shouldn't stop a pasted batch.
- Only new-style ids. Simpler alternative: also parse `math/0601001`. Rare in recent papers, so it
  is listed under known limitations.

**Why it matters (interview):** It shows I wrote code that talks to an external API politely (rate
limit, User-Agent) and tested it without depending on the network.

**Likely interview questions:**
- *How do you avoid hammering arXiv?* Every request is followed by a 3 second sleep, and papers
  are processed one at a time, which matches arXiv's guidance of one request per 3 seconds.
- *How do you test code that calls an API?* I split fetching from parsing and saved a real
  response as a fixture. Tests check the parser on that file and never touch the network.
- *Why not take the metadata from Claude?* arXiv already has it exactly, and the filters on
  category, year and author depend on exact values.
