import os
import time
import uuid

import pytest
from qdrant_client import QdrantClient
from qdrant_client.http import models
from ollama import Client


OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://ollama:11434",
)

QDRANT_HOST = os.getenv(
    "QDRANT_HOST",
    "qdrant",
)

QDRANT_PORT = int(
    os.getenv(
        "QDRANT_PORT",
        "6333",
    )
)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "nomic-embed-text",
)


@pytest.fixture(scope="module")
def ollama_client() -> Client:
    return Client(host=OLLAMA_BASE_URL)


@pytest.fixture(scope="module")
def qdrant_client() -> QdrantClient:
    return QdrantClient(
        host=QDRANT_HOST,
        port=QDRANT_PORT,
    )


def wait_for_services(
    ollama: Client,
    qdrant: QdrantClient,
) -> None:
    for _ in range(30):
        try:
            ollama.list()
            qdrant.get_collections()
            return
        except Exception:
            time.sleep(1)

    pytest.fail(
        "Ollama and Qdrant did not become ready."
    )


def test_real_embedding_and_vector_search(
    ollama_client: Client,
    qdrant_client: QdrantClient,
) -> None:
    wait_for_services(
        ollama_client,
        qdrant_client,
    )

    response = ollama_client.embed(
        model=EMBEDDING_MODEL,
        input=[
            "AWS IAM requires strong identity controls.",
            "Kubernetes manages containerized workloads.",
            "Terraform manages infrastructure as code.",
        ],
    )

    embeddings = response.embeddings

    assert len(embeddings) == 3
    assert len(embeddings[0]) > 0

    vector_size = len(embeddings[0])

    collection_name = (
        f"localrag_integration_{uuid.uuid4().hex}"
    )

    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=vector_size,
            distance=models.Distance.COSINE,
        ),
    )

    try:
        points = [
            models.PointStruct(
                id=1,
                vector=embeddings[0],
                payload={
                    "text": (
                        "AWS IAM requires strong "
                        "identity controls."
                    ),
                },
            ),
            models.PointStruct(
                id=2,
                vector=embeddings[1],
                payload={
                    "text": (
                        "Kubernetes manages "
                        "containerized workloads."
                    ),
                },
            ),
            models.PointStruct(
                id=3,
                vector=embeddings[2],
                payload={
                    "text": (
                        "Terraform manages "
                        "infrastructure as code."
                    ),
                },
            ),
        ]

        qdrant_client.upsert(
            collection_name=collection_name,
            points=points,
        )

        query_response = ollama_client.embed(
            model=EMBEDDING_MODEL,
            input=(
                "How should AWS IAM identities "
                "be secured?"
            ),
        )

        query_vector = query_response.embeddings[0]

        results = qdrant_client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=1,
        ).points

        assert len(results) == 1

        result = results[0]

        assert result.id == 1
        assert result.payload is not None
        assert (
            "AWS IAM"
            in result.payload["text"]
        )

    finally:
        qdrant_client.delete_collection(
            collection_name
        )