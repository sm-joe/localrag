import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import get_settings
from app.services.embeddings import EmbeddingService
from app.services.ingestion import IngestionService
from app.services.vector_store import VectorStore


router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    chunks: int
    status: str


class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    content_type: str
    chunks: int


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]


class DocumentDeleteResponse(BaseModel):
    document_id: str
    status: str


def create_vector_store() -> VectorStore:
    settings = get_settings()

    return VectorStore(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        collection_name=settings.qdrant_collection,
    )


def create_ingestion_service() -> IngestionService:
    settings = get_settings()

    embedding_service = EmbeddingService(
        base_url=settings.ollama_base_url,
        model=settings.embedding_model,
    )

    vector_store = create_vector_store()

    return IngestionService(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
)
async def upload_document(
    file: UploadFile = File(...),
) -> DocumentUploadResponse:
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required.",
        )

    original_filename = Path(
        file.filename
    ).name

    extension = Path(
        original_filename
    ).suffix.lower()

    allowed_extensions = {
        ".pdf",
        ".docx",
        ".txt",
        ".md",
    }

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: {extension}"
            ),
        )

    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=extension,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(
                temporary_file.name
            )

            content = await file.read()

            temporary_file.write(content)

        service = create_ingestion_service()

        result = service.ingest(
            file_path=temporary_path,
            content_type=file.content_type
            or "application/octet-stream",
            original_filename=original_filename,
        )

        status = (
            "already_indexed"
            if result.already_indexed
            else "indexed"
        )

        return DocumentUploadResponse(
            document_id=result.document_id,
            filename=result.filename,
            chunks=result.chunks,
            status=status,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Document ingestion failed.",
        ) from exc

    finally:
        if temporary_path is not None:
            temporary_path.unlink(
                missing_ok=True
            )


@router.get(
    "",
    response_model=DocumentListResponse,
)
def list_documents() -> DocumentListResponse:
    try:
        vector_store = create_vector_store()

        points = vector_store.list_points(
            limit=1000,
        )

        documents: dict[str, DocumentResponse] = {}

        for point in points:
            payload = point.payload or {}

            document_id = payload.get(
                "document_id"
            )

            if not document_id:
                continue

            document_id = str(document_id)

            if document_id not in documents:
                documents[document_id] = (
                    DocumentResponse(
                        document_id=document_id,
                        filename=str(
                            payload.get(
                                "filename",
                                "unknown",
                            )
                        ),
                        content_type=str(
                            payload.get(
                                "content_type",
                                "application/octet-stream",
                            )
                        ),
                        chunks=0,
                    )
                )

            documents[document_id] = (
                documents[document_id].model_copy(
                    update={
                        "chunks": (
                            documents[document_id].chunks
                            + 1
                        )
                    }
                )
            )

        return DocumentListResponse(
            documents=list(
                documents.values()
            )
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to list documents.",
        ) from exc


@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
)
def delete_document(
    document_id: str,
) -> DocumentDeleteResponse:
    if not document_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Document ID is required.",
        )

    try:
        vector_store = create_vector_store()

        vector_store.delete_document(
            document_id
        )

        return DocumentDeleteResponse(
            document_id=document_id,
            status="deleted",
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to delete document.",
        ) from exc