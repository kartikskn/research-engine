# Step Log

One entry per build step, written for interview preparation.

## Step 0: Setup
**What it built:** The empty skeleton of the project. A Python 3.12 virtual environment with the
five libraries from the plan installed, a `pyproject.toml` that describes the project, and a
Streamlit page with five empty tabs (Add, Library, Paper, Glossary, Compare) and a footer note
saying records are AI-generated.

**Code to know:**
- `pyproject.toml`: lists the project's dependencies (streamlit, pandas, scikit-learn, pydantic,
  openai), plus pytest as a dev-only extra, and tells pytest to look in `tests/`.
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
record (the structured summary the LLM will write for each paper), and a `Paper` that combines
the two. Seven tests check that good data loads, bad data is rejected and everything survives a
round trip to JSON.

**Code to know:**
- `PaperMetadata`: title, authors, date, category and abstract from the arXiv API. Has an
  `arxiv_url` property that builds the link to the paper.
- `KeyConcept`: a term and a plain explanation.
- `StudyRecord`: the schema for the LLM's output: plain summary, key concepts, background,
  research question, methods, data, key results, limitations and keywords.
- `Paper`: metadata + record + the time it was added.
- `tests/test_models.py`: checks valid data, a missing field, a wrong type, JSON round trips,
  the URL property and that field descriptions reach the JSON schema.

**Concepts:**
- **Pydantic `BaseModel`:** a class whose fields have types. Creating an instance validates the
  data and raises `ValidationError` if something is missing or the wrong type.
- **`Field(description=...)`:** text attached to a field. It becomes part of the JSON schema,
  which in step 4 is sent to the LLM, so the descriptions act as instructions.
- **JSON round trip:** `model_dump_json()` turns a model into text and `model_validate_json()`
  rebuilds it. That is how a record will be stored in one SQLite column.

**Design choices:**
- Metadata comes from the arXiv API, not from the LLM. Simpler alternative: ask the LLM for the
  title and authors. The API is exact, and the filters depend on exact values.
- "3 to 6 concepts" is only in the description, not enforced. Simpler alternative:
  `min_length`/`max_length`. A hard limit would make a whole paper fail if the LLM returned 7.
  This is listed as a known limitation.
- Lists for methods, results and limitations; plain strings for data and research question.
  Simpler alternative: strings everywhere. Lists display as bullets and compare well side by side.

**Why it matters (interview):** It shows I define the data contract first and validate it, rather
than passing loose dictionaries around. That makes the LLM output checkable.

**Likely interview questions:**
- *Why Pydantic instead of a dict or a dataclass?* It validates types when the object is created,
  and it generates the JSON schema I give to the LLM. A dict does neither, and a dataclass only
  does the typing.
- *What happens if the LLM returns something that doesn't fit the schema?* Validation fails with
  an error. The paper is reported as failed in the Add tab and the rest of the batch continues.
- *Why does the metadata not come from the LLM?* arXiv already has the exact title, authors and
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
- *Why not take the metadata from the LLM?* arXiv already has it exactly, and the filters on
  category, year and author depend on exact values.

## Change of plan: OpenAI instead of Claude
**What changed:** The app now calls the OpenAI API (`openai` SDK, model `gpt-6-luna`) instead of the
Claude API, because I have OpenAI credits. Nothing built in steps 0-2 depended on the old choice
except the dependency list and some wording, so only `pyproject.toml`, PLAN.md and CLAUDE.md changed.

**Why `gpt-6-luna`:** OpenAI's docs call it their most efficient model for focused, high-volume
tasks. It costs $0.10 per 1M input tokens and $0.50 per 1M output tokens (about 20x cheaper than the
mid-tier `gpt-6.2-sol` at $2 / $10), has a 1M-token context window so a whole paper fits, and lists
Structured Outputs among its features. A tiny test call parsed straight into a Pydantic model.
**Simpler alternative:** `gpt-6.2-sol`, a bit smarter but ~20x the price. Because the model name is one
constant in `llm.py`, switching later is a one-line change if the records turn out too weak.

**Concepts:** The SDK's `client.responses.parse(..., text_format=StudyRecord)` does the same job as
Claude's structured outputs: the reply is constrained to the Pydantic schema and arrives validated as
`response.output_parsed`. Token usage is `response.usage.input_tokens` / `output_tokens`.

