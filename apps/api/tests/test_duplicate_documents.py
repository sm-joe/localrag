from pathlib import Path

from app.services.ingestion import IngestionService


class FakeEmbeddingService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(
        self,
        text: str,
    ) -> list[float]:
        self.calls.append(text)

        return [
            0.1,
            0.2,
            0.3,
        ]


class FakeVectorStore:
    def __init__(
        self,
        existing_document: dict[str, str]
        | None = None,
    ) -> None:
        self.existing_document = (
            existing_document
        )
        self.upsert_calls = 0
        self.ensure_collection_calls = 0
        self.points = []

    def find_document_by_hash(
        self,
        document_hash: str,
    ) -> dict[str, str] | None:
        return self.existing_document

    def ensure_collection(
        self,
        vector_size: int,
    ) -> None:
        self.ensure_collection_calls += 1

    def upsert(self, points) -> None:
        self.upsert_calls += 1
        self.points.extend(points)


def test_duplicate_document_is_not_reindexed(
    tmp_path: Path,
) -> None:
    document = tmp_path / "document.txt"

    document.write_text(
        "LocalRAG uses Qdrant for vector storage.",
        encoding="utf-8",
    )

    embedding_service = FakeEmbeddingService()

    vector_store = FakeVectorStore(
        existing_document={
            "document_id": "existing-document-id",
            "filename": "original.txt",
        }
    )

    service = IngestionService(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    result = service.ingest(
        file_path=document,
        content_type="text/plain",
        original_filename="duplicate.txt",
    )

    assert result.document_id == (
        "existing-document-id"
    )

    assert result.filename == "original.txt"

    assert result.chunks == 0

    assert result.already_indexed is True

    assert embedding_service.calls == []

    assert vector_store.upsert_calls == 0

    assert vector_store.ensure_collection_calls == 0


def test_new_document_is_indexed(
    tmp_path: Path,
) -> None:
    document = tmp_path / "document.txt"

    document.write_text(
        "LocalRAG uses Qdrant for vector storage.",
        encoding="utf-8",
    )

    embedding_service = FakeEmbeddingService()

    vector_store = FakeVectorStore()

    service = IngestionService(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    result = service.ingest(
        file_path=document,
        content_type="text/plain",
        original_filename="document.txt",
    )

    assert result.already_indexed is False

    assert result.document_id

    assert result.filename == "document.txt"

    assert result.chunks == 1

    assert len(
        embedding_service.calls
    ) == 1

    assert vector_store.ensure_collection_calls == 1

    assert vector_store.upsert_calls == 1

    assert len(vector_store.points) == 1

    payload = (
        vector_store.points[0].payload
    )

    assert payload["document_id"] == (
        result.document_id
    )

    assert payload["filename"] == (
        "document.txt"
    )

    assert payload["document_hash"]

    assert len(
        payload["document_hash"]
    ) == 64


def test_same_content_with_different_filename_is_duplicate(
    tmp_path: Path,
) -> None:
    document = tmp_path / "document.txt"

    document.write_text(
        "The same content should produce "
        "the same SHA-256 hash.",
        encoding="utf-8",
    )

    embedding_service = FakeEmbeddingService()

    vector_store = FakeVectorStore(
        existing_document={
            "document_id": "existing-id",
            "filename": "first-name.txt",
        }
    )

    service = IngestionService(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    result = service.ingest(
        file_path=document,
        content_type="text/plain",
        original_filename="different-name.txt",
    )

    assert result.already_indexed is True

    assert result.document_id == "existing-id"

    assert result.filename == "first-name.txt"

    assert embedding_service.calls == []

    assert vector_store.upsert_calls == 0


def test_different_content_is_not_treated_as_duplicate(
    tmp_path: Path,
) -> None:
    document = tmp_path / "document.txt"

    document.write_text(
        "This is different content.",
        encoding="utf-8",
    )

    embedding_service = FakeEmbeddingService()

    vector_store = FakeVectorStore()

    service = IngestionService(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    result = service.ingest(
        file_path=document,
        content_type="text/plain",
        original_filename="document.txt",
    )

    assert result.already_indexed is False

    assert vector_store.upsert_calls == 1