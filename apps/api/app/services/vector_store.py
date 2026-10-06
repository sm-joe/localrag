from collections.abc import Sequence
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models


class VectorStore:
    def __init__(
        self,
        host: str,
        port: int,
        collection_name: str,
    ) -> None:
        self.client = QdrantClient(
            host=host,
            port=port,
        )
        self.collection_name = collection_name

    def ensure_collection(
        self,
        vector_size: int,
    ) -> None:
        collections = self.client.get_collections()

        exists = any(
            collection.name == self.collection_name
            for collection in collections.collections
        )

        if exists:
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    def upsert(
        self,
        points: Sequence[models.PointStruct],
    ) -> None:
        if not points:
            return

        self.client.upsert(
            collection_name=self.collection_name,
            points=list(points),
        )

    def search(
        self,
        vector: list[float],
        limit: int = 5,
    ) -> list[Any]:
        if not vector:
            raise ValueError(
                "Search vector cannot be empty."
            )

        if limit <= 0:
            raise ValueError(
                "Search limit must be greater than zero."
            )

        return self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=limit,
        ).points

    def list_points(
        self,
        limit: int = 100,
    ) -> list[Any]:
        if limit <= 0:
            raise ValueError(
                "Limit must be greater than zero."
            )

        records, _ = self.client.scroll(
            collection_name=self.collection_name,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        return records

    def find_document_by_hash(
        self,
        document_hash: str,
    ) -> dict[str, str] | None:
        normalized_hash = document_hash.strip()

        if not normalized_hash:
            raise ValueError(
                "Document hash cannot be empty."
            )

        collections = self.client.get_collections()

        collection_exists = any(
            collection.name == self.collection_name
            for collection in collections.collections
        )

        if not collection_exists:
            return None

        records, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_hash",
                        match=models.MatchValue(
                            value=normalized_hash,
                        ),
                    )
                ]
            ),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )

        if not records:
            return None

        payload = records[0].payload or {}

        document_id = payload.get("document_id")
        filename = payload.get("filename")

        if not document_id:
            return None

        return {
            "document_id": str(document_id),
            "filename": str(
                filename or "unknown"
            ),
        }

    def find_points_by_filename(
        self,
        filename: str,
        limit: int = 100,
    ) -> list[Any]:
        normalized_filename = filename.strip()

        if not normalized_filename:
            raise ValueError(
                "Filename cannot be empty."
            )

        if limit <= 0:
            raise ValueError(
                "Limit must be greater than zero."
            )

        records, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="filename",
                        match=models.MatchValue(
                            value=normalized_filename,
                        ),
                    )
                ]
            ),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        return records

    def delete_document(
        self,
        document_id: str,
    ) -> None:
        if not document_id.strip():
            raise ValueError(
                "Document ID cannot be empty."
            )

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(
                                value=document_id,
                            ),
                        )
                    ]
                )
            ),
        )