## Step 3: LaTeX source and flattening
**What it built:** The second half of `arxiv.py`: downloading a paper's LaTeX source and turning it into one
clean string containing just the paper body. On a real paper (2611.27274) it produced about 62,000
characters, roughly 6,700 words, starting at the abstract and ending before the bibliography.

**Code to know:**
- `fetch_source(id)`: downloads `arxiv.org/e-print/<id>` and returns raw bytes (`_get` now returns bytes;
  `fetch_metadata` decodes them to text).
- `flatten_source(raw)`: the whole pipeline in four lines: read files, strip comments, find the main
  file and inline its `\input`s, keep the body.
- `_read_tex_files`: un-gzips, rejects PDFs, then reads `.tex` files from the tar into a dict, in memory.
- `_find_main_file`: the file containing `\documentclass` (longest one if several).
- `_inline_inputs`: replaces `\input{x}` / `\include{x}` with `x.tex`'s text, recursively; missing is empty.
- `_keep_body`: keeps text between `\begin{document}` and `\end{document}`, cut at the bibliography.
- `tests/conftest.py`: fixtures that build fake downloads (gzipped file, tar.gz) in memory.
- `scripts/try_paper.py source <link>`: prints body size and the first 1,500 characters.

**Concepts:**
- **Magic bytes:** gzip files start with `\x1f\x8b` and PDFs with `%PDF`, so we can tell what was downloaded
  by looking at its first bytes instead of trusting a file name.
- **`tarfile` in memory:** `tarfile.open(fileobj=io.BytesIO(raw))` reads an archive without writing files, so a
  hostile archive can't write outside our folder.
- **Regex substitution with a function:** `re.sub(pattern, fn, text)` calls `fn` for each match. `_inline_inputs`
  uses that, and `fn` calls `_inline_inputs` again, which handles nested `\input`s.

**Design choices:**
- Read everything in memory. Simpler alternative: extract to a temp folder. In memory is shorter and safer.
- Remove comments before inlining. Otherwise a commented-out `\input` or old text would reach the LLM.
- No section splitting at all (chunking is out of scope): the LLM reads the whole body.
- Known limitations: no macro expansion, appendices placed after the bibliography are cut, a `%` inside
  verbatim code is treated as a comment, files that include themselves would loop forever.

**Why it matters (interview):** It shows I handled messy real-world input (several archive layouts) with a few
small, individually tested functions rather than one big parser.

**Likely interview questions:**
- *Why not use a LaTeX parsing library?* The LLM reads LaTeX fine. All I need is the body text with comments
  gone and the files joined, which is four small regex steps. A parser would be a new dependency to explain.
- *What if the paper has no LaTeX source?* Some papers only upload a PDF. We detect `%PDF` and raise a clear
  error, and the Add tab will show that paper as failed. PDF upload is out of scope for v1.
- *Why read the tar in memory?* Archives come from the internet, so I don't want to extract files from them to
  disk. Reading members into strings avoids path tricks entirely.

## Step 4: The study record (first LLM call)
**What it built:** `llm.make_study_record()`, which sends one paper to the model and gets back a validated
`StudyRecord`, plus the token counts. `try_paper.py record <link>` runs it on a real paper. On paper
2611.27274 it returned a sensible record (5 concepts, 6 methods, 6 results) for 18,167 input and
1,576 output tokens, about $0.0026, in roughly 20 seconds.

**Code to know:**
- `MODEL = "gpt-6-luna"`: the single constant that names the model. `MAX_OUTPUT_TOKENS = 16000`.
- `RECORD_INSTRUCTIONS`: the system prompt. Use only the paper, write "Not stated in the paper" rather than
  guess, explain plainly.
- `make_study_record(metadata, latex_text, client)`: builds the prompt (title, authors, abstract, then the body
  inside `<paper>` tags), calls `client.responses.parse(...)`, checks the status, and returns
  `(record, input_tokens, output_tokens)`.
- `tests/test_llm.py`: a `FakeClient` that records the call and returns a canned response, so the tests check the
  prompt, the model constant, the schema, and the two failure cases without the network.

**Concepts:**
- **Structured outputs:** `text_format=StudyRecord` makes the API constrain the reply to that Pydantic model's JSON
  schema, so `response.output_parsed` is already a valid `StudyRecord`. No manual JSON parsing.
- **Reasoning tokens:** the model thinks before answering and those tokens are billed as output and count
  against `max_output_tokens`, so the limit is set high (16,000) to avoid cutting off a long paper.
