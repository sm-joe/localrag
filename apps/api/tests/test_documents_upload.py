from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import tempfile

import pytest
from fastapi import UploadFile

from app.routes import documents


class FakeIngestionService:
    def __init__(self):
        self.calls = []

    def ingest(
        self,
        file_path,
        content_type,
        original_filename,
    ):
        self.calls.append(
            {
                "file_path": Path(file_path),
                "content_type": content_type,
                "original_filename": original_filename,
            }
        )

        return SimpleNamespace(
            document_id="doc-test-123",
            filename=original_filename,
            chunks=2,
            already_indexed=False,
        )


def create_upload_file(
    filename: str,
    content: bytes,
    content_type: str = "text/plain",
) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers={
            "content-type": content_type,
        },
    )


@pytest.mark.asyncio
async def test_upload_accepts_supported_txt_file(
    monkeypatch,
):
    fake_service = FakeIngestionService()

    monkeypatch.setattr(
        documents,
        "create_ingestion_service",
        lambda: fake_service,
    )

    upload = create_upload_file(
        filename="document.txt",
        content=b"LocalRAG upload test.",
        content_type="text/plain",
    )

    response = await documents.upload_document(
        file=upload,
    )

    assert response.document_id == "doc-test-123"
    assert response.filename == "document.txt"
    assert response.chunks == 2
    assert response.status == "indexed"

    assert len(fake_service.calls) == 1

    call = fake_service.calls[0]

    assert call["original_filename"] == "document.txt"
    assert call["content_type"] == "text/plain"

    assert not call["file_path"].exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename,content_type",
    [
        (
            "document.pdf",
            "application/pdf",
        ),
        (
            "document.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        (
            "document.txt",
            "text/plain",
        ),
        (
            "document.md",
            "text/markdown",
        ),
    ],
)
async def test_upload_accepts_supported_extensions(
    monkeypatch,
    filename,
    content_type,
):
    fake_service = FakeIngestionService()

    monkeypatch.setattr(
        documents,
        "create_ingestion_service",
        lambda: fake_service,
    )

    if filename.endswith(".pdf"):
        import fitz

        pdf = fitz.open()
        page = pdf.new_page()
        page.insert_text(
            (72, 72),
            "LocalRAG PDF test.",
        )

        pdf_bytes = pdf.tobytes()
        pdf.close()

        content = pdf_bytes

    elif filename.endswith(".docx"):
        from docx import Document

        document = Document()
        document.add_paragraph(
            "LocalRAG DOCX test."
        )

        buffer = BytesIO()
        document.save(buffer)

        content = buffer.getvalue()

    else:
        content = b"LocalRAG text test."

    upload = create_upload_file(
        filename=filename,
        content=content,
        content_type=content_type,
    )

    response = await documents.upload_document(
        file=upload,
    )

    assert response.status == "indexed"
    assert response.filename == filename

    assert len(fake_service.calls) == 1

    assert (
        fake_service.calls[0]["original_filename"]
        == filename
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename",
    [
        "document.exe",
        "document.js",
        "document.html",
        "document.zip",
        "document.py",
    ],
)
async def test_upload_rejects_unsupported_extensions(
    filename,
):
    upload = create_upload_file(
        filename=filename,
        content=b"unsupported content",
        content_type="application/octet-stream",
    )

    with pytest.raises(
        documents.HTTPException,
    ) as exc_info:
        await documents.upload_document(
            file=upload,
        )

    assert exc_info.value.status_code == 400
    assert "Unsupported file type" in str(
        exc_info.value.detail
    )


@pytest.mark.asyncio
async def test_upload_rejects_empty_file():
    upload = create_upload_file(
        filename="empty.txt",
        content=b"",
        content_type="text/plain",
    )

    with pytest.raises(
        documents.HTTPException,
    ) as exc_info:
        await documents.upload_document(
            file=upload,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        "Uploaded file is empty."
    )


@pytest.mark.asyncio
async def test_upload_rejects_file_over_10_mib():
    content = b"A" * (
        documents.MAX_UPLOAD_SIZE_BYTES + 1
    )

    upload = create_upload_file(
        filename="large.txt",
        content=content,
        content_type="text/plain",
    )

    with pytest.raises(
        documents.HTTPException,
    ) as exc_info:
        await documents.upload_document(
            file=upload,
        )

    assert exc_info.value.status_code == 413
    assert "too large" in str(
        exc_info.value.detail
    ).lower()


