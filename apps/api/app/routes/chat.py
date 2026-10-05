from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.embeddings import EmbeddingService
from app.services.llm import LLMService
from app.services.rag import RAGService
from app.services.retrieval import RetrievalService
from app.services.vector_store import VectorStore


router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


class ChatRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=4000,
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
    )


class ChatSource(BaseModel):
    document_id: str
    filename: str
    chunk_id: int
    score: float
    citation: str


class ChatRetrievalDiagnostics(BaseModel):
    requested_limit: int
    candidate_count: int
    returned_count: int
    filtered_count: int
    top_candidate_score: float | None
    bottom_candidate_score: float | None
    top_score: float | None
    bottom_score: float | None
    has_context: bool


class ChatPerformance(BaseModel):
    embedding_ms: float
    retrieval_ms: float
    prompt_build_ms: float
    llm_ms: float
    total_ms: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    retrieval: ChatRetrievalDiagnostics
    performance: ChatPerformance


def create_rag_service() -> RAGService:
    settings = get_settings()

    embedding_service = EmbeddingService(
        base_url=settings.ollama_base_url,
        model=settings.embedding_model,
    )

    vector_store = VectorStore(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        collection_name=settings.qdrant_collection,
    )

    retrieval_service = RetrievalService(
        embedding_service=embedding_service,
        vector_store=vector_store,
        top_k=5,
        score_threshold=0.45,
    )

    llm_service = LLMService(
        base_url=settings.ollama_base_url,
        model=settings.llm_model,
    )

    return RAGService(
        retrieval_service=retrieval_service,
        llm_service=llm_service,
    )


@router.post(
    "",
    response_model=ChatResponse,
)
def chat(
    request: ChatRequest,
) -> ChatResponse:
    try:
        service = create_rag_service()

        result = service.answer(
            question=request.question,
            top_k=request.top_k,
        )

        return ChatResponse(
            answer=result.answer,
            sources=[
                ChatSource(
                    document_id=source.document_id,
                    filename=source.filename,
                    chunk_id=source.chunk_id,
                    score=source.score,
                    citation=source.citation,
                )
                for source in result.sources
            ],
            retrieval=ChatRetrievalDiagnostics(
                requested_limit=(
                    result.retrieval.requested_limit
                ),
                candidate_count=(
                    result.retrieval.candidate_count
                ),
                returned_count=(
                    result.retrieval.returned_count
                ),
                filtered_count=(
                    result.retrieval.filtered_count
                ),
                top_candidate_score=(
                    result.retrieval.top_candidate_score
                ),
                bottom_candidate_score=(
                    result.retrieval.bottom_candidate_score
                ),
                top_score=(
                    result.retrieval.top_score
                ),
                bottom_score=(
                    result.retrieval.bottom_score
                ),
                has_context=(
                    result.retrieval.has_context
                ),
            ),
            performance=ChatPerformance(
                embedding_ms=(
                    result.performance.embedding_ms
                ),
                retrieval_ms=(
                    result.performance.retrieval_ms
                ),
                prompt_build_ms=(
                    result.performance.prompt_build_ms
                ),
                llm_ms=(
                    result.performance.llm_ms
                ),
                total_ms=(
                    result.performance.total_ms
                ),
            ),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="RAG chat failed.",
        ) from exc