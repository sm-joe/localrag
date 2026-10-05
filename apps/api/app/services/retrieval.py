import re
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStore


@dataclass(frozen=True)
class RetrievedChunk:
    document_id: str
    filename: str
    content_type: str
    chunk_id: int
    text: str
    start_char: int
    end_char: int
    score: float


@dataclass(frozen=True)
class RetrievalDiagnostics:
    requested_limit: int
    candidate_count: int
    returned_count: int
    filtered_count: int
    top_candidate_score: float | None
    bottom_candidate_score: float | None
    top_score: float | None
    bottom_score: float | None
    has_context: bool


@dataclass(frozen=True)
class RetrievalPerformance:
    embedding_ms: float
    search_ms: float
    total_ms: float


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[RetrievedChunk]
    diagnostics: RetrievalDiagnostics
    performance: RetrievalPerformance


class RetrievalService:
    SUPPORTED_FILENAME_EXTENSIONS = (
        ".pdf",
        ".docx",
        ".txt",
        ".md",
    )

    FILENAME_PATTERN = re.compile(
        r"""
        (?:
            ["']([^"']+\.(?:pdf|docx|txt|md))
            ["']
        )
        |
        (?:
            ([^\s"'<>]+\.(?:pdf|docx|txt|md))
        )
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> None:
        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than zero"
            )

        if not 0.0 <= score_threshold <= 1.0:
            raise ValueError(
                "score_threshold must be between "
                "0.0 and 1.0"
            )

        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.top_k = top_k
        self.score_threshold = score_threshold

    def retrieve(
        self,
        query: str,
        limit: int | None = None,
    ) -> RetrievalResult:
        normalized_query = query.strip()

        if not normalized_query:
            raise ValueError(
                "Query cannot be empty"
            )

        search_limit = (
            self.top_k
            if limit is None
            else limit
        )

        if search_limit <= 0:
            raise ValueError(
                "Search limit must be greater than zero"
            )

        total_start = perf_counter()

        explicit_filename = self._extract_filename(
            normalized_query
        )

        if explicit_filename:
            filename_result = (
                self._retrieve_by_filename(
                    filename=explicit_filename,
                    limit=search_limit,
                    total_start=total_start,
                )
            )

            if filename_result is not None:
                return filename_result

        embedding_start = perf_counter()

        query_embedding = (
            self.embedding_service.embed(
                normalized_query
            )
        )

        embedding_ms = (
            perf_counter()
            - embedding_start
        ) * 1000

        search_start = perf_counter()

        results = self.vector_store.search(
            vector=query_embedding,
            limit=search_limit,
        )

        search_ms = (
            perf_counter()
            - search_start
        ) * 1000

        candidate_scores = [
            float(result.score)
            for result in results
        ]

        retrieved_chunks: list[RetrievedChunk] = []
        candidate_count = len(results)
        filtered_count = 0

        for result in results:
            score = float(result.score)

            if score < self.score_threshold:
                filtered_count += 1
                continue

            payload = result.payload or {}

            chunk = self._build_chunk(
                payload=payload,
                score=score,
            )

            if chunk is None:
                filtered_count += 1
                continue

            retrieved_chunks.append(chunk)

        scores = [
            chunk.score
            for chunk in retrieved_chunks
        ]

        diagnostics = RetrievalDiagnostics(
            requested_limit=search_limit,
            candidate_count=candidate_count,
            returned_count=len(
                retrieved_chunks
            ),
            filtered_count=filtered_count,
            top_candidate_score=(
                max(candidate_scores)
                if candidate_scores
                else None
            ),
            bottom_candidate_score=(
                min(candidate_scores)
                if candidate_scores
                else None
            ),
            top_score=(
                max(scores)
                if scores
                else None
            ),
            bottom_score=(
                min(scores)
                if scores
                else None
            ),
            has_context=bool(
                retrieved_chunks
            ),
        )

        performance = RetrievalPerformance(
            embedding_ms=round(
                embedding_ms,
                2,
            ),
            search_ms=round(
                search_ms,
                2,
            ),
            total_ms=round(
                (
                    perf_counter()
                    - total_start
                )
                * 1000,
                2,
            ),
        )

        return RetrievalResult(
            chunks=retrieved_chunks,
            diagnostics=diagnostics,
            performance=performance,
        )

    def _retrieve_by_filename(
        self,
        filename: str,
        limit: int,
        total_start: float,
    ) -> RetrievalResult | None:
        search_start = perf_counter()

        records = (
            self.vector_store.find_points_by_filename(
                filename=filename,
                limit=limit,
            )
        )

        search_ms = (
            perf_counter()
            - search_start
        ) * 1000

        if not records:
            return None

        records.sort(
            key=lambda record: int(
                (record.payload or {}).get(
                    "chunk_id",
                    0,
                )
            )
        )

        retrieved_chunks: list[RetrievedChunk] = []
        filtered_count = 0

        for record in records[:limit]:
            payload = record.payload or {}

            chunk = self._build_chunk(
                payload=payload,
                score=1.0,
            )

            if chunk is None:
                filtered_count += 1
                continue

            retrieved_chunks.append(chunk)

        scores = [
            chunk.score
            for chunk in retrieved_chunks
        ]

        diagnostics = RetrievalDiagnostics(
            requested_limit=limit,
            candidate_count=len(records),
            returned_count=len(
                retrieved_chunks
            ),
            filtered_count=filtered_count,
            top_candidate_score=(
                1.0
                if records
                else None
            ),
            bottom_candidate_score=(
                1.0
                if records
                else None
            ),
            top_score=(
                max(scores)
                if scores
                else None
            ),
            bottom_score=(
                min(scores)
                if scores
                else None
            ),
            has_context=bool(
                retrieved_chunks
            ),
        )

        performance = RetrievalPerformance(
            embedding_ms=0.0,
            search_ms=round(
                search_ms,
                2,
            ),
            total_ms=round(
                (
                    perf_counter()
                    - total_start
                )
                * 1000,
                2,
            ),
        )

        return RetrievalResult(
            chunks=retrieved_chunks,
            diagnostics=diagnostics,
            performance=performance,
        )

    @classmethod
    def _extract_filename(
        cls,
        query: str,
    ) -> str | None:
        matches = cls.FILENAME_PATTERN.findall(
            query
        )

        if not matches:
            return None

        for quoted, unquoted in matches:
            filename = (
                quoted.strip()
                if quoted
                else unquoted.strip()
            )

            if cls._is_supported_filename(
                filename
            ):
                return filename

        return None

    @classmethod
    def _is_supported_filename(
        cls,
        filename: str,
    ) -> bool:
        return filename.lower().endswith(
            cls.SUPPORTED_FILENAME_EXTENSIONS
        )

    @staticmethod
    def _build_chunk(
        payload: dict[str, Any],
        score: float,
    ) -> RetrievedChunk | None:
        required_fields = {
            "document_id",
            "filename",
            "content_type",
            "chunk_id",
            "text",
            "start_char",
            "end_char",
        }

        if not required_fields.issubset(
            payload
        ):
            return None

        return RetrievedChunk(
            document_id=str(
                payload["document_id"]
            ),
            filename=str(
                payload["filename"]
            ),
            content_type=str(
                payload["content_type"]
            ),
            chunk_id=int(
                payload["chunk_id"]
            ),
            text=str(
                payload["text"]
            ),
            start_char=int(
                payload["start_char"]
            ),
            end_char=int(
                payload["end_char"]
            ),
            score=score,
        )