- **Dependency injection:** the client is a parameter, not created inside the function. Tests pass a fake;
  the app passes the real `OpenAI()`.

**Design choices:**
- Send the whole paper body. Simpler alternative: only the abstract. The abstract doesn't state methods, data or
  limitations, and the full paper costs a fraction of a cent on this model.
- Return a plain tuple `(record, tokens_in, tokens_out)`. Simpler alternative: a custom result class. A tuple is
  enough for three values used in one place.
- Raise `ValueError` for an unfinished or refused response; the Add tab will show it as "failed".
- Default reasoning effort, no `temperature`. Simpler alternative: tune both. Not needed yet.

**Why it matters (interview):** It shows I can get reliable, typed data out of an LLM (schema-constrained output,
checked status) and test that code without paying for or depending on the API.

**Likely interview questions:**
- *How do you stop the model inventing things?* The prompt says to use only the paper text and write "Not stated
  in the paper" otherwise, and the app footer tells users to check records against the paper. I also spot-check
  10 records by hand at the end and count mistakes.
- *Why is the OpenAI client passed in?* So tests can pass a fake client and run offline, instantly and for free.
- *What does structured output give you over asking for JSON?* The schema is enforced by the API, so I always
  get a valid `StudyRecord` or a clear failure, never half-valid JSON I have to repair.

## Step 5: SQLite storage
**What it built:** `storage.py`: one SQLite table with one row per paper, and the five functions the rest of the app
needs. `try_paper.py add <link>` now fetches a paper, makes its record and saves it; running it a second time
says "already saved" without calling the LLM. A real paper is now in `data/library.db` (git-ignored).

**Code to know:**
- `connect(path=None)`: opens the database (path from `LIBRARY_DB`, default `data/library.db`), creates the folder and
  the `papers` table if needed, and returns the connection.
- `paper_exists(db, id)`: a one-line `SELECT 1` lookup, used to skip papers already saved.
- `save_paper(db, paper, latex_text, model, tokens_in, tokens_out)`: one `INSERT`. The record is stored as one JSON column.
- `load_paper(db, id)`: rebuilds a `Paper` (metadata + `StudyRecord`) from a row.
- `load_library(db)`: the whole table as a pandas DataFrame, newest first, with `authors` as lists, `record` as
  `StudyRecord` objects, and a `year` column, so later steps can filter and search with plain pandas.
- `tests/test_storage.py`: round trip, exists, duplicate refused, newest-first order, empty library, env var path.

**Concepts:**
- **`sqlite3` (standard library):** a database in one file. `?` placeholders pass values safely (no string-built SQL).
  The `PRIMARY KEY` on `arxiv_id` makes duplicates impossible even if the code forgets to check.
- **JSON in a column:** the record is saved with `model_dump_json()` and read back with `model_validate_json()`, so
  Pydantic does the conversion both ways.
- **`pd.read_sql`:** runs a query and returns a DataFrame; I then convert the JSON columns into Python objects.

**Design choices:**
- One table with the record as JSON. Simpler alternative: one column per record field. Nothing queries inside the
  record, and JSON round-trips through Pydantic in one call.
- Keep `latex_text` in the row. Simpler alternative: don't store it. It lets me redo a record without re-downloading.
- Store token counts and the model name. Simpler alternative: skip them. They let me see what each paper cost.
- Filtering happens in pandas, not SQL `WHERE`. The library is small and I know pandas.
- Known limitation: no way to delete or edit a paper from the app.

**Why it matters (interview):** It shows I can design a small schema, use parameterised SQL, and keep
persistence separate from the rest of the logic so it is testable with a temporary database.

**Likely interview questions:**
- *Why SQLite?* It is a single file, needs no server, ships with Python, and a personal library is tiny. If real users
  arrive I can move the same table to a hosted database.
- *Why store the record as JSON instead of columns?* I never query inside it in SQL; pandas does the searching. JSON
  keeps the schema in one place (the Pydantic model), so adding a field doesn't need a table change.
- *How do you prevent duplicates?* `arxiv_id` (without the version) is the primary key, and the add flow checks
  `paper_exists` first so the user sees "skipped" instead of an error.

## Step 6: Adding papers (ingest + Add tab)
**What it built:** The loop that turns pasted links into saved papers, and the Add tab that drives it. Paste links
one per line, press the button, watch a progress bar, and get a results table showing which papers were added,
skipped (already saved) or failed (and why). A live run with a four-line paste added two new papers (about $0.0055
and $0.0036), skipped the duplicate and reported the junk line.

