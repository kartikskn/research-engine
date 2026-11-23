from datetime import date
from types import SimpleNamespace

import pytest

from research_engine import llm
from research_engine.models import KeyConcept, PaperMetadata, StudyRecord


class FakeClient:
    """Stands in for openai.OpenAI(): remembers the call and returns a canned response."""

    def __init__(self, **response_fields):
        defaults = dict(
            status="completed",
            incomplete_details=None,
            output_parsed=make_record(),
            usage=SimpleNamespace(input_tokens=1200, output_tokens=340),
        )
        defaults.update(response_fields)
        self.calls = []
        self.responses = SimpleNamespace(parse=self._parse)
        self._response = SimpleNamespace(**defaults)

    def _parse(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


def make_record() -> StudyRecord:
    return StudyRecord(
        plain_summary="A summary.",
        key_concepts=[KeyConcept(term="term", explanation="explanation")],
        background=["b"],
        research_question="q",
        methods=["m"],
        data="d",
        key_results=["r"],
        limitations=["l"],
        keywords=["k"],
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


def test_record_and_token_counts_come_back():
    client = FakeClient()
    record, tokens_in, tokens_out = llm.make_study_record(make_metadata(), "LATEX BODY", client)
    assert record == make_record()
    assert (tokens_in, tokens_out) == (1200, 340)


def test_paper_text_and_metadata_reach_the_prompt():
    client = FakeClient()
    llm.make_study_record(make_metadata(), "UNIQUE LATEX BODY", client)
    call = client.calls[0]
    assert "UNIQUE LATEX BODY" in call["input"]
    assert "A Test Paper" in call["input"] and "A. Author, B. Author" in call["input"]
    assert "We study volatility." in call["input"]


def test_call_uses_the_model_constant_and_the_study_record_schema():
    client = FakeClient()
    llm.make_study_record(make_metadata(), "x", client)
    call = client.calls[0]
    assert call["model"] == llm.MODEL
    assert call["text_format"] is StudyRecord
    assert "Not stated in the paper" in call["instructions"]


def test_incomplete_response_raises():
    client = FakeClient(status="incomplete", incomplete_details=SimpleNamespace(reason="max_output_tokens"))
    with pytest.raises(ValueError, match="did not finish"):
        llm.make_study_record(make_metadata(), "x", client)


def test_refusal_raises():
    client = FakeClient(output_parsed=None)
    with pytest.raises(ValueError, match="refused"):
        llm.make_study_record(make_metadata(), "x", client)
