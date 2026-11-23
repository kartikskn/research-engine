from datetime import date, datetime

import pytest

from research_engine import storage
from research_engine.models import KeyConcept, Paper, PaperMetadata, StudyRecord


def make_paper(arxiv_id="2310.01234", added_at=datetime(2026, 11, 23, 14, 30)) -> Paper:
    return Paper(
        metadata=PaperMetadata(
            arxiv_id=arxiv_id,
            title=f"Paper {arxiv_id}",
            authors=["A. Author", "B. Author"],
            published=date(2023, 10, 2),
            primary_category="q-fin.ST",
            abstract="We study volatility.",
        ),
        record=StudyRecord(
            plain_summary="A summary.",
            key_concepts=[KeyConcept(term="term", explanation="explanation")],
            background=["b"],
            research_question="q",
            methods=["m"],
            data="d",
            key_results=["r"],
            limitations=["l"],
            keywords=["k"],
        ),
        added_at=added_at,
    )


@pytest.fixture
def db(tmp_path):
    connection = storage.connect(str(tmp_path / "test.db"))
    yield connection
    connection.close()


def save(db, paper):
    storage.save_paper(db, paper, "LATEX", "test-model", 1000, 200)


def test_save_then_load_gives_an_equal_paper(db):
    paper = make_paper()
    save(db, paper)
    assert storage.load_paper(db, "2310.01234") == paper


def test_paper_exists(db):
    assert not storage.paper_exists(db, "2310.01234")
    save(db, make_paper())
    assert storage.paper_exists(db, "2310.01234")
    assert not storage.paper_exists(db, "2401.05678")


def test_load_missing_paper_raises(db):
    with pytest.raises(KeyError):
        storage.load_paper(db, "2310.01234")


def test_saving_the_same_paper_twice_is_refused(db):
    save(db, make_paper())
    with pytest.raises(Exception):  # sqlite3.IntegrityError: arxiv_id is the primary key
        save(db, make_paper())


def test_load_library_columns_and_types(db):
    save(db, make_paper())
    df = storage.load_library(db)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["authors"] == ["A. Author", "B. Author"]
    assert row["record"].research_question == "q"
    assert row["year"] == 2023
    assert row["primary_category"] == "q-fin.ST"
    assert (row["input_tokens"], row["output_tokens"], row["model"]) == (1000, 200, "test-model")
    assert "record_json" not in df.columns


def test_load_library_newest_first(db):
    save(db, make_paper("2310.00001", added_at=datetime(2026, 1, 1)))
    save(db, make_paper("2310.00002", added_at=datetime(2026, 3, 1)))
    save(db, make_paper("2310.00003", added_at=datetime(2026, 2, 1)))
    assert list(storage.load_library(db)["arxiv_id"]) == ["2310.00002", "2310.00003", "2310.00001"]


def test_load_library_when_empty_still_has_the_columns(db):
    df = storage.load_library(db)
    assert df.empty
    assert {"arxiv_id", "title", "authors", "record", "year", "primary_category"} <= set(df.columns)


def test_connect_creates_missing_folder_and_uses_env_variable(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARY_DB", str(tmp_path / "newfolder" / "lib.db"))
    storage.connect().close()
    assert (tmp_path / "newfolder" / "lib.db").exists()
