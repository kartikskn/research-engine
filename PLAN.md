# PLAN.md: Research Learning Library, v1

## Goal
A simple learning library. I add research papers from arXiv, and it helps me understand,
connect and compare them. Each paper gets one AI-written **study record**. The app then lets me
search the library, read a paper's record, browse a glossary of concepts across papers, and
compare 2–4 papers.

**Out of scope:** chat/Q&A, chunking, quote checking, PDF upload, deployment, accounts.

**Agreed decisions:**
- Model `claude-sonnet-5-5`.
- Claude uses only the paper's own text (for records) or stored records (for comparisons), and
  writes "Not stated in the paper" rather than guessing.
- Each paper page links to arXiv.
- One footer note says records are AI-generated and should be checked against the paper.
- No beta refusal fallback: a declined paper shows "failed" in the progress table and the batch
  carries on.
- One Streamlit file with tabs.

Steps marked **Learn:** are where you'll meet Streamlit, Pydantic or the Claude API for the first time.

---

## 1. Data flow

```
ADD PAPERS (one link per line)
  text box ──► arxiv.parse_links ──► ["2310.01234", "2401.05678", ...]   (versions stripped)
  for each id (st.progress bar, one at a time):
    storage.paper_exists? ── yes ──► "skipped (already saved)"
    arxiv.fetch_metadata  ──► PaperMetadata        (arXiv Atom API)
    arxiv.fetch_source    ──► bytes                (arxiv.org/e-print/<id>)
    arxiv.flatten_source  ──► one LaTeX string (body only)
    llm.make_study_record ──► StudyRecord          (ONE Claude call, structured output)
    storage.save_paper    ──► one row in SQLite
    any error ──► "failed: <reason>", carry on with the next link

USE THE LIBRARY (no Claude calls)
  storage.load_library ──► pandas DataFrame (one row per paper)
    ├─ library.apply_filters (category, year range, author) ─► library.search (TF-IDF) ─► results ─► CSV export
    ├─ Paper tab: plain summary → key concepts → background → detailed record → arXiv link
    └─ library.build_glossary ─► term → explanation(s) + papers that use it

COMPARE
  pick 2–4 papers ─► records side by side (st.columns)
  button ─► llm.write_comparison(stored records only) ─► short markdown text (ONE Claude call, not stored)
```

| Choice | Simpler alternative | Why this one |
|---|---|---|
| Send Claude the whole LaTeX body | Send only the abstract (much cheaper) | The abstract rarely states methods, data or limitations. The whole paper costs ~$0.10 on Sonnet 5.5, once per paper |
| One paper at a time, with a progress bar | Run in parallel | Easy to follow and debug. arXiv asks for ≤1 request per 3 s anyway |
| `ingest.add_papers(ids, on_progress)` callback | Put the loop inside the Add tab | The loop can be tested without Streamlit. The tab just passes a function that moves the bar |

---

## 2. Folder layout

```
research-engine/
├── CLAUDE.md, PLAN.md
├── pyproject.toml            # dependencies + pytest config; `pip install -e ".[dev]"` makes research_engine importable
├── .gitignore                # .venv/, data/, __pycache__/
├── app/
│   └── app.py                # the whole UI: st.tabs + one small function per tab, render_record(), footer note
├── research_engine/
│   ├── models.py             # Pydantic models: PaperMetadata, KeyConcept, StudyRecord, Paper
│   ├── arxiv.py              # parse links → ids; fetch metadata + source; flatten LaTeX source to one body string
│   ├── llm.py                # make_study_record() and write_comparison(); prompts as constants
│   ├── storage.py            # SQLite: create table, paper_exists, save_paper, load_paper, load_library
│   ├── library.py            # pandas + scikit-learn: filters, TF-IDF search, glossary, CSV frame
│   └── ingest.py             # add_papers(): the per-paper loop with skip/fail handling
├── scripts/
│   └── try_paper.py          # CLI for checking steps before the UI exists: meta / source / record / add
├── tests/
│   ├── conftest.py           # builds small fake arXiv tarballs in memory + a sample library DataFrame
│   ├── fixtures/atom_sample.xml
│   └── test_models.py, test_arxiv.py, test_llm.py, test_storage.py, test_ingest.py, test_library.py
└── data/library.db           # created at runtime, gitignored
```

