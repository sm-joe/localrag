from dataclasses import dataclass

import pytest

from app.services.retrieval import RetrievalService


@dataclass
class FakeEmbeddingService:
    calls: list[str]

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [0.1, 0.2, 0.3]


@dataclass
class FakeResult:
    score: float
    payload: dict


class FakeVectorStore:
    def __init__(self) -> None:
        self.calls: list[tuple[list[float], int]] = []

    def search(
        self,
        vector: list[float],
        limit: int,
    ) -> list[FakeResult]:
        self.calls.append((vector, limit))

        return [
            FakeResult(
                score=0.92,
                payload={
                    "document_id": "doc-123",
                    "filename": "rag-test.txt",
                    "content_type": "text/plain",
                    "chunk_id": 0,
                    "text": (
                        "LocalRAG is a portable RAG "
                        "application."
                    ),
                    "start_char": 0,
                    "end_char": 52,
                },
            ),
            FakeResult(
                score=0.81,
                payload={
                    "document_id": "doc-123",
                    "filename": "rag-test.txt",
                    "content_type": "text/plain",
                    "chunk_id": 1,
                    "text": (
                        "Qdrant stores vector embeddings "
                        "for retrieval."
                    ),
                    "start_char": 52,
                    "end_char": 106,
                },
            ),
        ]


def test_retrieve_returns_chunks():
    embedding_service = FakeEmbeddingService(
        calls=[]
    )
    vector_store = FakeVectorStore()

    service = RetrievalService(
        embedding_service=embedding_service,
        vector_store=vector_store,
        top_k=5,
    )

    result = service.retrieve(
        "What is LocalRAG?"
    )

    assert len(result.chunks) == 2

    assert result.chunks[0].document_id == "doc-123"
    assert result.chunks[0].filename == "rag-test.txt"
    assert result.chunks[0].chunk_id == 0
    assert result.chunks[0].score == 0.92

    assert result.chunks[1].chunk_id == 1
    assert result.chunks[1].score == 0.81


def test_retrieve_embeds_query_and_searches_vector_store():
    embedding_service = FakeEmbeddingService(
        calls=[]
    )
    vector_store = FakeVectorStore()

    service = RetrievalService(
        embedding_service=embedding_service,
        vector_store=vector_store,
        top_k=3,
    )

    result = service.retrieve(
        "  What is Qdrant?  "
    )

    assert embedding_service.calls == [
        "What is Qdrant?"
    ]

    assert vector_store.calls == [
        ([0.1, 0.2, 0.3], 3)
    ]

    assert result.performance.embedding_ms >= 0
    assert result.performance.search_ms >= 0
    assert result.performance.total_ms >= 0


def test_retrieve_allows_custom_limit():
    embedding_service = FakeEmbeddingService(
        calls=[]
    )
    vector_store = FakeVectorStore()

    service = RetrievalService(
        embedding_service=embedding_service,
        vector_store=vector_store,
        top_k=5,
    )

    result = service.retrieve(
        "What is Qdrant?",
        limit=1,
    )

    assert vector_store.calls == [
        ([0.1, 0.2, 0.3], 1)
    ]

    assert (
        result.diagnostics.requested_limit
        == 1
    )


def test_retrieve_rejects_empty_query():
    embedding_service = FakeEmbeddingService(
        calls=[]
    )
    vector_store = FakeVectorStore()

    service = RetrievalService(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    with pytest.raises(
        ValueError,
        match="Query cannot be empty",
    ):
        service.retrieve("   ")


def test_retrieval_rejects_invalid_top_k():
    embedding_service = FakeEmbeddingService(
        calls=[]
    )
    vector_store = FakeVectorStore()

    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero",
    ):
        RetrievalService(
            embedding_service=embedding_service,
            vector_store=vector_store,
            top_k=0,
        )


def test_retrieval_rejects_invalid_limit():
    embedding_service = FakeEmbeddingService(
        calls=[]
    )
    vector_store = FakeVectorStore()

    service = RetrievalService(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    with pytest.raises(
        ValueError,
        match="Search limit must be greater than zero",
    ):
        service.retrieve(
            "What is Qdrant?",
            limit=0,
        )


def test_retrieval_skips_invalid_payload():
    embedding_service = FakeEmbeddingService(
        calls=[]
    )

    class InvalidPayloadVectorStore:
        def search(
            self,
            vector: list[float],
            limit: int,
        ) -> list[FakeResult]:
            return [
                FakeResult(
                    score=0.95,
                    payload={
                        "document_id": "doc-123",
                        "text": "Incomplete payload",
                    },
                )
            ]

    service = RetrievalService(
        embedding_service=embedding_service,
        vector_store=InvalidPayloadVectorStore(),
    )

    result = service.retrieve(
        "What is LocalRAG?"
    )

    assert result.chunks == []
    assert result.diagnostics.candidate_count == 1
    assert result.diagnostics.returned_count == 0
    assert result.diagnostics.filtered_count == 1
    assert result.diagnostics.top_score is None
    assert result.diagnostics.bottom_score is None
    assert result.diagnostics.has_context is False


def test_retrieve_filters_results_below_threshold():
    embedding_service = FakeEmbeddingService(
        calls=[]
    )
    vector_store = FakeVectorStore()

    service = RetrievalService(
        embedding_service=embedding_service,
        vector_store=vector_store,
        score_threshold=0.85,
    )

    result = service.retrieve(
        "What is LocalRAG?"
    )

    assert len(result.chunks) == 1
    assert result.chunks[0].score == 0.92

    assert result.diagnostics.candidate_count == 2
    assert result.diagnostics.returned_count == 1
    assert result.diagnostics.filtered_count == 1
    assert result.diagnostics.top_score == 0.92
    assert result.diagnostics.bottom_score == 0.92
    assert result.diagnostics.has_context is True


def test_retrieval_rejects_invalid_threshold():
    embedding_service = FakeEmbeddingService(
        calls=[]
    )
    vector_store = FakeVectorStore()

    with pytest.raises(
        ValueError,
        match="score_threshold must be between",
    ):
        RetrievalService(
            embedding_service=embedding_service,
            vector_store=vector_store,
            score_threshold=1.1,
        )


def test_retrieval_diagnostics_track_all_scores():
    embedding_service = FakeEmbeddingService(
        calls=[]
    )
    vector_store = FakeVectorStore()

    service = RetrievalService(
        embedding_service=embedding_service,
        vector_store=vector_store,
        score_threshold=0.70,
    )

    result = service.retrieve(
        "What is LocalRAG?"
    )

    assert result.diagnostics.requested_limit == 5
    assert result.diagnostics.candidate_count == 2
    assert result.diagnostics.returned_count == 2
    assert result.diagnostics.filtered_count == 0
    assert result.diagnostics.top_score == 0.92
    assert result.diagnostics.bottom_score == 0.81
    assert result.diagnostics.has_context is True


def test_retrieval_performance_contains_all_timings():
    embedding_service = FakeEmbeddingService(
        calls=[]
    )
    vector_store = FakeVectorStore()

    service = RetrievalService(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    result = service.retrieve(
        "What is LocalRAG?"
    )

    assert (
        result.performance.embedding_ms
        >= 0
    )

    assert (
        result.performance.search_ms
        >= 0
    )

    assert (
        result.performance.total_ms
        >= result.performance.embedding_ms
    )