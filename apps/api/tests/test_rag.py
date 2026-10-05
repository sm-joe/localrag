from dataclasses import dataclass

import pytest

from app.services.rag import RAGService
from app.services.retrieval import (
    RetrievedChunk,
    RetrievalDiagnostics,
    RetrievalPerformance,
    RetrievalResult,
)


@dataclass
class FakeRetrievalService:
    result: RetrievalResult
    calls: list[tuple[str, int | None]]

    def retrieve(
        self,
        query: str,
        limit: int | None = None,
    ) -> RetrievalResult:
        self.calls.append((query, limit))
        return self.result


@dataclass
class FakeLLMService:
    prompts: list[str]

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return (
            "LocalRAG uses Qdrant for vector "
            "storage. [1]"
        )


def create_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        document_id="doc-123",
        filename="rag-test.txt",
        content_type="text/plain",
        chunk_id=0,
        text=(
            "LocalRAG uses Qdrant for vector "
            "storage."
        ),
        start_char=0,
        end_char=46,
        score=0.94,
    )


def create_diagnostics(
    returned_count: int = 1,
) -> RetrievalDiagnostics:
    return RetrievalDiagnostics(
        requested_limit=5,
        candidate_count=2,
        returned_count=returned_count,
        filtered_count=1,
        top_score=0.94,
        bottom_score=0.94,
        has_context=returned_count > 0,
    )


def create_performance() -> RetrievalPerformance:
    return RetrievalPerformance(
        embedding_ms=25.0,
        search_ms=5.0,
        total_ms=31.0,
    )


def create_result(
    chunks: list[RetrievedChunk] | None = None,
) -> RetrievalResult:
    actual_chunks = (
        [create_chunk()]
        if chunks is None
        else chunks
    )

    return RetrievalResult(
        chunks=actual_chunks,
        diagnostics=create_diagnostics(
            returned_count=len(
                actual_chunks
            )
        ),
        performance=create_performance(),
    )


def test_rag_answer_returns_answer_and_sources():
    retrieval_service = FakeRetrievalService(
        result=create_result(),
        calls=[],
    )

    llm_service = FakeLLMService(
        prompts=[]
    )

    service = RAGService(
        retrieval_service=retrieval_service,
        llm_service=llm_service,
    )

    result = service.answer(
        question=(
            "What does LocalRAG use "
            "for vector storage?"
        )
    )

    assert (
        result.answer
        == "LocalRAG uses Qdrant for vector storage. [1]"
    )

    assert len(result.sources) == 1
    assert result.sources[0].filename == "rag-test.txt"
    assert result.sources[0].chunk_id == 0
    assert result.sources[0].score == 0.94
    assert result.sources[0].citation == "[1]"


def test_rag_returns_retrieval_diagnostics():
    retrieval_service = FakeRetrievalService(
        result=create_result(),
        calls=[],
    )

    llm_service = FakeLLMService(
        prompts=[]
    )

    service = RAGService(
        retrieval_service=retrieval_service,
        llm_service=llm_service,
    )

    result = service.answer(
        question="What is Qdrant?"
    )

    assert result.retrieval.requested_limit == 5
    assert result.retrieval.candidate_count == 2
    assert result.retrieval.returned_count == 1
    assert result.retrieval.filtered_count == 1
    assert result.retrieval.top_score == 0.94
    assert result.retrieval.bottom_score == 0.94
    assert result.retrieval.has_context is True


def test_rag_returns_performance_diagnostics():
    retrieval_service = FakeRetrievalService(
        result=create_result(),
        calls=[],
    )

    llm_service = FakeLLMService(
        prompts=[]
    )

    service = RAGService(
        retrieval_service=retrieval_service,
        llm_service=llm_service,
    )

    result = service.answer(
        question="What is Qdrant?"
    )

    assert result.performance.embedding_ms == 25.0
    assert result.performance.retrieval_ms == 31.0
    assert result.performance.prompt_build_ms >= 0
    assert result.performance.llm_ms >= 0
    assert result.performance.total_ms >= 0


