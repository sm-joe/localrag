from pathlib import Path

import pytest

from app.services.parser import parse_document


def test_parse_text_file(tmp_path: Path) -> None:
    file_path = tmp_path / "example.txt"

    file_path.write_text(
        "Hello LocalRAG.\n\nThis is a test document.",
        encoding="utf-8",
    )

    result = parse_document(
        file_path,
        "text/plain",
    )

    assert result.filename == "example.txt"
    assert result.content_type == "text/plain"
    assert "Hello LocalRAG." in result.text
    assert "This is a test document." in result.text


def test_parse_markdown_file(tmp_path: Path) -> None:
    file_path = tmp_path / "example.md"

    file_path.write_text(
        "# LocalRAG\n\nRAG is useful.",
        encoding="utf-8",
    )

    result = parse_document(
        file_path,
        "text/markdown",
    )

    assert result.filename == "example.md"
    assert "# LocalRAG" in result.text


def test_reject_unsupported_file(tmp_path: Path) -> None:
    file_path = tmp_path / "example.exe"
    file_path.write_bytes(b"invalid")

    with pytest.raises(ValueError, match="Unsupported file type"):
        parse_document(
            file_path,
            "application/octet-stream",
        )