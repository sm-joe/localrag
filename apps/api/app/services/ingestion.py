import hashlib
import uuid
from pathlib import Path

from qdrant_client.http import models

from app.services.chunker import chunk_text
from app.services.embeddings import EmbeddingService
from app.services.parser import parse_document
from app.services.vector_store import VectorStore


class IngestionResult:
    def __init__(
        self,
        document_id: str,
        filename: str,
        chunks: int,
        already_indexed: bool = False,
    ) -> None:
        self.document_id = document_id
        self.filename = filename
        self.chunks = chunks
        self.already_indexed = already_indexed


class IngestionService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ) -> None:
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def ingest(
        self,
        file_path: str | Path,
        content_type: str,
        original_filename: str | None = None,
    ) -> IngestionResult:
        path = Path(file_path)

        if not path.is_file():
            raise ValueError(
                "Document file does not exist."
            )

        document_hash = self._calculate_hash(
            path
        )

        filename = (
            original_filename
            if original_filename
            else path.name
        )

        collections = self.vector_store.client.get_collections()

        collection_exists = any(
            collection.name
            == self.vector_store.collection_name
            for collection in collections.collections
        )

        if collection_exists:
            existing_document = (
                self.vector_store.find_document_by_hash(
                    document_hash
                )
            )

            if self._is_existing_document(
                existing_document
            ):
                return IngestionResult(
                    document_id=existing_document[
                        "document_id"
                    ],
                    filename=existing_document[
                        "filename"
                    ],
                    chunks=0,
                    already_indexed=True,
                )

        parsed = parse_document(
            path,
            content_type,
        )

        chunks = chunk_text(
            parsed.text,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

        if not chunks:
            raise ValueError(
                "Document produced no chunks."
            )

        document_id = str(uuid.uuid4())

        first_embedding = (
            self.embedding_service.embed(
                chunks[0].text
            )
        )

        self.vector_store.ensure_collection(
            vector_size=len(first_embedding)
        )

        points: list[models.PointStruct] = []

        first_point = models.PointStruct(
            id=str(uuid.uuid4()),
            vector=first_embedding,
            payload={
                "document_id": document_id,
                "document_hash": document_hash,
                "filename": filename,
                "content_type": parsed.content_type,
                "chunk_id": chunks[0].chunk_id,
                "text": chunks[0].text,
                "start_char": chunks[0].start_char,
                "end_char": chunks[0].end_char,
            },
        )

        points.append(first_point)

        for chunk in chunks[1:]:
            embedding = self.embedding_service.embed(
                chunk.text
            )

            points.append(
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "document_id": document_id,
                        "document_hash": document_hash,
                        "filename": filename,
                        "content_type": parsed.content_type,
                        "chunk_id": chunk.chunk_id,
                        "text": chunk.text,
                        "start_char": chunk.start_char,
                        "end_char": chunk.end_char,
                    },
                )
            )

        self.vector_store.upsert(points)

        return IngestionResult(
            document_id=document_id,
            filename=filename,
            chunks=len(chunks),
            already_indexed=False,
        )

    @staticmethod
    def _is_existing_document(
        document: object,
    ) -> bool:
        if not isinstance(document, dict):
            return False

        document_id = document.get(
            "document_id"
        )

        filename = document.get(
            "filename"
        )

        return bool(
            isinstance(document_id, str)
            and document_id.strip()
            and isinstance(filename, str)
            and filename.strip()
        )

    @staticmethod
    def _calculate_hash(
        path: Path,
    ) -> str:
        digest = hashlib.sha256()

        with path.open("rb") as document:
            for block in iter(
                lambda: document.read(1024 * 1024),
                b"",
            ):
                digest.update(block)

        return digest.hexdigest()