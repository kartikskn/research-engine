"""The whole Streamlit UI: five tabs, one small function per tab."""

from dataclasses import asdict

import pandas as pd
import streamlit as st
from openai import OpenAI, OpenAIError

from research_engine import arxiv, ingest, library, llm, storage
from research_engine.models import Paper


def add_tab(db) -> None:
    st.subheader("Add papers")
    text = st.text_area("arXiv links, one per line", height=150)
    if not st.button("Add papers"):
        return
    ids, bad_lines = arxiv.parse_links(text)
    if not ids and not bad_lines:
        st.warning("Paste at least one arXiv link first.")
        return
    try:
        client = OpenAI()  # reads OPENAI_API_KEY from the environment
    except OpenAIError as error:
        st.error(f"Cannot reach the LLM: {error}")
        return

    bar = st.progress(0.0)

    def show_progress(done: int, total: int, current_id: str) -> None:
        bar.progress(done / total, text=f"Adding {current_id} ({done + 1} of {total})" if current_id else "Done")

    results = ingest.add_papers(ids, client, db, show_progress)
    bad = [ingest.IngestResult(line, "failed", "no arXiv id found in this line") for line in bad_lines]
    st.dataframe(pd.DataFrame([asdict(r) for r in bad + results]), hide_index=True)


def bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def render_record(paper: Paper, open_details: bool = False) -> None:
    """Show one paper: plain summary first, then concepts and background, then the detailed record."""
    meta, record = paper.metadata, paper.record
    authors = ", ".join(meta.authors[:6]) + (" et al." if len(meta.authors) > 6 else "")
    st.subheader(meta.title)
    st.caption(f"{authors} · {meta.published} · {meta.primary_category}")
    st.markdown(f"[Read the paper on arXiv]({meta.arxiv_url})")

    st.markdown("**In plain words**")
    st.write(record.plain_summary)
    st.markdown("**Key concepts**")
    st.markdown("\n".join(f"- **{c.term}**: {c.explanation}" for c in record.key_concepts))
    st.markdown("**Background: what to know first**")
    st.markdown(bullets(record.background))

    with st.expander("Detailed record", expanded=open_details):
        st.markdown(f"**Research question**\n\n{record.research_question}")
        st.markdown("**Methods**\n\n" + bullets(record.methods))
        st.markdown(f"**Data**\n\n{record.data}")
        st.markdown("**Key results**\n\n" + bullets(record.key_results))
        st.markdown("**Limitations**\n\n" + bullets(record.limitations))
        st.markdown("**Keywords**\n\n" + ", ".join(record.keywords))


def library_tab(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No papers yet. Add some in the Add tab.")
        return
    col_category, col_year, col_author = st.columns(3)
    categories = col_category.multiselect("Category", sorted(df["primary_category"].unique()))
    first_year, last_year = int(df["year"].min()), int(df["year"].max())
    year_range = (first_year, last_year)
    if first_year < last_year:  # a slider needs a range, so skip it when every paper is from one year
        year_range = col_year.slider("Year", first_year, last_year, (first_year, last_year))
    author = col_author.text_input("Author contains")
    query = st.text_input("Search the library", placeholder="e.g. realised volatility forecasting")

    results = library.search(library.apply_filters(df, categories, year_range, author), query)
    table = library.to_csv_frame(results)
    st.write(f"{len(results)} of {len(df)} papers")
    st.dataframe(
        table[["arxiv_id", "title", "authors", "published", "primary_category", "plain_summary"]],
        hide_index=True,
    )
    st.download_button("Download CSV", table.to_csv(index=False), "library.csv", "text/csv")


def paper_tab(db, df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No papers yet. Add some in the Add tab.")
        return
    titles = dict(zip(df["arxiv_id"], df["title"]))
    arxiv_id = st.selectbox("Paper", options=list(titles), format_func=lambda i: f"{titles[i]} ({i})")
    render_record(storage.load_paper(db, arxiv_id))


def glossary_tab(df: pd.DataFrame) -> None:
    glossary = library.build_glossary(df)
    if not glossary:
        st.info("No concepts yet. Add some papers in the Add tab.")
        return
    needle = st.text_input("Filter concepts").strip().lower()
    shown = [entry for entry in glossary if needle in entry["term"].lower()]
    st.write(f"{len(shown)} of {len(glossary)} concepts")
    for entry in shown:
        st.markdown(f"#### {entry['term']}")
        st.markdown("\n".join(f"- {p['explanation']}  *(from {p['title']}, {p['arxiv_id']})*" for p in entry["papers"]))


def compare_tab(db, df: pd.DataFrame) -> None:
    if len(df) < 2:
        st.info("Add at least two papers to compare them.")
        return
    titles = dict(zip(df["arxiv_id"], df["title"]))
    chosen = st.multiselect(
        "Choose 2 to 4 papers", list(titles), format_func=lambda i: f"{titles[i]} ({i})", max_selections=4
    )
    if len(chosen) < 2:
        st.info("Pick at least two papers.")
        return

    papers = [storage.load_paper(db, arxiv_id) for arxiv_id in chosen]
    for column, paper in zip(st.columns(len(papers)), papers):
        with column:
            render_record(paper, open_details=True)

    st.subheader("Written comparison")
    # The comparison is kept in session_state so it survives reruns. It isn't saved in the database:
    # pressing the button again just makes a new one.
    if st.button("Write comparison"):
        try:
            with st.spinner("Writing..."):
                text = llm.write_comparison(papers, OpenAI())
            st.session_state["comparison"] = (tuple(chosen), text)
        except Exception as error:  # a missing key, a network problem or an unfinished reply
            st.error(f"Could not write the comparison: {error}")
    saved = st.session_state.get("comparison")
    if saved and saved[0] == tuple(chosen):  # only show it while the same papers are selected
        st.markdown(saved[1])


def main() -> None:
    st.set_page_config(page_title="Research Library", layout="wide")
    st.title("Research Library")
    db = storage.connect()

    add, library, paper, glossary, compare = st.tabs(
        ["Add", "Library", "Paper", "Glossary", "Compare"]
    )
    # Streamlit reruns this whole script on every click, and every tab's code
    # runs each time (st.tabs only changes the layout), so keep tab functions cheap.
    with add:
        add_tab(db)
    df = storage.load_library(db)  # loaded after the Add tab, so a paper just added shows up at once
    with library:
        library_tab(df)
    with paper:
        paper_tab(db, df)
    with glossary:
        glossary_tab(df)
    with compare:
        compare_tab(db, df)

    st.caption("Records are AI-generated summaries. Check them against the paper.")


main()
