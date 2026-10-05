from unittest.mock import MagicMock

import pytest
from qdrant_client.http import models

from app.services.vector_store import VectorStore


def create_store() -> VectorStore:
    store = VectorStore(
        host="qdrant",
        port=6333,
        collection_name="test_collection",
    )

    store.client = MagicMock()

    return store


def test_ensure_collection_creates_missing_collection() -> None:
    store = create_store()

    store.client.get_collections.return_value.collections = []

    store.ensure_collection(vector_size=3)

    store.client.create_collection.assert_called_once()

    kwargs = store.client.create_collection.call_args.kwargs

    assert kwargs["collection_name"] == "test_collection"

    vector_config = kwargs["vectors_config"]

    assert vector_config.size == 3
    assert vector_config.distance == models.Distance.COSINE


def test_ensure_collection_does_not_recreate_existing_collection() -> None:
    store = create_store()

    existing = MagicMock()
    existing.name = "test_collection"

    store.client.get_collections.return_value.collections = [
        existing
    ]

    store.ensure_collection(vector_size=3)

    store.client.create_collection.assert_not_called()


def test_upsert_points() -> None:
    store = create_store()

    point = models.PointStruct(
        id="chunk-1",
        vector=[0.1, 0.2, 0.3],
        payload={
            "text": "Hello LocalRAG"
        },
    )

    store.upsert([point])

    store.client.upsert.assert_called_once_with(
        collection_name="test_collection",
        points=[point],
    )


def test_upsert_empty_points_does_nothing() -> None:
    store = create_store()

    store.upsert([])

    store.client.upsert.assert_not_called()


def test_search_rejects_empty_vector() -> None:
    store = create_store()

    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        store.search([])


def test_search_rejects_invalid_limit() -> None:
    store = create_store()

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        store.search(
            [0.1, 0.2, 0.3],
            limit=0,
        )


def test_search_returns_points() -> None:
    store = create_store()

    points = [
        MagicMock(),
        MagicMock(),
    ]

    store.client.query_points.return_value.points = points

    result = store.search(
        [0.1, 0.2, 0.3],
        limit=5,
    )

    assert result == points

    store.client.query_points.assert_called_once_with(
        collection_name="test_collection",
        query=[0.1, 0.2, 0.3],
        limit=5,
    )