`app/app.py` outline:
```python
def render_record(paper: Paper) -> None: ...    # used by the Paper and Compare tabs
def add_tab(db, client) -> None: ...
def library_tab(df) -> None: ...
def paper_tab(df) -> None: ...
def glossary_tab(df) -> None: ...
def compare_tab(df, client) -> None: ...

def main() -> None:
    st.set_page_config(page_title="Research Library", layout="wide")
    db, client = open_db(), anthropic.Anthropic()
    add, lib, paper, gloss, comp = st.tabs(["Add", "Library", "Paper", "Glossary", "Compare"])
    with add:   add_tab(db, client)
    df = storage.load_library(db)               # loaded after Add, so new papers show up at once
    with lib:   library_tab(df)
    ...
    st.caption("Records are AI-generated summaries. Check them against the paper.")
```

| Choice | Simpler alternative | Why this one |
|---|---|---|
| One `app.py` with `st.tabs` | A multipage app (`pages/` folder or `st.navigation`) | One file to read, and the footer and setup are written once. With tabs, every tab's code runs on every rerun, which is fine because the only expensive call is behind a button |
| `arxiv.py` holds fetching *and* LaTeX flattening | Two modules | Both are "turn an arXiv id into text". Together they're ~80 lines, which is still one small module |
| Separate `research_engine/` (no Streamlit inside) | Logic in `app.py` | Logic outside the UI is testable with plain pytest |
| `research_engine/` package + editable install | Everything inside `app/` | `streamlit run app/app.py` only puts `app/` on the import path. One install command lets pytest, the script and the app all import the same code |

**Dependencies:** `streamlit`, `pandas`, `scikit-learn`, `pydantic`, `anthropic` (the official
Claude SDK). Dev only: `pytest`.
- Why pytest, when the stdlib's `unittest` is the simpler alternative? Tests are plain functions
  with `assert`, and `tmp_path` gives each test a fresh db. It's tooling only, never imported by the app.
- Deliberately not added: `requests` (stdlib `urllib` is enough) and `python-dotenv` (export the
  API key in your shell).

---

## 3. Schema (Pydantic)

**Learn (Pydantic):**
- A `BaseModel` subclass is a typed record. Creating one validates the data, and a
  missing field or wrong type raises `ValidationError`.
- `Field(description=...)` text is sent to Claude as part of the JSON schema, so it doubles as
  instructions.
- `.model_dump_json()` / `.model_validate_json()` convert to and from a JSON string. That's how
  the record is stored in SQLite.

```python
# research_engine/models.py

class PaperMetadata(BaseModel):          # from the arXiv API, never from Claude
    arxiv_id: str                        # "2310.01234" (no version)
    title: str
    authors: list[str]
    published: date
    primary_category: str                # "q-fin.ST", "stat.ME", ...
    abstract: str

    @property
    def arxiv_url(self) -> str: ...      # https://arxiv.org/abs/<id>

class KeyConcept(BaseModel):
    term: str = Field(description="Short name of the concept, e.g. 'realised volatility'")
    explanation: str = Field(description="1–3 plain sentences a second-year student would follow")

class StudyRecord(BaseModel):            # ← the paper schema; changes need your OK
    plain_summary: str = Field(description="3–5 sentences, no jargon: what the paper does and why it matters")
    key_concepts: list[KeyConcept] = Field(description="3 to 6 concepts central to the paper")
    background: list[str] = Field(description="Topics to know first, each with why it's needed")
    research_question: str
    methods: list[str] = Field(description="Models, estimators or proof techniques used")
    data: str = Field(description="Datasets, period, frequency; 'None: theoretical paper' if none")
    key_results: list[str]
    limitations: list[str] = Field(description="Limitations the authors state; ['Not stated in the paper'] if none")
    keywords: list[str] = Field(description="5–10 lowercase search keywords")

class Paper(BaseModel):                  # what the app works with after loading
    metadata: PaperMetadata
    record: StudyRecord
    added_at: datetime
```

