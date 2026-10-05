from unittest.mock import MagicMock

import pytest

from app.services.embeddings import EmbeddingService


def test_embed_returns_vector() -> None:
    client = MagicMock()

    client.embed.return_value.embeddings = [
        [0.1, 0.2, 0.3]
    ]

    service = EmbeddingService(
        base_url="http://ollama:11434",
        model="nomic-embed-text",
    )

    service.client = client

    result = service.embed("Hello LocalRAG")

    assert result == [0.1, 0.2, 0.3]

    client.embed.assert_called_once_with(
        model="nomic-embed-text",
        input="Hello LocalRAG",
    )


def test_embed_rejects_empty_text() -> None:
    service = EmbeddingService(
        base_url="http://ollama:11434",
        model="nomic-embed-text",
    )

    with pytest.raises(
        ValueError,
        match="empty text",
    ):
        service.embed("   ")


def test_embed_rejects_empty_response() -> None:
    client = MagicMock()

    client.embed.return_value.embeddings = []

    service = EmbeddingService(
        base_url="http://ollama:11434",
        model="nomic-embed-text",
    )

    service.client = client

    with pytest.raises(
        RuntimeError,
        match="no embeddings",
    ):
        service.embed("Hello LocalRAG")