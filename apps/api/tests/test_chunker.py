import pytest

from app.services.chunker import chunk_text


def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []


def test_whitespace_only_text_returns_no_chunks():
    assert chunk_text("   \n\n   ") == []


def test_short_text_returns_single_chunk():
    text = "LocalRAG uses Qdrant."

    chunks = chunk_text(
        text,
        chunk_size=100,
        chunk_overlap=10,
    )

    assert len(chunks) == 1
    assert chunks[0].chunk_id == 0
    assert chunks[0].text == text
    assert chunks[0].start_char == 0
    assert chunks[0].end_char == len(text)


def test_paragraphs_are_kept_together_when_they_fit():
    text = (
        "LocalRAG is a RAG application.\n\n"
        "It uses Qdrant for vector storage.\n\n"
        "It uses Ollama for local models."
    )

    chunks = chunk_text(
        text,
        chunk_size=200,
        chunk_overlap=20,
    )

    assert len(chunks) == 1

    assert chunks[0].text == (
        "LocalRAG is a RAG application.\n\n"
        "It uses Qdrant for vector storage.\n\n"
        "It uses Ollama for local models."
    )


def test_paragraphs_are_split_at_paragraph_boundaries():
    text = (
        "Paragraph one contains information "
        "about retrieval.\n\n"
        "Paragraph two contains information "
        "about embeddings.\n\n"
        "Paragraph three contains information "
        "about Qdrant."
    )

    chunks = chunk_text(
        text,
        chunk_size=100,
        chunk_overlap=0,
    )

    assert len(chunks) == 3

    assert "Paragraph one" in chunks[0].text
    assert "Paragraph two" in chunks[1].text
    assert "Paragraph three" in chunks[2].text


def test_chunk_ids_are_sequential():
    text = (
        "Paragraph one.\n\n"
        "Paragraph two.\n\n"
        "Paragraph three.\n\n"
        "Paragraph four."
    )

    chunks = chunk_text(
        text,
        chunk_size=20,
        chunk_overlap=0,
    )

    assert [
        chunk.chunk_id
        for chunk in chunks
    ] == list(range(len(chunks)))


def test_chunks_respect_maximum_size():
    text = (
        "This is the first paragraph with "
        "some useful information.\n\n"
        "This is the second paragraph with "
        "some more useful information.\n\n"
        "This is the third paragraph."
    )

    chunks = chunk_text(
        text,
        chunk_size=60,
        chunk_overlap=0,
    )

    assert chunks

    for chunk in chunks:
        assert len(chunk.text) <= 60


def test_long_paragraph_is_split_by_sentences():
    text = (
        "LocalRAG retrieves documents. "
        "It converts questions into embeddings. "
        "Qdrant stores the vectors. "
        "Ollama generates the final answer."
    )

    chunks = chunk_text(
        text,
        chunk_size=70,
        chunk_overlap=0,
    )

    assert len(chunks) > 1

    for chunk in chunks:
        assert len(chunk.text) <= 70


def test_long_word_is_split_when_necessary():
    text = (
        "prefix "
        "abcdefghijklmnopqrstuvwxyz"
        "abcdefghijklmnopqrstuvwxyz"
        " suffix"
    )

    chunks = chunk_text(
        text,
        chunk_size=20,
        chunk_overlap=0,
    )

    assert chunks

    for chunk in chunks:
        assert len(chunk.text) <= 20


def test_overlap_is_used_between_chunks():
    text = (
        "The first paragraph explains "
        "retrieval and embeddings.\n\n"
        "The second paragraph explains "
        "vector databases and search.\n\n"
        "The third paragraph explains "
        "language model generation."
    )

    chunks = chunk_text(
        text,
        chunk_size=80,
        chunk_overlap=30,
    )

    assert len(chunks) >= 2

    first_text = chunks[0].text
    second_text = chunks[1].text

    shared_words = set(
        first_text.split()
    ).intersection(
        second_text.split()
    )

    assert shared_words


def test_zero_overlap_is_supported():
    text = (
        "First paragraph.\n\n"
        "Second paragraph.\n\n"
        "Third paragraph."
    )

    chunks = chunk_text(
        text,
        chunk_size=25,
        chunk_overlap=0,
    )

    assert len(chunks) >= 2


def test_negative_overlap_is_rejected():
    with pytest.raises(
        ValueError,
        match="chunk_overlap cannot be negative",
    ):
        chunk_text(
            "LocalRAG",
            chunk_size=100,
            chunk_overlap=-1,
        )


def test_zero_chunk_size_is_rejected():
    with pytest.raises(
        ValueError,
        match="chunk_size must be greater than zero",
    ):
        chunk_text(
            "LocalRAG",
            chunk_size=0,
        )


def test_overlap_equal_to_chunk_size_is_rejected():
    with pytest.raises(
        ValueError,
        match="chunk_overlap must be smaller than chunk_size",
    ):
        chunk_text(
            "LocalRAG",
            chunk_size=100,
            chunk_overlap=100,
        )


def test_paragraph_offsets_are_preserved():
    text = (
        "First paragraph.\n\n"
        "Second paragraph."
    )

    chunks = chunk_text(
        text,
        chunk_size=18,
        chunk_overlap=0,
    )

    assert chunks[0].start_char == 0
    assert chunks[0].end_char == len(
        "First paragraph."
    )

    second_start = text.index(
        "Second paragraph."
    )

    assert chunks[1].start_char == second_start
    assert chunks[1].end_char == len(text)


def test_multiple_blank_lines_do_not_create_empty_chunks():
    text = (
        "First paragraph.\n\n\n\n"
        "Second paragraph.\n\n\n"
        "Third paragraph."
    )

    chunks = chunk_text(
        text,
        chunk_size=100,
        chunk_overlap=0,
    )

    assert len(chunks) == 1

    assert (
        "First paragraph."
        in chunks[0].text
    )
    assert (
        "Second paragraph."
        in chunks[0].text
    )
    assert (
        "Third paragraph."
        in chunks[0].text
    )