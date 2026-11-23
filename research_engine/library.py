"""Working with the library DataFrame: filters, TF-IDF search and CSV export. No Streamlit in here."""

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

CSV_COLUMNS = [
    "arxiv_id", "title", "authors", "published", "primary_category", "plain_summary",
    "key_concepts", "background", "research_question", "methods", "data",
    "key_results", "limitations", "keywords",
]  # fmt: skip


def apply_filters(
    df: pd.DataFrame,
    categories: list[str] | None = None,
    year_range: tuple[int, int] | None = None,
    author: str = "",
) -> pd.DataFrame:
    """Keep papers matching all the filters that are set. An empty filter keeps everything."""
    if categories:
        df = df[df["primary_category"].isin(categories)]
    if year_range:
        first_year, last_year = year_range
        df = df[df["year"].between(first_year, last_year)]
    if author.strip():
        needle = author.strip().lower()
        df = df[df["authors"].apply(lambda names: any(needle in name.lower() for name in names))]
    return df


def search_text(row: pd.Series) -> str:
    """Everything about a paper we want a search to match: clean prose from the record, not raw LaTeX."""
    record = row["record"]
    parts = [row["title"], row["abstract"], record.plain_summary]
    parts += [concept.term for concept in record.key_concepts]
    parts += record.keywords + record.methods
    return " ".join(parts)


def search(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Rank papers by TF-IDF cosine similarity to the query; papers with no match are dropped.

    An empty query returns every paper, newest first. The index is rebuilt on every call:
    for a personal library that takes milliseconds, so there is nothing to cache or keep in sync.
    """
    if not query.strip() or df.empty:
        return df.sort_values("added_at", ascending=False)
    texts = df.apply(search_text, axis=1)
    vectorizer = TfidfVectorizer(stop_words="english", sublinear_tf=True)
    paper_vectors = vectorizer.fit_transform(texts)
    scores = cosine_similarity(vectorizer.transform([query]), paper_vectors)[0]
    ranked = df.assign(_score=scores)
    ranked = ranked[ranked["_score"] > 0].sort_values("_score", ascending=False)
    return ranked.drop(columns="_score")


def to_csv_frame(df: pd.DataFrame) -> pd.DataFrame:
    """One flat row per paper (lists joined into text) so the data opens cleanly in a spreadsheet."""
    rows = []
    for _, paper in df.iterrows():
        record = paper["record"]
        rows.append(
            {
                "arxiv_id": paper["arxiv_id"],
                "title": paper["title"],
                "authors": "; ".join(paper["authors"]),
                "published": paper["published"].date().isoformat(),
                "primary_category": paper["primary_category"],
                "plain_summary": record.plain_summary,
                "key_concepts": " | ".join(f"{c.term}: {c.explanation}" for c in record.key_concepts),
                "background": "; ".join(record.background),
                "research_question": record.research_question,
                "methods": "; ".join(record.methods),
                "data": record.data,
                "key_results": "; ".join(record.key_results),
                "limitations": "; ".join(record.limitations),
                "keywords": "; ".join(record.keywords),
            }
        )
    return pd.DataFrame(rows, columns=CSV_COLUMNS)


def normalise_term(term: str) -> str:
    """'Realised  Volatility' and 'realised volatility' count as the same concept."""
    return " ".join(term.casefold().split())


def build_glossary(df: pd.DataFrame) -> list[dict]:
    """Every key concept in the library, A to Z, each with the papers that use it.

    Each entry is {"term": ..., "papers": [{"arxiv_id", "title", "explanation"}, ...]}.
    Built from the stored records, so it costs no LLM calls.
    """
    entries: dict[str, dict] = {}
    for _, paper in df.iterrows():
        for concept in paper["record"].key_concepts:
            entry = entries.setdefault(normalise_term(concept.term), {"term": concept.term, "papers": []})
            entry["papers"].append(
                {"arxiv_id": paper["arxiv_id"], "title": paper["title"], "explanation": concept.explanation}
            )
    return [entries[key] for key in sorted(entries)]
