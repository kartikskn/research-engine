from datetime import date

import pytest

from research_engine import ingest, storage
from research_engine.models import KeyConcept, PaperMetadata, StudyRecord


def fake_metadata(arxiv_id):
    if arxiv_id == "1111.00000":
        raise ValueError("paper not found")
    return PaperMetadata(
        arxiv_id=arxiv_id,
        title=f"Paper {arxiv_id}",
        authors=["A. Author"],
        published=date(2023, 10, 2),
        primary_category="q-fin.ST",
        abstract="Abstract.",
    )


def fake_flatten(raw):
    if raw == b"PDF-ONLY":
        raise ValueError("PDF-only paper: no LaTeX source")
    return "LATEX BODY"


def fake_record(metadata, body, client):
    record = StudyRecord(
        plain_summary="s",
        key_concepts=[KeyConcept(term="t", explanation="e")],
        background=["b"],
        research_question="q",
        methods=["m"],
        data="d",
        key_results=["r"],
        limitations=["l"],
        keywords=["k"],
    )
    return record, 100, 20


@pytest.fixture
def db(tmp_path, monkeypatch):
    # Replace the network and LLM calls with fakes so the loop can be tested offline.
    monkeypatch.setattr(ingest.arxiv, "fetch_metadata", fake_metadata)
    monkeypatch.setattr(ingest.arxiv, "fetch_source", lambda arxiv_id: b"PDF-ONLY" if arxiv_id == "2222.00000" else b"ok")
    monkeypatch.setattr(ingest.arxiv, "flatten_source", fake_flatten)
    monkeypatch.setattr(ingest.llm, "make_study_record", fake_record)
    connection = storage.connect(str(tmp_path / "test.db"))
    yield connection
    connection.close()


def no_progress(done, total, current):
    pass


def test_added_skipped_and_failed_in_one_batch(db):
    ingest.add_papers(["2310.00001"], client=None, db=db, on_progress=no_progress)  # already saved
    ids = ["2310.00001", "2310.00002", "1111.00000", "2222.00000", "2310.00003"]
    results = ingest.add_papers(ids, client=None, db=db, on_progress=no_progress)

    assert [(r.arxiv_id, r.status) for r in results] == [
        ("2310.00001", "skipped"),
        ("2310.00002", "added"),
        ("1111.00000", "failed"),  # not found on arXiv
        ("2222.00000", "failed"),  # PDF-only
        ("2310.00003", "added"),  # the batch carried on after the failures
    ]
    assert results[0].message == "already saved"
    assert results[2].message == "paper not found"
    assert "PDF-only" in results[3].message
    assert set(storage.load_library(db)["arxiv_id"]) == {"2310.00001", "2310.00002", "2310.00003"}


def test_saved_paper_keeps_body_model_and_tokens(db):
    ingest.add_papers(["2310.00001"], client=None, db=db, on_progress=no_progress)
    row = db.execute("SELECT latex_text, model, input_tokens, output_tokens FROM papers").fetchone()
    assert row == ("LATEX BODY", ingest.llm.MODEL, 100, 20)


def test_progress_is_reported_before_each_paper_and_at_the_end(db):
    calls = []
    ingest.add_papers(
        ["2310.00001", "2310.00002"], client=None, db=db, on_progress=lambda *args: calls.append(args)
    )
    assert calls == [(0, 2, "2310.00001"), (1, 2, "2310.00002"), (2, 2, "")]


def test_empty_batch(db):
    calls = []
    assert ingest.add_papers([], client=None, db=db, on_progress=lambda *a: calls.append(a)) == []
    assert calls == [(0, 0, "")]
