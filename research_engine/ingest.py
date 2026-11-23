"""Adding papers to the library: the per-paper loop, with skip and fail handling."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from sqlite3 import Connection

from research_engine import arxiv, llm, storage
from research_engine.models import Paper


@dataclass
class IngestResult:
    arxiv_id: str
    status: str  # "added", "skipped" or "failed"
    message: str


def add_papers(
    ids: list[str],
    client,
    db: Connection,
    on_progress: Callable[[int, int, str], None],
) -> list[IngestResult]:
    """Add papers one at a time. on_progress(done, total, current_id) lets the UI move a progress bar."""
    results = []
    for done, arxiv_id in enumerate(ids):
        on_progress(done, len(ids), arxiv_id)
        results.append(_add_one(arxiv_id, client, db))
    on_progress(len(ids), len(ids), "")
    return results


def _add_one(arxiv_id: str, client, db: Connection) -> IngestResult:
    if storage.paper_exists(db, arxiv_id):
        return IngestResult(arxiv_id, "skipped", "already saved")
    try:
        metadata = arxiv.fetch_metadata(arxiv_id)
        body = arxiv.flatten_source(arxiv.fetch_source(arxiv_id))
        record, tokens_in, tokens_out = llm.make_study_record(metadata, body, client)
    except Exception as error:  # one bad paper must not stop the rest of the batch
        return IngestResult(arxiv_id, "failed", str(error))
    paper = Paper(metadata=metadata, record=record, added_at=datetime.now())
    storage.save_paper(db, paper, body, llm.MODEL, tokens_in, tokens_out)
    return IngestResult(arxiv_id, "added", metadata.title)
