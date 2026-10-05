from dataclasses import dataclass
from pathlib import Path


@dataclass
class ParsedDocument:
    filename: str
    content_type: str
    text: str


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
    ".md",
}

MAX_PDF_PAGES = 200
MAX_EXTRACTED_TEXT_CHARS = 2_000_000
MAX_DOCX_PARAGRAPHS = 10_000


def parse_document(
    file_path: str | Path,
    content_type: str,
) -> ParsedDocument:
    path = Path(file_path)

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {path.suffix}"
        )

    if not path.is_file():
        raise ValueError(
            "Document file does not exist."
        )

    extension = path.suffix.lower()

    if extension == ".pdf":
        text = _parse_pdf(path)
    elif extension == ".docx":
        text = _parse_docx(path)
    elif extension in {".txt", ".md"}:
        text = _parse_text(path)
    else:
        raise ValueError(
            f"Unsupported file type: {extension}"
        )

    normalized_text = _normalize_text(text)

    if not normalized_text:
        raise ValueError(
            "The document contains no extractable text."
        )

    if len(normalized_text) > MAX_EXTRACTED_TEXT_CHARS:
        raise ValueError(
            "The document contains too much extracted text."
        )

    return ParsedDocument(
        filename=path.name,
        content_type=content_type,
        text=normalized_text,
    )


def _parse_pdf(path: Path) -> str:
    import fitz

    pages: list[str] = []

    try:
        with fitz.open(path) as document:
            page_count = len(document)

            if page_count > MAX_PDF_PAGES:
                raise ValueError(
                    "PDF contains too many pages."
                )

            for page in document:
                pages.append(page.get_text())

    except ValueError:
        raise

    except Exception as exc:
        raise ValueError(
            "The PDF document could not be parsed."
        ) from exc

    return "\n\n".join(pages)


def _parse_docx(path: Path) -> str:
    from docx import Document

    try:
        document = Document(path)

        if len(document.paragraphs) > MAX_DOCX_PARAGRAPHS:
            raise ValueError(
                "DOCX document contains too many paragraphs."
            )

        paragraphs = [
            paragraph.text
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        ]

        return "\n\n".join(paragraphs)

    except ValueError:
        raise

    except Exception as exc:
        raise ValueError(
            "The DOCX document could not be parsed."
        ) from exc


def _parse_text(path: Path) -> str:
    try:
        return path.read_text(
            encoding="utf-8",
            errors="replace",
        )

    except OSError as exc:
        raise ValueError(
            "The text document could not be read."
        ) from exc


def _normalize_text(text: str) -> str:
    lines = [
        line.strip()
        for line in text.splitlines()
    ]

    normalized_text = "\n".join(
        line
        for line in lines
        if line
    ).strip()

    return normalized_text