**Code to know:**
- `ingest.IngestResult`: a tiny dataclass: the id, a status (`added` / `skipped` / `failed`) and a message.
- `ingest.add_papers(ids, client, db, on_progress)`: loops over the ids one at a time, calling `on_progress` before each
  paper and once at the end, and returns the list of results.
- `ingest._add_one`: skip if the id exists; otherwise fetch metadata, fetch and flatten the source, make the record, save.
  Any exception becomes a `failed` result, so one bad paper never stops the batch.
- `app.add_tab(db)`: text area, button, `st.progress` bar and results table. It creates the `OpenAI()` client only when
  the button is pressed, so the app still opens without an API key and shows a clear error instead.
- `tests/test_ingest.py`: fakes the network and the LLM with `monkeypatch`, and checks a batch with an added, a skipped and
  two failed papers (not found, PDF-only), progress callbacks, and what gets saved.

**Concepts:**
- **Callback:** `on_progress` is a function passed in. `ingest.py` knows nothing about Streamlit; the Add tab passes a
  function that moves the bar. That keeps the loop testable.
- **`monkeypatch`:** a pytest fixture that swaps a function for a fake during one test, then restores it.
- **`st.text_area`, `st.button`, `st.progress`, `st.dataframe`:** a widget returns its current value on each rerun;
  `st.button` is `True` only on the rerun right after the click.

**Design choices:**
- Catch `Exception` per paper. Simpler alternative: stop on the first error. For a batch, partial success with a
  clear report is more useful, and this is the one place a broad catch is right.
- One paper at a time. Simpler alternative: parallel requests. Sequential respects arXiv's rate limit and is easier to follow.
- Lines with no arXiv id are reported by the tab, not by `add_papers`, which only receives valid ids.
- Known limitation: results are shown only for the rerun right after the click; refreshing the page clears the table.

**Why it matters (interview):** It shows I keep orchestration logic separate from the UI and make failures visible instead of
swallowing them, so a batch of 20 papers is safe to run.

**Likely interview questions:**
- *What happens if one paper in a batch fails?* It is recorded as `failed` with the reason, and the loop moves on. The user
  sees the whole batch's outcome in one table.
- *How do you test a loop that calls the network and an LLM?* I replace those calls with fakes using `monkeypatch`, so the
  test checks the loop's logic (skip, fail, continue, save) and runs in under a second.
- *Why a callback for progress instead of using Streamlit inside the loop?* So the loop has no Streamlit dependency and can
  be tested and reused from a script. The UI just hands it a function.

## Step 7: Paper tab and `render_record`
**What it built:** The Paper tab: pick a saved paper from a dropdown and read its study record. The page shows the title,
authors, date, category and a link to the paper on arXiv, then the plain summary first, key concepts, background, and the
detailed record (research question, methods, data, results, limitations, keywords) inside an expander. I checked it headlessly
against all three real saved papers and an empty library.

**Code to know:**
- `render_record(paper, open_details=False)`: the one function that draws a paper. The Compare tab will reuse it.
- `bullets(items)`: turns a list of strings into a markdown bullet list.
- `paper_tab(db, df)`: shows "No papers yet" for an empty library; otherwise a `selectbox` of titles, then
  `storage.load_paper` and `render_record`.
- `main()` now loads the library DataFrame once, right after the Add tab runs, so a paper added in this same click
  appears in the dropdown immediately.

**Concepts:**
- **`st.selectbox` with `format_func`:** the options are the arXiv ids (stable values) and `format_func` turns each into
  a readable label with the title.
- **`st.expander`:** a collapsible section. `expanded=True` opens it; Compare will use that.
- **Markdown math:** `st.markdown` renders `$...$` as maths, so formulas the LLM writes display properly.
- **Headless UI testing (`AppTest`):** Streamlit can run the app script without a browser, set widget values and
  inspect what was drawn. I use it for my own checks; it is not part of the committed test suite.

**Design choices:**
- Read the full `Paper` from the database with `load_paper` instead of building it from a DataFrame row. Simpler
  alternative: convert the row. A query by id is one line and already tested.
- Show at most six authors then "et al." so a large collaboration doesn't fill the page.
- The Library can't jump to this tab (`st.tabs` can't be switched from code), so you pick the paper here. Known limitation.

**Why it matters (interview):** It shows I turned structured data into a readable page, putting the most useful part (the
plain summary) first, and reused one rendering function rather than copying it.

