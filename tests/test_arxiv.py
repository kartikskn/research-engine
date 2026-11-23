from datetime import date
from pathlib import Path

import pytest

from research_engine.arxiv import flatten_source, parse_links, parse_metadata

FIXTURE = Path(__file__).parent / "fixtures" / "atom_sample.xml"


# ---- parse_links ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "https://arxiv.org/abs/2310.01234",
        "http://arxiv.org/abs/2310.01234",
        "arxiv.org/abs/2310.01234",
        "https://arxiv.org/pdf/2310.01234",
        "https://arxiv.org/pdf/2310.01234.pdf",
        "https://arxiv.org/abs/2310.01234v2",
        "https://arxiv.org/pdf/2310.01234v3.pdf",
        "2310.01234",
        "2310.01234v2",
        "  2310.01234  ",
        "arXiv:2310.01234",
    ],
)
def test_parse_links_accepts_common_formats(line):
    assert parse_links(line) == (["2310.01234"], [])


def test_parse_links_handles_five_digit_ids():
    assert parse_links("https://arxiv.org/abs/2611.27274v1") == (["2611.27274"], [])


def test_parse_links_one_per_line_skips_blank_lines_and_keeps_order():
    text = "2401.05678\n\n   \nhttps://arxiv.org/abs/2310.01234\n"
    assert parse_links(text) == (["2401.05678", "2310.01234"], [])


def test_parse_links_removes_duplicates_even_when_versions_differ():
    text = "2310.01234\nhttps://arxiv.org/abs/2310.01234v2\nhttps://arxiv.org/pdf/2310.01234.pdf"
    assert parse_links(text) == (["2310.01234"], [])


def test_parse_links_reports_lines_without_an_id():
    text = "2310.01234\nnot a link\nhttps://example.com/paper\nmath/0601001"
    ids, bad = parse_links(text)
    assert ids == ["2310.01234"]
    # The old-style id is a known limitation, so it lands here too.
    assert bad == ["not a link", "https://example.com/paper", "math/0601001"]


def test_parse_links_rejects_numbers_that_are_too_long():
    assert parse_links("2310.012345") == ([], ["2310.012345"])


def test_parse_links_empty_text():
    assert parse_links("") == ([], [])


# ---- parse_metadata ------------------------------------------------------------------------


def test_parse_metadata_from_saved_response():
    meta = parse_metadata(FIXTURE.read_text(encoding="utf-8"))
    assert meta.arxiv_id == "2611.27274"  # no version suffix
    assert meta.title == "Nonlinear Shrinkage for Higher Moments Estimation in Large Portfolios"
    assert meta.authors == ["Paul Ruelloux", "Christian Bongiorno", "Damien Challet"]
    assert meta.published == date(2026, 11, 20)
    assert meta.abstract.startswith("Portfolio risk is not limited to the variance of returns.")
    assert meta.arxiv_url == "https://arxiv.org/abs/2611.27274"


def test_parse_metadata_uses_the_primary_category():
    # The paper is also tagged q-fin.RM and q-fin.ST; only q-fin.PM is primary.
    meta = parse_metadata(FIXTURE.read_text(encoding="utf-8"))
    assert meta.primary_category == "q-fin.PM"


def test_parse_metadata_joins_wrapped_lines_into_one():
    xml = FIXTURE.read_text(encoding="utf-8").replace(
        "Nonlinear Shrinkage for Higher",
        "Nonlinear Shrinkage\n      for   Higher",
    )
    meta = parse_metadata(xml)
    assert meta.title == "Nonlinear Shrinkage for Higher Moments Estimation in Large Portfolios"


def test_parse_metadata_no_entry_raises_not_found():
    empty_feed = '<feed xmlns="http://www.w3.org/2005/Atom"><title>arXiv Query</title></feed>'
    with pytest.raises(ValueError, match="paper not found"):
        parse_metadata(empty_feed)


def test_parse_metadata_error_entry_raises_not_found():
    error_feed = (
        '<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
        "<id>http://arxiv.org/api/errors#incorrect_id_format_for_1234</id>"
        "<title>Error</title></entry></feed>"
    )
    with pytest.raises(ValueError, match="paper not found"):
        parse_metadata(error_feed)


# ---- flatten_source ------------------------------------------------------------------------

SINGLE_FILE = r"""\documentclass{article}
\usepackage{amsmath}
\begin{document}
\section{Intro}
Hello world.
\end{document}
"""


def test_flatten_single_gzipped_tex_file(make_gz):
    body = flatten_source(make_gz(SINGLE_FILE))
    assert body == "\\section{Intro}\nHello world."  # only what is inside the document


def test_flatten_multi_file_paper_inlines_input_and_include(make_tar_gz):
    raw = make_tar_gz(
        {
            "main.tex": "\\documentclass{article}\n\\begin{document}\n"
            "\\input{intro}\n\\include{sections/methods.tex}\n\\end{document}\n",
            "intro.tex": "\\section{Intro} Intro text.",
            "sections/methods.tex": "\\section{Methods} Uses \\input{formula} inside.",
            "formula.tex": "$x^2$",
        }
    )
    body = flatten_source(raw)
    assert "Intro text." in body
    assert "\\section{Methods} Uses $x^2$ inside." in body  # nested input is inlined too
    assert "\\input" not in body and "\\include" not in body


def test_flatten_picks_the_file_with_documentclass(make_tar_gz):
    raw = make_tar_gz(
        {
            "notes.tex": "just some notes",
            "paper.tex": SINGLE_FILE,
        }
    )
    assert "Hello world." in flatten_source(raw)


def test_flatten_missing_input_file_becomes_empty(make_tar_gz):
    raw = make_tar_gz(
        {"main.tex": "\\documentclass{article}\\begin{document}A\\input{nothere}B\\end{document}"}
    )
    assert flatten_source(raw) == "AB"


def test_flatten_strips_comments_but_keeps_escaped_percent(make_gz):
    tex = (
        "\\documentclass{article}\\begin{document}\n"
        "Growth was 5\\% last year. % this is a comment\n"
        "% \\input{secret}\n"
        "Next line.\n\\end{document}"
    )
    body = flatten_source(make_gz(tex))
    assert "comment" not in body and "secret" not in body
    assert "Growth was 5\\% last year." in body
    assert "Next line." in body


def test_flatten_cuts_at_the_bibliography(make_gz):
    tex = (
        "\\documentclass{article}\\begin{document}Body text.\n"
        "\\bibliographystyle{plain}\n\\bibliography{refs}\n\\end{document}"
    )
    assert flatten_source(make_gz(tex)).startswith("Body text.")
    assert "bibliography{refs}" not in flatten_source(make_gz(tex))


def test_flatten_pdf_only_source_raises():
    with pytest.raises(ValueError, match="PDF-only"):
        flatten_source(b"%PDF-1.5 pretend pdf bytes")


def test_flatten_gzipped_pdf_only_source_raises(make_gz):
    with pytest.raises(ValueError, match="PDF-only"):
        flatten_source(make_gz("%PDF-1.5 pretend pdf bytes"))


def test_flatten_without_documentclass_raises(make_tar_gz):
    with pytest.raises(ValueError, match="no main .tex"):
        flatten_source(make_tar_gz({"a.tex": "no class here"}))
