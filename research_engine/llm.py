"""The LLM calls. The client is passed in, so tests can hand in a fake one and never touch the network."""

from research_engine.models import Paper, PaperMetadata, StudyRecord

# gpt-6-luna is OpenAI's cheapest current model ($0.10 / $0.50 per 1M input / output tokens).
# Change this one line to try a different model.
MODEL = "gpt-6-luna"

# Reasoning tokens count as output tokens, so leave plenty of room beyond the record itself.
MAX_OUTPUT_TOKENS = 16000

RECORD_INSTRUCTIONS = """You are helping a student learn from a research paper.
Fill in the study record using ONLY the paper text provided. Do not use outside knowledge.
Where the paper does not say, write "Not stated in the paper" instead of guessing.
Explain concepts plainly, as if to a second-year maths, statistics or finance student.
The paper is LaTeX; write your answer in plain text, using $...$ only for short formulas."""


def make_study_record(
    metadata: PaperMetadata, latex_text: str, client
) -> tuple[StudyRecord, int, int]:
    """One LLM call: returns (study record, input tokens, output tokens)."""
    paper_prompt = (
        f"Title: {metadata.title}\n"
        f"Authors: {', '.join(metadata.authors)}\n"
        f"Abstract: {metadata.abstract}\n\n"
        f"<paper>\n{latex_text}\n</paper>"
    )
    response = client.responses.parse(
        model=MODEL,
        instructions=RECORD_INSTRUCTIONS,
        input=paper_prompt,
        text_format=StudyRecord,  # the reply is forced to match this Pydantic model
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    if response.status != "completed":
        raise ValueError(f"the model did not finish ({response.incomplete_details})")
    if response.output_parsed is None:
        raise ValueError("the model returned no record (it may have refused)")
    return response.output_parsed, response.usage.input_tokens, response.usage.output_tokens


COMPARISON_INSTRUCTIONS = """You are helping a student compare research papers.
You are given a study record for each paper. Use ONLY these records. Do not use outside knowledge,
and do not add details they don't contain; if the records don't say, say so.
Write about 300 words of markdown with four short headings: Shared ideas, Methods and data,
Results, Which to read first. Refer to the papers by their titles."""


def write_comparison(papers: list[Paper], client) -> str:
    """One LLM call: a short written comparison, based only on the stored records (not the paper text)."""
    sections = [
        f"PAPER {number}: {paper.metadata.title} ({paper.metadata.arxiv_id}, {paper.metadata.published.year})\n"
        f"{paper.record.model_dump_json(indent=2)}"
        for number, paper in enumerate(papers, start=1)
    ]
    response = client.responses.create(
        model=MODEL,
        instructions=COMPARISON_INSTRUCTIONS,
        input="\n\n".join(sections),
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    if response.status != "completed":
        raise ValueError(f"the model did not finish ({response.incomplete_details})")
    return response.output_text
