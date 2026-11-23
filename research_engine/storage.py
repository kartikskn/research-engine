"""SQLite storage: one table, one row per paper. Uses the standard library's sqlite3, no ORM."""

import json
import os
import sqlite3
from pathlib import Path

import pandas as pd

from research_engine.models import Paper, PaperMetadata, StudyRecord

DEFAULT_DB_PATH = "data/library.db"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS papers (
    arxiv_id         TEXT PRIMARY KEY,   -- version stripped, so a duplicate check is a lookup
    title            TEXT NOT NULL,
    authors          TEXT NOT NULL,      -- JSON list
    published        TEXT NOT NULL,      -- ISO date, "2023-10-02"
    primary_category TEXT NOT NULL,
    abstract         TEXT NOT NULL,
    record_json      TEXT NOT NULL,      -- StudyRecord.model_dump_json()
    latex_text       TEXT NOT NULL,      -- flattened body, so a record can be redone without re-downloading
    model            TEXT NOT NULL,      -- which LLM wrote the record
    input_tokens     INTEGER,            -- cost tracking
    output_tokens    INTEGER,
    added_at         TEXT NOT NULL
)
"""


def connect(path: str | None = None) -> sqlite3.Connection:
    """Open the database (creating the file and table if needed)."""
    path = path or os.environ.get("LIBRARY_DB", DEFAULT_DB_PATH)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute(CREATE_TABLE)
    return db


def paper_exists(db: sqlite3.Connection, arxiv_id: str) -> bool:
    row = db.execute("SELECT 1 FROM papers WHERE arxiv_id = ?", (arxiv_id,)).fetchone()
    return row is not None


def save_paper(
    db: sqlite3.Connection,
    paper: Paper,
    latex_text: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    meta = paper.metadata
    db.execute(
        "INSERT INTO papers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            meta.arxiv_id,
            meta.title,
            json.dumps(meta.authors),
            meta.published.isoformat(),
            meta.primary_category,
            meta.abstract,
            paper.record.model_dump_json(),
            latex_text,
            model,
            input_tokens,
            output_tokens,
            paper.added_at.isoformat(),
        ),
    )
    db.commit()


def load_paper(db: sqlite3.Connection, arxiv_id: str) -> Paper:
    row = db.execute(
        "SELECT arxiv_id, title, authors, published, primary_category, abstract, record_json, added_at "
        "FROM papers WHERE arxiv_id = ?",
        (arxiv_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"paper {arxiv_id} is not in the library")
    arxiv_id, title, authors, published, category, abstract, record_json, added_at = row
    return Paper(
        metadata=PaperMetadata(
            arxiv_id=arxiv_id,
            title=title,
            authors=json.loads(authors),
            published=published,  # Pydantic turns the ISO string back into a date
            primary_category=category,
            abstract=abstract,
        ),
        record=StudyRecord.model_validate_json(record_json),
        added_at=added_at,
    )


def load_library(db: sqlite3.Connection) -> pd.DataFrame:
    """The whole library as one DataFrame (one row per paper, newest first)."""
    df = pd.read_sql(
        "SELECT arxiv_id, title, authors, published, primary_category, abstract, record_json, "
        "model, input_tokens, output_tokens, added_at FROM papers ORDER BY added_at DESC",
        db,
    )
    df["authors"] = df["authors"].apply(json.loads)
    df["record"] = df["record_json"].apply(StudyRecord.model_validate_json)
    df["published"] = pd.to_datetime(df["published"])
    df["year"] = df["published"].dt.year
    df["added_at"] = pd.to_datetime(df["added_at"])
    return df.drop(columns="record_json")
