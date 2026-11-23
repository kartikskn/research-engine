from datetime import date, datetime

import pytest
from pydantic import ValidationError

from research_engine.models import KeyConcept, Paper, PaperMetadata, StudyRecord


def make_record() -> StudyRecord:
    return StudyRecord(
        plain_summary="The paper forecasts volatility with a simple regression.",
        key_concepts=[
            KeyConcept(term="realised volatility", explanation="Volatility measured from intraday returns."),
        ],
        background=["Linear regression: the model is a regression."],
        research_question="Can a simple model forecast realised volatility?",
        methods=["HAR-RV regression"],
        data="S&P 500 5-minute returns, 2000-2020",
        key_results=["The simple model beats GARCH out of sample."],
        limitations=["Only one market is tested."],
        keywords=["volatility", "har-rv"],
    )


def make_metadata() -> PaperMetadata:
    return PaperMetadata(
        arxiv_id="2310.01234",
        title="A Test Paper",
        authors=["A. Author", "B. Author"],
        published=date(2023, 10, 2),
        primary_category="q-fin.ST",
        abstract="We study volatility.",
    )


def test_valid_record_loads():
    record = make_record()
    assert record.key_concepts[0].term == "realised volatility"
    assert record.methods == ["HAR-RV regression"]


def test_missing_field_raises_validation_error():
    data = make_record().model_dump()
    del data["research_question"]
    with pytest.raises(ValidationError):
        StudyRecord(**data)


def test_wrong_type_raises_validation_error():
    data = make_record().model_dump()
    data["methods"] = "not a list"
    with pytest.raises(ValidationError):
        StudyRecord(**data)


def test_record_json_round_trip():
    record = make_record()
    restored = StudyRecord.model_validate_json(record.model_dump_json())
    assert restored == record


def test_paper_json_round_trip():
    paper = Paper(
        metadata=make_metadata(),
        record=make_record(),
        added_at=datetime(2026, 11, 23, 14, 30),
    )
    restored = Paper.model_validate_json(paper.model_dump_json())
    assert restored == paper
    assert restored.metadata.published == date(2023, 10, 2)


def test_arxiv_url():
    assert make_metadata().arxiv_url == "https://arxiv.org/abs/2310.01234"


def test_field_descriptions_reach_the_json_schema():
    # These descriptions are what the LLM sees when filling in a StudyRecord.
    schema = StudyRecord.model_json_schema()
    assert "3 to 6" in schema["properties"]["key_concepts"]["description"]
