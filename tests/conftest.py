"""Shared test helpers. Fake arXiv downloads are built in memory, so no binary files are committed."""

import gzip
import io
import tarfile

import pytest


@pytest.fixture
def make_tar_gz():
    """Return a function: {file name: text} -> bytes of a .tar.gz, like arXiv's multi-file sources."""

    def build(files: dict[str, str]) -> bytes:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            for name, text in files.items():
                data = text.encode("utf-8")
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        return buffer.getvalue()

    return build


@pytest.fixture
def make_gz():
    """Return a function: text -> bytes of a gzipped single .tex file."""
    return lambda text: gzip.compress(text.encode("utf-8"))


@pytest.fixture
def paper_factory():
    """Return a function that builds a Paper with sensible defaults; tests override what they care about."""
    from datetime import date, datetime

    from research_engine.models import KeyConcept, Paper, PaperMetadata, StudyRecord

    def build(
        arxiv_id="2310.00001",
        title="A Paper",
        authors=("A. Author",),
        category="q-fin.ST",
        published=date(2023, 1, 1),
        summary="A summary.",
        concepts=(("term", "explanation"),),
        keywords=("keyword",),
        methods=("method",),
        added_at=datetime(2026, 1, 1),
    ) -> Paper:
        return Paper(
            metadata=PaperMetadata(
                arxiv_id=arxiv_id,
                title=title,
                authors=list(authors),
                published=published,
                primary_category=category,
                abstract="Abstract.",
            ),
            record=StudyRecord(
                plain_summary=summary,
                key_concepts=[KeyConcept(term=t, explanation=e) for t, e in concepts],
                background=["background topic"],
                research_question="question",
                methods=list(methods),
                data="data",
                key_results=["result"],
                limitations=["limitation"],
                keywords=list(keywords),
            ),
            added_at=added_at,
        )

    return build


@pytest.fixture
def library_df(paper_factory):
    """A small library as the DataFrame the app works with: three papers, saved to and loaded from SQLite."""
    from datetime import date, datetime

    from research_engine import storage

    db = storage.connect(":memory:")
    papers = [
        paper_factory(
            arxiv_id="2101.00001", title="Realised volatility forecasting with HAR models",
            authors=("Alice Smith", "Bob Jones"), category="q-fin.ST", published=date(2021, 5, 1),
            summary="Forecasts realised volatility with a simple regression.",
            concepts=(("realised volatility", "Volatility measured from intraday returns."),),
            keywords=("volatility", "har"), methods=("HAR regression",), added_at=datetime(2026, 1, 1),
        ),
        paper_factory(
            arxiv_id="2301.00002", title="Cointegration tests for pairs trading",
            authors=("Carol White",), category="q-fin.TR", published=date(2023, 3, 1),
            summary="Tests whether two prices move together over the long run.",
            concepts=(("cointegration", "Two series share a long-run trend."),),
            keywords=("pairs", "trading"), methods=("Engle-Granger test",), added_at=datetime(2026, 2, 1),
        ),
        paper_factory(
            arxiv_id="2302.00003", title="Bayesian shrinkage for covariance estimation",
            authors=("Alice Smith",), category="stat.ME", published=date(2023, 7, 1),
            summary="Shrinks a noisy sample covariance matrix towards a simple target.",
            concepts=(("shrinkage", "Pulling noisy estimates toward a stable target."),),
            keywords=("covariance", "bayesian"), methods=("Ledoit-Wolf shrinkage",), added_at=datetime(2026, 3, 1),
        ),
    ]  # fmt: skip
    for paper in papers:
        storage.save_paper(db, paper, "LATEX", "test-model", 100, 20)
    df = storage.load_library(db)
    db.close()
    return df