**Likely interview questions:**
- *Why does the page put the plain summary first?* The app is for learning. A student wants the gist before the details,
  and the detailed record is one click away.
- *How do you test a Streamlit page without a browser?* `AppTest` runs the script headlessly and lets me read the widgets
  and text it produced. The real logic lives in `research_engine/`, which has normal pytest tests.
- *Why is the app's data loaded after the Add tab?* The script runs top to bottom on every click. If I loaded the library
  first, a paper added in this click wouldn't show until the next rerun.

## Step 8: Library tab (filters, search, CSV)
**What it built:** `library.py`, three pure functions on the library DataFrame, and the Library tab that uses them: filters by
category, year and author, a TF-IDF search box ranked by cosine similarity, a results table, and a "Download CSV" button.
Checked headlessly on the real library: searching "volatility forecasting" returned the two volatility papers, and the
category and author filters narrowed the list correctly.

**Code to know:**
- `apply_filters(df, categories, year_range, author)`: pandas boolean filters. An empty filter keeps everything; the author
  filter is a case-insensitive substring match against any author.
- `search_text(row)`: the text we index per paper: title, abstract, plain summary, concept terms, keywords and methods
  (clean prose from the record, not the raw LaTeX).
- `search(df, query)`: fits `TfidfVectorizer(stop_words="english", sublinear_tf=True)` on those texts, scores the query by
  `cosine_similarity`, drops zero scores and sorts best first. An empty query returns everything, newest first.
- `to_csv_frame(df)`: flattens each record into one row of text (lists joined with `; `, concepts as `term: explanation | ...`).
- `app.library_tab(df)`: filter widgets, search box, table and `st.download_button`. The CSV is of the current results.
- `tests/conftest.py`: a `paper_factory` fixture and a `library_df` fixture (three papers saved to and loaded from an
  in-memory SQLite database). `tests/test_library.py` has 15 tests.

**Concepts:**
- **TF-IDF:** each word is weighted by how often it appears in a paper (term frequency) and how rare it is across the library
  (inverse document frequency), so distinctive words like "cointegration" count more than common ones.
- **Cosine similarity:** the angle between the query's vector and each paper's vector; 1 means the same direction, 0 means no
  shared words. `sublinear_tf=True` uses `1 + log(tf)` so a word repeated 20 times doesn't swamp the score.
- **`st.columns`, `st.multiselect`, `st.slider`, `st.download_button`:** layout and widgets; the download button gets the CSV text.

**Design choices:**
- Search the record text, not the LaTeX. Simpler alternative: index the full paper. The records are clean prose, so the index
  is small and the matches are meaningful.
- Refit the TF-IDF index on every search. Simpler alternative: cache it. It takes milliseconds, and nothing can go stale.
- Search runs after the filters, so the vocabulary and scores only involve papers still in play.
- The year slider is hidden when every paper is from the same year (a slider needs a range).
- Known limitations: a search made only of stop words matches nothing; search is on words, not meaning (no synonyms).

**Why it matters (interview):** It shows I can apply familiar tools (pandas, scikit-learn) to a real feature and keep the logic in
pure, tested functions with the UI as a thin layer.

**Likely interview questions:**
- *How does the search work?* I build a text per paper from its record, fit a TF-IDF vectorizer over the library, turn the query
  into the same kind of vector and rank papers by cosine similarity, dropping the ones with a score of zero.
- *Why TF-IDF rather than embeddings?* The library is small, TF-IDF is free, instant and explainable, and technical terms like
  "GARCH" are exactly the sort of distinctive words it handles well. Embeddings would add a service and cost.
- *Why refit the vectorizer on each search?* For tens or hundreds of papers it's milliseconds, so I avoid cache invalidation bugs.

## Step 9: Glossary tab
**What it built:** A page listing every key concept across the library, A to Z, each with the explanation from every paper that
uses it (and which paper). A text box filters the list. It is built entirely from the stored records, so it makes no LLM calls.
On the three real papers it lists 18 concepts.

**Code to know:**
- `normalise_term(term)`: lower-cases (using `casefold`) and collapses whitespace, so "Realised  Volatility" and "realised volatility"
  are the same key.
- `build_glossary(df)`: loops over the papers and their key concepts, collects them in a dict keyed by the normalised term, and
  returns a sorted list of `{"term": ..., "papers": [{arxiv_id, title, explanation}, ...]}`.
