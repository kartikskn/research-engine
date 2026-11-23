"""Pydantic models: the shapes of data that flow through the app.

A BaseModel is a typed record. Creating one validates the data, and a missing
field or wrong type raises pydantic.ValidationError.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field


class PaperMetadata(BaseModel):
    """Facts about the paper, taken from the arXiv API (never written by Claude)."""

    arxiv_id: str  # "2310.01234", no version suffix
    title: str
    authors: list[str]
    published: date
    primary_category: str  # "q-fin.ST", "stat.ME", ...
    abstract: str

    @property
    def arxiv_url(self) -> str:
        return f"https://arxiv.org/abs/{self.arxiv_id}"


class KeyConcept(BaseModel):
    # The Field descriptions below are sent to Claude as part of the JSON schema
    # when it fills in a StudyRecord, so they double as instructions.
    term: str = Field(description="Short name of the concept, e.g. 'realised volatility'")
    explanation: str = Field(description="1-3 plain sentences a second-year student would follow")


class StudyRecord(BaseModel):
    """What Claude writes about one paper. Changing this schema needs the owner's OK."""

    plain_summary: str = Field(
        description="3-5 sentences, no jargon: what the paper does and why it matters"
    )
    # "3 to 6" is only asked for, not enforced: a hard limit would make the whole
    # paper fail if Claude returned 7 (listed under Known limitations in PLAN.md).
    key_concepts: list[KeyConcept] = Field(description="3 to 6 concepts central to the paper")
    background: list[str] = Field(description="Topics to know first, each with why it's needed")
    research_question: str
    methods: list[str] = Field(description="Models, estimators or proof techniques used")
    data: str = Field(
        description="Datasets, period, frequency; 'None: theoretical paper' if none"
    )
    key_results: list[str]
    limitations: list[str] = Field(
        description="Limitations the authors state; ['Not stated in the paper'] if none"
    )
    keywords: list[str] = Field(description="5-10 lowercase search keywords")


class Paper(BaseModel):
    """What the app works with after loading a paper from the database."""

    metadata: PaperMetadata
    record: StudyRecord
    added_at: datetime