def test_rag_passes_question_and_top_k_to_retrieval():
    retrieval_service = FakeRetrievalService(
        result=create_result(),
        calls=[],
    )

    llm_service = FakeLLMService(
        prompts=[]
    )

    service = RAGService(
        retrieval_service=retrieval_service,
        llm_service=llm_service,
    )

    service.answer(
        question="What is RAG?",
        top_k=3,
    )

    assert retrieval_service.calls == [
        ("What is RAG?", 3)
    ]


def test_rag_prompt_contains_question_and_context():
    retrieval_service = FakeRetrievalService(
        result=create_result(),
        calls=[],
    )

    llm_service = FakeLLMService(
        prompts=[]
    )

    service = RAGService(
        retrieval_service=retrieval_service,
        llm_service=llm_service,
    )

    service.answer(
        question="What does LocalRAG use?"
    )

    assert len(llm_service.prompts) == 1

    prompt = llm_service.prompts[0]

    assert (
        "What does LocalRAG use?"
        in prompt
    )

    assert (
        "LocalRAG uses Qdrant for vector storage."
        in prompt
    )

    assert "rag-test.txt" in prompt
    assert "[Source 1]" in prompt
    assert "source citations" in prompt


def test_rag_rejects_empty_question():
    retrieval_service = FakeRetrievalService(
        result=RetrievalResult(
            chunks=[],
            diagnostics=RetrievalDiagnostics(
                requested_limit=5,
                candidate_count=0,
                returned_count=0,
                filtered_count=0,
                top_score=None,
                bottom_score=None,
                has_context=False,
            ),
            performance=RetrievalPerformance(
                embedding_ms=0,
                search_ms=0,
                total_ms=0,
            ),
        ),
        calls=[],
    )

    llm_service = FakeLLMService(
        prompts=[]
    )

    service = RAGService(
        retrieval_service=retrieval_service,
        llm_service=llm_service,
    )

    with pytest.raises(
        ValueError,
        match="Question cannot be empty",
    ):
        service.answer("   ")


def test_rag_handles_no_retrieved_chunks():
    retrieval_result = RetrievalResult(
        chunks=[],
        diagnostics=RetrievalDiagnostics(
            requested_limit=5,
            candidate_count=3,
            returned_count=0,
            filtered_count=3,
            top_score=None,
            bottom_score=None,
            has_context=False,
        ),
        performance=RetrievalPerformance(
            embedding_ms=10,
            search_ms=2,
            total_ms=12,
        ),
    )

    retrieval_service = FakeRetrievalService(
        result=retrieval_result,
        calls=[],
    )

    llm_service = FakeLLMService(
        prompts=[]
    )

    service = RAGService(
        retrieval_service=retrieval_service,
        llm_service=llm_service,
    )

    result = service.answer(
        question=(
            "Something not in the documents."
        )
    )

    assert (
        result.answer
        == "LocalRAG uses Qdrant for vector storage. [1]"
    )

    assert result.sources == []

    assert result.retrieval.candidate_count == 3
    assert result.retrieval.returned_count == 0
    assert result.retrieval.filtered_count == 3
    assert result.retrieval.top_score is None
    assert result.retrieval.bottom_score is None
    assert result.retrieval.has_context is False

    assert (
        "No relevant documents were found."
        in llm_service.prompts[0]
    )


def test_rag_assigns_sequential_citations():
    first_chunk = create_chunk()

    second_chunk = RetrievedChunk(
        document_id="doc-456",
        filename="second.txt",
        content_type="text/plain",
        chunk_id=2,
        text="Terraform manages infrastructure.",
        start_char=0,
        end_char=35,
        score=0.82,
    )

    retrieval_service = FakeRetrievalService(
        result=create_result(
            chunks=[
                first_chunk,
                second_chunk,
            ]
        ),
        calls=[],
    )

    llm_service = FakeLLMService(
        prompts=[]
    )

    service = RAGService(
        retrieval_service=retrieval_service,
        llm_service=llm_service,
    )

    result = service.answer(
        question="What tools are mentioned?"
    )

    assert [
        source.citation
        for source in result.sources
    ] == ["[1]", "[2]"]