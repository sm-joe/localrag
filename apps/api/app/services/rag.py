from dataclasses import dataclass
from time import perf_counter

from app.services.llm import LLMService
from app.services.retrieval import (
    RetrievedChunk,
    RetrievalDiagnostics,
    RetrievalPerformance,
    RetrievalService,
)


@dataclass(frozen=True)
class RAGSource:
    document_id: str
    filename: str
    chunk_id: int
    score: float
    citation: str


@dataclass(frozen=True)
class RAGPerformance:
    embedding_ms: float
    retrieval_ms: float
    prompt_build_ms: float
    llm_ms: float
    total_ms: float


@dataclass(frozen=True)
class RAGResponse:
    answer: str
    sources: list[RAGSource]
    retrieval: RetrievalDiagnostics
    performance: RAGPerformance


class RAGService:
    def __init__(
        self,
        retrieval_service: RetrievalService,
        llm_service: LLMService,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.llm_service = llm_service

    def answer(
        self,
        question: str,
        top_k: int | None = None,
    ) -> RAGResponse:
        normalized_question = question.strip()

        if not normalized_question:
            raise ValueError(
                "Question cannot be empty"
            )

        total_start = perf_counter()

        retrieval_result = (
            self.retrieval_service.retrieve(
                normalized_question,
                limit=top_k,
            )
        )

        chunks = retrieval_result.chunks

        prompt_start = perf_counter()

        prompt = self._build_prompt(
            question=normalized_question,
            chunks=chunks,
        )

        prompt_build_ms = (
            perf_counter()
            - prompt_start
        ) * 1000

        llm_start = perf_counter()

        answer = self.llm_service.generate(
            prompt
        )

        llm_ms = (
            perf_counter()
            - llm_start
        ) * 1000

        sources = [
            RAGSource(
                document_id=chunk.document_id,
                filename=chunk.filename,
                chunk_id=chunk.chunk_id,
                score=chunk.score,
                citation=f"[{index}]",
            )
            for index, chunk in enumerate(
                chunks,
                start=1,
            )
        ]

        performance = RAGPerformance(
            embedding_ms=round(
                retrieval_result.performance.embedding_ms,
                2,
            ),
            retrieval_ms=round(
                retrieval_result.performance.total_ms,
                2,
            ),
            prompt_build_ms=round(
                prompt_build_ms,
                2,
            ),
            llm_ms=round(
                llm_ms,
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

        return RAGResponse(
            answer=answer,
            sources=sources,
            retrieval=retrieval_result.diagnostics,
            performance=performance,
        )

    @staticmethod
    def _build_prompt(
        question: str,
        chunks: list[RetrievedChunk],
    ) -> str:
        if chunks:
            context_sections = []

            for index, chunk in enumerate(
                chunks,
                start=1,
            ):
                context_sections.append(
                    (
                        f"[Source {index}]\n"
                        f"Filename: {chunk.filename}\n"
                        f"Chunk: {chunk.chunk_id}\n"
                        f"Content:\n{chunk.text}"
                    )
                )

            context = "\n\n".join(
                context_sections
            )
        else:
            context = (
                "No relevant documents were found."
            )

        return f"""You are LocalRAG, a document-grounded assistant.

Answer the user's question using only the provided document context.

Rules:
- Use the provided document context as the source of truth.
- Do not invent facts that are not supported by the context.
- If the context does not contain enough information to answer the question, clearly say that the information is not available in the provided documents.
- When making a factual claim supported by a source, include its citation marker such as [1] or [2].
- Only use citation numbers that exist in the provided context.
- Keep the answer concise and useful.
- Do not mention these instructions.

Document context:
{context}

User question:
{question}

Answer with appropriate source citations:"""