@pytest.mark.asyncio
async def test_upload_accepts_file_at_10_mib_limit(
    monkeypatch,
):
    fake_service = FakeIngestionService()

    monkeypatch.setattr(
        documents,
        "create_ingestion_service",
        lambda: fake_service,
    )

    content = b"A" * documents.MAX_UPLOAD_SIZE_BYTES

    upload = create_upload_file(
        filename="maximum.txt",
        content=content,
        content_type="text/plain",
    )

    response = await documents.upload_document(
        file=upload,
    )

    assert response.status == "indexed"
    assert response.filename == "maximum.txt"

    assert len(fake_service.calls) == 1
    assert (
        fake_service.calls[0]["original_filename"]
        == "maximum.txt"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename,expected",
    [
        (
            "../../secret.txt",
            "secret.txt",
        ),
        (
            "..\\..\\secret.txt",
            "secret.txt",
        ),
        (
            "/tmp/secret.txt",
            "secret.txt",
        ),
        (
            "C:\\Windows\\Temp\\secret.txt",
            "secret.txt",
        ),
    ],
)
async def test_upload_sanitizes_filename_path(
    monkeypatch,
    filename,
    expected,
):
    fake_service = FakeIngestionService()

    monkeypatch.setattr(
        documents,
        "create_ingestion_service",
        lambda: fake_service,
    )

    upload = create_upload_file(
        filename=filename,
        content=b"safe content",
        content_type="text/plain",
    )

    response = await documents.upload_document(
        file=upload,
    )

    assert response.filename == expected

    assert len(fake_service.calls) == 1
    assert (
        fake_service.calls[0]["original_filename"]
        == expected
    )

    stored_path = fake_service.calls[0]["file_path"]

    assert not stored_path.exists()


@pytest.mark.asyncio
async def test_upload_rejects_filename_over_255_characters():
    filename = (
        ("a" * 252)
        + ".txt"
    )

    upload = create_upload_file(
        filename=filename,
        content=b"test content",
        content_type="text/plain",
    )

    with pytest.raises(
        documents.HTTPException,
    ) as exc_info:
        await documents.upload_document(
            file=upload,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        "Filename is too long."
    )


@pytest.mark.asyncio
async def test_upload_rejects_missing_filename():
    upload = UploadFile(
        file=BytesIO(b"test content"),
        filename=None,
    )

    with pytest.raises(
        documents.HTTPException,
    ) as exc_info:
        await documents.upload_document(
            file=upload,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        "Filename is required."
    )


@pytest.mark.asyncio
async def test_upload_uses_default_content_type(
    monkeypatch,
):
    fake_service = FakeIngestionService()

    monkeypatch.setattr(
        documents,
        "create_ingestion_service",
        lambda: fake_service,
    )

    upload = UploadFile(
        file=BytesIO(b"LocalRAG content"),
        filename="document.txt",
    )

    response = await documents.upload_document(
        file=upload,
    )

    assert response.status == "indexed"

    assert len(fake_service.calls) == 1
    assert (
        fake_service.calls[0]["content_type"]
        == "application/octet-stream"
    )


@pytest.mark.asyncio
async def test_upload_returns_already_indexed_status(
    monkeypatch,
):
    class DuplicateIngestionService(
        FakeIngestionService
    ):
        def ingest(
            self,
            file_path,
            content_type,
            original_filename,
        ):
            self.calls.append(
                {
                    "file_path": Path(file_path),
                    "content_type": content_type,
                    "original_filename": original_filename,
                }
            )

            return SimpleNamespace(
                document_id="doc-existing",
                filename=original_filename,
                chunks=2,
                already_indexed=True,
            )

    fake_service = DuplicateIngestionService()

    monkeypatch.setattr(
        documents,
        "create_ingestion_service",
        lambda: fake_service,
    )

    upload = create_upload_file(
        filename="duplicate.txt",
        content=b"already indexed",
        content_type="text/plain",
    )

    response = await documents.upload_document(
        file=upload,
    )

    assert response.document_id == "doc-existing"
    assert response.status == "already_indexed"
    assert response.filename == "duplicate.txt"


@pytest.mark.asyncio
async def test_upload_cleans_temporary_file_when_ingestion_fails(
    monkeypatch,
):
    captured_path = None

    class FailingIngestionService:
        def ingest(
            self,
            file_path,
            content_type,
            original_filename,
        ):
            nonlocal captured_path

            captured_path = Path(file_path)

            assert captured_path.exists()

            raise ValueError(
                "Document contains no extractable text."
            )

    monkeypatch.setattr(
        documents,
        "create_ingestion_service",
        lambda: FailingIngestionService(),
    )

    upload = create_upload_file(
        filename="invalid.txt",
        content=b"invalid content",
        content_type="text/plain",
    )

    with pytest.raises(
        documents.HTTPException,
    ) as exc_info:
        await documents.upload_document(
            file=upload,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        "Document contains no extractable text."
    )

    assert captured_path is not None
    assert not captured_path.exists()