| Choice | Simpler alternative | Why this one |
|---|---|---|
| Lists for methods/results/limitations/background | One string per field | They show as bullets and compare well side by side. `data` and `research_question` stay single strings |
| "3 to 6" in the description only | `Field(min_length=3, max_length=6)` | A hard limit would make the whole paper fail if Claude returns 7. Listed as a known limitation |
| Metadata from the arXiv API | Ask Claude for title/authors/date | It's the ground truth, it's free, and filters depend on it being exact |

---

## 4. Database: one table, one row per paper (stdlib `sqlite3`, no ORM)

```sql
CREATE TABLE IF NOT EXISTS papers (
    arxiv_id         TEXT PRIMARY KEY,   -- "2310.01234", version stripped → duplicate check is a lookup
    title            TEXT NOT NULL,
    authors          TEXT NOT NULL,      -- JSON list
    published        TEXT NOT NULL,      -- ISO date, "2023-10-02"
    primary_category TEXT NOT NULL,
    abstract         TEXT NOT NULL,
    record_json      TEXT NOT NULL,      -- StudyRecord.model_dump_json()
    latex_text       TEXT NOT NULL,      -- flattened body; lets us regenerate a record without re-downloading
    model            TEXT NOT NULL,      -- "claude-sonnet-5-5"
    input_tokens     INTEGER,            -- cost tracking
    output_tokens    INTEGER,
    added_at         TEXT NOT NULL
);
```
- The db path comes from the `LIBRARY_DB` env var (default `data/library.db`).
- `load_library()` uses `pd.read_sql` and returns one DataFrame. `authors` and the record fields
  are parsed from JSON into Python lists and objects, so all filtering, search and the glossary
  are plain pandas.

| Choice | Simpler alternative | Why this one |
|---|---|---|
| Record as one JSON column | One column per record field | Pydantic writes and reads it in one call, and nothing needs SQL queries inside the record |
| Keep `latex_text` | Don't store the source | While tuning the prompt in step 4 you'll regenerate records often, and this avoids hitting arXiv each time |
| Filter in pandas | SQL `WHERE` clauses | You know pandas, the library is small, and TF-IDF needs the rows in memory anyway |

---

## 5. How each part works

**arxiv.py: from link to text**
- `parse_links(text)`: split lines, skip blanks, and pull a new-style id (`\d{4}\.\d{4,5}`) out
  of each line with one regex. Strip `vN` and drop duplicates within the paste. Lines with no id
  are reported as failed.
- `fetch_metadata(id)`: `urllib` GET `export.arxiv.org/api/query?id_list=<id>`, parsed with
  `xml.etree`. No entry raises "paper not found".
- `fetch_source(id)`: GET `arxiv.org/e-print/<id>`.
- Every arXiv request sends a generic User-Agent (`research-engine/0.1`) and is followed by
  `time.sleep(3)`, which respects arXiv's rate limit.
