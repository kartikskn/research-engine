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
