"""The whole Streamlit UI: five tabs, one small function per tab."""

from dataclasses import asdict

import pandas as pd
import streamlit as st
from openai import OpenAI, OpenAIError

from research_engine import arxiv, ingest, storage


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


def library_tab() -> None:
    st.write("Library: coming in step 8.")


def paper_tab() -> None:
    st.write("Paper: coming in step 7.")


def glossary_tab() -> None:
    st.write("Glossary: coming in step 9.")


def compare_tab() -> None:
    st.write("Compare: coming in step 10.")


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
    with library:
        library_tab()
    with paper:
        paper_tab()
    with glossary:
        glossary_tab()
    with compare:
        compare_tab()

    st.caption("Records are AI-generated summaries. Check them against the paper.")


main()