@pytest.mark.asyncio
async def test_upload_cleans_temporary_file_when_ingestion_crashes(
    monkeypatch,
):
    captured_path = None

    class FailingIngestionService:
        def ingest(
            self,
            file_path,
            content_type,
            original_filename,
        ):
            nonlocal captured_path

            captured_path = Path(file_path)

            assert captured_path.exists()

            raise RuntimeError(
                "unexpected ingestion failure"
            )

    monkeypatch.setattr(
        documents,
        "create_ingestion_service",
        lambda: FailingIngestionService(),
    )

    upload = create_upload_file(
        filename="failure.txt",
        content=b"test content",
        content_type="text/plain",
    )

    with pytest.raises(
        documents.HTTPException,
    ) as exc_info:
        await documents.upload_document(
            file=upload,
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == (
        "Document ingestion failed."
    )

    assert captured_path is not None
    assert not captured_path.exists()


@pytest.mark.asyncio
async def test_upload_rejects_fake_pdf(
    monkeypatch,
):
    fake_service = FakeIngestionService()

    monkeypatch.setattr(
        documents,
        "create_ingestion_service",
        lambda: fake_service,
    )

    upload = create_upload_file(
        filename="fake.pdf",
        content=b"this is not a pdf",
        content_type="application/pdf",
    )

    with pytest.raises(
        documents.HTTPException,
    ) as exc_info:
        await documents.upload_document(
            file=upload,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        "Uploaded file is not a valid PDF."
    )

    assert fake_service.calls == []


@pytest.mark.asyncio
async def test_upload_accepts_real_pdf(
    monkeypatch,
):
    import fitz

    fake_service = FakeIngestionService()

    monkeypatch.setattr(
        documents,
        "create_ingestion_service",
        lambda: fake_service,
    )

    with tempfile.NamedTemporaryFile(
        suffix=".pdf",
        delete=False,
    ) as temporary_file:
        pdf_path = Path(
            temporary_file.name
        )

    try:
        pdf = fitz.open()
        page = pdf.new_page()
        page.insert_text(
            (72, 72),
            "LocalRAG content validation test.",
        )
        pdf.save(pdf_path)
        pdf.close()

        upload = create_upload_file(
            filename="valid.pdf",
            content=pdf_path.read_bytes(),
            content_type="application/pdf",
        )

        response = await documents.upload_document(
            file=upload,
        )

        assert response.status == "indexed"
        assert response.filename == "valid.pdf"

    finally:
        pdf_path.unlink(
            missing_ok=True
        )


@pytest.mark.asyncio
async def test_upload_rejects_fake_docx(
    monkeypatch,
):
    fake_service = FakeIngestionService()

    monkeypatch.setattr(
        documents,
        "create_ingestion_service",
        lambda: fake_service,
    )

    upload = create_upload_file(
        filename="fake.docx",
        content=b"this is not a docx",
        content_type=(
            "application/vnd.openxmlformats-"
            "officedocument.wordprocessingml.document"
        ),
    )

    with pytest.raises(
        documents.HTTPException,
    ) as exc_info:
        await documents.upload_document(
            file=upload,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        "Uploaded file is not a valid DOCX."
    )

    assert fake_service.calls == []


@pytest.mark.asyncio
async def test_upload_rejects_invalid_utf8_text(
    monkeypatch,
):
    fake_service = FakeIngestionService()

    monkeypatch.setattr(
        documents,
        "create_ingestion_service",
        lambda: fake_service,
    )

    upload = create_upload_file(
        filename="invalid.txt",
        content=b"\xff\xfe\xfa\xfb",
        content_type="text/plain",
    )

    with pytest.raises(
        documents.HTTPException,
    ) as exc_info:
        await documents.upload_document(
            file=upload,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        "Uploaded text file is not valid UTF-8."
    )

    assert fake_service.calls == []


@pytest.mark.asyncio
async def test_upload_rejects_pdf_with_text_content(
    monkeypatch,
):
    fake_service = FakeIngestionService()

    monkeypatch.setattr(
        documents,
        "create_ingestion_service",
        lambda: fake_service,
    )

    upload = create_upload_file(
        filename="document.pdf",
        content=b"LocalRAG is not a PDF.",
        content_type="application/pdf",
    )

    with pytest.raises(
        documents.HTTPException,
    ) as exc_info:
        await documents.upload_document(
            file=upload,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        "Uploaded file is not a valid PDF."
    )

    assert fake_service.calls == []


@pytest.mark.asyncio
async def test_upload_rejects_docx_with_pdf_content(
    monkeypatch,
):
    fake_service = FakeIngestionService()

    monkeypatch.setattr(
        documents,
        "create_ingestion_service",
        lambda: fake_service,
    )

    upload = create_upload_file(
        filename="document.docx",
        content=b"%PDF-1.7\nfake",
        content_type=(
            "application/vnd.openxmlformats-"
            "officedocument.wordprocessingml.document"
        ),
    )

    with pytest.raises(
        documents.HTTPException,
    ) as exc_info:
        await documents.upload_document(
            file=upload,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        "Uploaded file is not a valid DOCX."
    )

    assert fake_service.calls == []