- `app.glossary_tab(df)`: a text filter and one heading per term with a bullet per paper.
- Tests: concepts come out A to Z, the same concept in two papers becomes one entry listing both, empty library, normalisation.

**Concepts:**
- **`dict.setdefault`:** returns the existing value for a key, or inserts a default and returns that. It lets me "add to the
  entry for this term, creating it if needed" in one line.
- **`str.casefold`:** a stronger, language-aware `lower()` for case-insensitive comparison.

**Design choices:**
- Compute the glossary on the fly. Simpler alternative: a separate `concepts` table. There is nothing to keep in sync and
  adding or deleting a paper needs no extra code.
- Return plain lists and dicts rather than a DataFrame: it is a nested structure (a term has many papers), which a flat table
  represents awkwardly.
- Keep each paper's own explanation instead of merging them, so you can compare how different papers describe the same idea.
- Known limitation: different spellings of one idea ("GARCH" vs "GARCH(1,1)") stay separate entries.

**Why it matters (interview):** It shows a feature built from data the app already stores (no extra cost or service), with the
grouping logic in a small tested function.

**Likely interview questions:**
- *How do you group the same concept across papers?* I normalise each term (casefold and collapse whitespace) and use it as a
  dictionary key; papers whose terms normalise to the same key land in the same entry.
- *Why not ask the LLM to build the glossary?* Every record already has the concepts and explanations, so reading them is free
  and instant, and it never contradicts what the Paper tab shows.
- *What are the weaknesses?* It only merges exact matches after normalisation, so near-synonyms stay separate; a fuzzy match or an
  LLM merge step would fix that but add complexity and cost.

## Step 10: Compare tab
**What it built:** Pick 2 to 4 saved papers and see their records side by side, then press "Write comparison" to get a short
written comparison (about 300 words: shared ideas, methods and data, results, which to read first). The comparison is written
from the stored records only, never the paper text. A live run on two real papers cost about $0.0006 (3,225 tokens in, 609 out).

**Code to know:**
- `llm.COMPARISON_INSTRUCTIONS`: the prompt: use only these records, say so if the records don't say, four headings, about 300 words.
- `llm.write_comparison(papers, client)`: builds one text from each paper's title, id, year and record JSON, makes a plain
  `client.responses.create(...)` call, raises if the reply is unfinished, and returns `response.output_text`.
- `app.compare_tab(db, df)`: a `multiselect` limited to 4, one `st.columns` column per paper using `render_record(open_details=True)`,
  and the button. The OpenAI client is created only when the button is pressed.
- Two new tests: the prompt contains the records (and not even the abstract) and the call is not structured; an unfinished reply raises.

**Concepts:**
- **`st.session_state`:** a dictionary that survives reruns. Because every click reruns the script, the comparison text is kept there;
  otherwise it would vanish the moment you touched another widget.
- **`st.columns`:** lays out widgets side by side; `with column:` puts the following calls inside that column.
- **Plain vs structured replies:** the record needs a rigid schema (`responses.parse`); the comparison is free text
  (`responses.create` and `output_text`), so there is no schema.

**Design choices:**
- Send records, not paper text. Simpler alternative: send the LaTeX of every paper. Records are short and the call is ~100x cheaper
  (cents become fractions of a cent), and it keeps the comparison grounded in what the Paper tab already shows.
- Not stored in the database. Simpler alternative: a `comparisons` table. One fewer table; pressing the button again regenerates it for a
  fraction of a cent.
- The saved comparison remembers which papers it was for, and is only shown while that same selection is chosen.
- Show errors from the call in the page (`st.error`) rather than a traceback.
- Known limitation: the comparison is only as good as the records, and the model can stretch to find "shared ideas" between unrelated
  papers (my live test did this a little).

**Why it matters (interview):** It shows I can keep a second LLM feature cheap and grounded by feeding it structured data I already
have, and handle Streamlit's rerun model with `session_state`.

**Likely interview questions:**
- *Why compare from records instead of the full papers?* It's far cheaper and faster, and the records already hold the methods, data and
  results. It also keeps the comparison consistent with what the user has read in the app.
- *How do you stop the comparison inventing things?* The prompt says to use only the supplied records and to say when they don't contain
  something. It can still over-interpret, so the footer asks users to check against the papers.
- *Why does the comparison disappear when I change the selection?* It's stored with the list of papers it was written for; if the selection
  differs, showing it would be misleading.