- `flatten_source(bytes) -> str`, common cases only:
  1. Decompress the gzip. If the result is a tar, read the `.tex` members into a `{name: text}`
     dict in memory. Otherwise it's a single `.tex` file. A `%PDF` source raises "PDF-only paper".
  2. Main file = the `.tex` containing `\documentclass`.
  3. Remove comments with one regex (a `%` not preceded by `\`).
  4. Replace `\input{x}` / `\include{x}` with `x.tex`'s text, using a recursive regex
     substitution. A missing file becomes empty text.
  5. Keep `\begin{document}`…`\end{document}` and cut at the bibliography.

**llm.py**
- `make_study_record(metadata, latex_text, client) -> (StudyRecord, usage)`
  - System prompt:
    - You are helping a student learn.
    - Use only the paper text below.
    - Where the paper doesn't say, write "Not stated in the paper".
    - Explain concepts plainly.
  - User message: title, authors, abstract, then the LaTeX body inside `<paper>` tags.
- `write_comparison(papers, client) -> str`
  - Input: each paper's title and stored record as JSON. No paper text, so the comparison is
    grounded in the records only.
  - Asks for about 300 words of markdown covering shared ideas, how the methods and data differ,
    how the results relate, and which to read first.
- **Learn (Claude API):**
  - `client = anthropic.Anthropic()` reads `ANTHROPIC_API_KEY` from your environment.
  - `client.messages.parse(model="claude-sonnet-5-5", max_tokens=16000, system=..., messages=[{"role": "user", "content": ...}], output_format=StudyRecord, output_config={"effort": "medium"})`
    constrains the reply to the Pydantic schema and returns it validated as `response.parsed_output`.
  - The comparison uses plain `client.messages.create(...)` and joins the `text` blocks.
  - `response.usage` gives the input and output tokens, which is what you pay for.
  - `response.stop_reason` is `"end_turn"` normally. We raise a clear error on `"max_tokens"` or `"refusal"`.
  - Don't pass `temperature`: Sonnet 5.5 rejects it. `effort` is the cost/quality dial.
  - Rough cost: ~$0.10 per paper record, ~$0.02 per comparison.
  - Testability: both functions take `client` as an argument, so tests pass a fake object and
    never call the API.

**ingest.py: `add_papers(ids, client, db, on_progress) -> list[IngestResult]`**
- For each id: skip it if it already exists, otherwise fetch → flatten → record → save. Each
  paper runs inside `try/except`, so one failure doesn't stop the batch.
- Each `IngestResult` has the id, a status (`added` / `skipped` / `failed`) and a message. The
  Add tab shows them as a table.

**library.py: pure functions on the library DataFrame**
- `apply_filters(df, categories, year_range, author)`: category multiselect, year slider, and a
  case-insensitive substring match on author names.
- `search(df, query)`
  - Build one search text per paper: title + abstract + plain summary + concept terms +
    keywords + methods.
  - Fit `TfidfVectorizer(stop_words="english", sublinear_tf=True)` on the filtered rows, then
    rank by `cosine_similarity` to the query and drop zero scores.
  - An empty query returns the rows newest first.
  - The index is refitted on every search, which takes milliseconds for a personal library.
- `build_glossary(df)`: explode `key_concepts` into one row per (term, explanation, paper) and
  group by a normalised term (casefold, collapse spaces). Each term lists every paper's
  explanation, so you can see how different papers describe it.
- `to_csv_frame(df)`: flatten lists to `"a; b; c"` and concepts to `"term: explanation | ..."`
  for export.

**app/app.py: the tabs**
- **Add:** text area, then an "Add papers" button. That calls `ingest.add_papers` with an
  `st.progress` callback and shows the results table.
- **Library:** filters, a search box, the results table and `st.download_button` for the CSV.
- **Paper:** a selectbox of titles, then `render_record`. `st.tabs` can't be switched from code,
  so the Library can't jump here; you pick the paper in this tab.
- **Glossary:** a text filter and one entry per term, listing each paper's explanation.
- **Compare:** `st.multiselect(max_selections=4)`, one `st.columns` column per paper with
  `render_record`, and a "Write comparison" button. Its result is kept in `st.session_state` so
  it survives reruns.

| Choice | Simpler alternative | Why this one |
|---|---|---|
| Search the record text, not the LaTeX | Index the full LaTeX | Records are clean prose. LaTeX is noisy and makes search slower |
| Glossary computed on the fly | A separate `concepts` table | Nothing to keep in sync, and no extra Claude calls (as specified) |
| Comparison not stored, kept in `st.session_state` | A `comparisons` table | One fewer table. Clicking the button again regenerates it for ~$0.02 |
| Compare with `st.columns` + `render_record` | One wide pandas table | Long text is unreadable in table cells, and it reuses the Paper tab's renderer |

---

## 6. Build steps (each about an evening, each ends with a check)

0. **Setup.**
   - Install Python 3.12 from python.org. This Mac has only the system Python 3.9 and no Homebrew.
   - `python3.12 -m venv .venv`, then `pyproject.toml` and `pip install -e ".[dev]"`.
   - `.gitignore`, and a `git init` (suggested).
   - `app/app.py` with five empty tabs and the footer note.

   **Check:** `pytest` runs, and `streamlit run app/app.py` shows the tabs and footer.
   **Learn (Streamlit):** the script reruns top to bottom on every click. Values that must survive
   a rerun live in `st.session_state`. `st.tabs` is layout only, so every tab's code runs on each rerun.
1. **models.py.** Tests: a valid record loads, a missing field raises `ValidationError`, and the
   JSON round-trip gives an equal object. **Check:** `pytest tests/test_models.py`. **Learn:** Pydantic.
2. **arxiv.py, part 1: links and metadata.** Tests: `parse_links` on abs/pdf/bare/versioned/junk
   lines and duplicates; metadata parsed from the saved XML.
   **Check:** `python scripts/try_paper.py meta <link>` prints the title, authors, date and category.
3. **arxiv.py, part 2: source and flattening.** Tests on tarballs built in `conftest.py`: a
   single-file paper, a multi-file paper with `\input`, a PDF-only source, and comment stripping.
   **Check:** `try_paper.py source <link>` prints the first 1,500 characters of the body.
4. **llm.make_study_record.** Tests with a fake client: the paper text reaches the prompt, the
   record comes back, and a `refusal` stop reason raises. **Check:** `export ANTHROPIC_API_KEY=...`,
   then `try_paper.py record <link>` prints the record and its token cost. Read 2–3 records
   against their papers and tune the prompt. **Learn:** Claude API.
5. **storage.py.** Tests on a `tmp_path` db: save → load gives an equal `Paper`, `paper_exists`
   works, and `load_library` returns the expected columns. **Check:** `try_paper.py add <link>`
   twice; the second run says "already saved".
6. **ingest.py + Add tab.** Tests with a fake client and fake fetchers: an added, a skipped and a
   failed paper in one batch. **Check:** in the app, paste 3 links (one duplicate, one junk line),
   watch the progress bar, and read the results table.
   **Learn:** `st.text_area`, `st.button`, `st.progress`, `st.dataframe`.
7. **Paper tab + `render_record`.** It shows the plain summary first, then key concepts,
   background, the detailed record in an expander, and the arXiv link.
   **Check:** pick each saved paper and read it.
   **Learn:** `st.selectbox`, `st.expander`, `st.markdown` (which renders `$…$` maths).
8. **Library tab: filters, search, CSV.** Tests in `test_library.py` on a small hand-made
   DataFrame: the obvious paper ranks first, filters narrow results, and the CSV has flat columns.
   **Check:** filter by category and year, search "volatility", and download the CSV and open it
   in pandas. **Learn:** `st.multiselect`, `st.slider`, `st.download_button`.
9. **Glossary tab.** Tests: the same term from two papers groups into one entry listing both.
   **Check:** the glossary lists every concept, and a text filter narrows it.
10. **Compare tab.** Tests: `write_comparison` sends only the records (no LaTeX) to the fake
    client. **Check:** pick 2, then 4 papers; the records appear side by side; "Write comparison"
    produces a short text that survives a rerun.
    **Learn:** `st.columns`, keeping results in `st.session_state`.
11. **End-to-end pass.** Add ~10 real papers across q-fin, stat and math. Fix rough edges: empty
    library, missing API key, a PDF-only paper. Update Known limitations with anything found.

After each step I'll stop and explain what changed and why before moving on.

---

## Verification (end of v1)
- `pytest` passes, with no network or API key needed.
- Manual run with `streamlit run app/app.py`:
  1. Add a batch of links that includes a duplicate and a PDF-only paper. Expect added, skipped
     and failed rows, and the batch keeps going.
  2. Spot-check 10 records against their papers. Note how many contain a mistake (an invented
     detail, a wrong method or result, a misattributed limitation) and what kind, and record the
     count in PLAN.md.
  3. Search, filter and export the CSV.
  4. In the glossary, check a shared concept lists both papers.
  5. Compare 2 papers and check the comparison mentions nothing absent from their records.
- Check the token columns: the total spend should be roughly what we estimated.

---

## Known limitations (accepted for v1)
- Only new-style arXiv ids (`2310.01234`). Old ids like `math/0601001` aren't parsed.
- PDF-only papers are reported as failed.
- Custom LaTeX macros stay unexpanded. Missing `\input` files are skipped.
- Very long papers are sent whole: no truncation, so they cost more.
- Ids are stored without a version, so a newer version of a saved paper isn't re-fetched.
- "3 to 6 key concepts" is asked for, not enforced.
- The glossary doesn't merge different spellings of one concept (e.g. "GARCH" vs "GARCH(1,1)").
- The Library tab can't jump to the Paper tab (`st.tabs` can't be switched from code); you pick
  the paper in the Paper tab.
- Records aren't editable or deletable in the UI, and comparisons aren't saved.
- Records are AI-generated and may contain mistakes (hence the footer note).
