from pathlib import Path
from unittest.mock import MagicMock

from app.services.ingestion import IngestionService


def test_ingest_document(tmp_path: Path) -> None:
    file_path = tmp_path / "test.txt"

    file_path.write_text(
        "LocalRAG is a portable RAG assistant. "
        "It uses embeddings and vector search.",
        encoding="utf-8",
    )

    embedding_service = MagicMock()

    embedding_service.embed.return_value = [
        0.1,
        0.2,
        0.3,
    ]

    vector_store = MagicMock()

    service = IngestionService(
        embedding_service=embedding_service,
        vector_store=vector_store,
        chunk_size=100,
        chunk_overlap=10,
    )

    result = service.ingest(
        file_path=file_path,
        content_type="text/plain",
    )

    assert result.filename == "test.txt"
    assert result.chunks > 0
    assert result.document_id

    vector_store.ensure_collection.assert_called_once_with(
        vector_size=3
    )

    vector_store.upsert.assert_called_once()

    points = (
        vector_store.upsert.call_args.args[0]
    )

    assert len(points) == result.chunks

    for point in points:
        assert point.payload["document_id"] == (
            result.document_id
        )

        assert point.payload["filename"] == (
            "test.txt"
        )

        assert point.payload["text"]


def test_ingest_rejects_empty_document(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "empty.txt"

    file_path.write_text(
        "",
        encoding="utf-8",
    )

    embedding_service = MagicMock()
    vector_store = MagicMock()

    service = IngestionService(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    try:
        service.ingest(
            file_path=file_path,
            content_type="text/plain",
        )
    except ValueError as exc:
        assert (
            "no extractable text"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Expected ValueError"
        )