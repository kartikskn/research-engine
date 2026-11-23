"""The whole Streamlit UI: five tabs, one small function per tab."""

import streamlit as st


def add_tab() -> None:
    st.write("Add papers: coming in step 6.")


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

    add, library, paper, glossary, compare = st.tabs(
        ["Add", "Library", "Paper", "Glossary", "Compare"]
    )
    # Streamlit reruns this whole script on every click, and every tab's code
    # runs each time (st.tabs only changes the layout), so keep tab functions cheap.
    with add:
        add_tab()
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
