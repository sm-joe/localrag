import tempfile
import zipfile
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


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
    ".md",
}

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
MAX_FILENAME_LENGTH = 255
UPLOAD_READ_CHUNK_SIZE = 1024 * 1024

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"


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


def _sanitize_filename(filename: str) -> str:
    normalized_filename = filename.replace("\\", "/")
    sanitized_filename = Path(normalized_filename).name

    if not sanitized_filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required.",
        )

    if "\x00" in sanitized_filename:
        raise HTTPException(
            status_code=400,
            detail="Filename contains invalid characters.",
        )

    if len(sanitized_filename) > MAX_FILENAME_LENGTH:
        raise HTTPException(
            status_code=400,
            detail="Filename is too long.",
        )

    return sanitized_filename


async def _write_upload_to_temporary_file(
    file: UploadFile,
    temporary_file,
) -> int:
    total_size = 0

    while True:
        chunk = await file.read(UPLOAD_READ_CHUNK_SIZE)

        if not chunk:
            break

        total_size += len(chunk)

        if total_size > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    "File is too large. "
                    "Maximum upload size is 10 MiB."
                ),
            )

        temporary_file.write(chunk)

    return total_size


def _validate_pdf(path: Path) -> None:
    try:
        with path.open("rb") as file:
            header = file.read(len(PDF_MAGIC))

    except OSError as exc:
        raise HTTPException(
            status_code=400,
            detail="Uploaded PDF could not be read.",
        ) from exc

    if header != PDF_MAGIC:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is not a valid PDF.",
        )


def _validate_docx(path: Path) -> None:
    try:
        with path.open("rb") as file:
            header = file.read(len(ZIP_MAGIC))

        if header != ZIP_MAGIC:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is not a valid DOCX.",
            )

        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())

            if "[Content_Types].xml" not in names:
                raise HTTPException(
                    status_code=400,
                    detail="Uploaded file is not a valid DOCX.",
                )

            if "word/document.xml" not in names:
                raise HTTPException(
                    status_code=400,
                    detail="Uploaded file is not a valid DOCX.",
                )

            if archive.testzip() is not None:
                raise HTTPException(
                    status_code=400,
                    detail="Uploaded DOCX archive is corrupted.",
                )

    except HTTPException:
        raise

    except (
        OSError,
        zipfile.BadZipFile,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is not a valid DOCX.",
        ) from exc


def _validate_text(path: Path) -> None:
    try:
        path.read_text(
            encoding="utf-8",
        )

    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="Uploaded text file is not valid UTF-8.",
        ) from exc

    except OSError as exc:
        raise HTTPException(
            status_code=400,
            detail="Uploaded text file could not be read.",
        ) from exc


def _validate_file_content(
    path: Path,
    extension: str,
) -> None:
    if extension == ".pdf":
        _validate_pdf(path)
        return

    if extension == ".docx":
        _validate_docx(path)
        return

    if extension in {".txt", ".md"}:
        _validate_text(path)
        return

    raise HTTPException(
        status_code=400,
        detail=(
            f"Unsupported file type: {extension}"
        ),
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

    original_filename = _sanitize_filename(
        file.filename
    )

    extension = Path(
        original_filename
    ).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
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

            total_size = await _write_upload_to_temporary_file(
                file=file,
                temporary_file=temporary_file,
            )

        if total_size == 0:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty.",
            )

        _validate_file_content(
            path=temporary_path,
            extension=extension,
        )

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

    except HTTPException:
        raise

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

        await file.close()


@router.get(
    "",
    response_model=DocumentListResponse,
)
def list_documents() -> DocumentListResponse:
    try:
        vector_store = create_vector_store()
        settings = get_settings()

        collections = vector_store.client.get_collections()

        collection_exists = any(
            collection.name == settings.qdrant_collection
            for collection in collections.collections
        )

        if not collection_exists:
            return DocumentListResponse(
                documents=[]
            )

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