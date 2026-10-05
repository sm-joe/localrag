import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: int
    text: str
    start_char: int
    end_char: int


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> list[DocumentChunk]:
    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than zero"
        )

    if chunk_overlap < 0:
        raise ValueError(
            "chunk_overlap cannot be negative"
        )

    if chunk_overlap >= chunk_size:
        raise ValueError(
            "chunk_overlap must be smaller than chunk_size"
        )

    normalized_text = text.strip()

    if not normalized_text:
        return []

    paragraphs = _extract_paragraphs(
        normalized_text
    )

    if not paragraphs:
        return []

    chunks: list[DocumentChunk] = []
    chunk_id = 0

    current_parts: list[str] = []
    current_start: int | None = None
    current_end: int | None = None

    for paragraph_text, paragraph_start, paragraph_end in paragraphs:
        if len(paragraph_text) > chunk_size:
            if current_parts:
                chunks.append(
                    _build_chunk(
                        chunk_id=chunk_id,
                        parts=current_parts,
                        start_char=current_start,
                        end_char=current_end,
                    )
                )
                chunk_id += 1

                overlap_text = _get_overlap_text(
                    current_parts,
                    chunk_overlap,
                )

                current_parts = (
                    [overlap_text]
                    if overlap_text
                    else []
                )

                current_start = (
                    current_end - len(overlap_text)
                    if overlap_text
                    and current_end is not None
                    else None
                )

                current_end = (
                    current_start + len(overlap_text)
                    if current_start is not None
                    else None
                )

            long_parts = _split_long_paragraph(
                paragraph_text,
                chunk_size,
            )

            for part_index, part in enumerate(
                long_parts
            ):
                part_start = paragraph_start + paragraph_text.find(
                    part
                )
                part_end = part_start + len(part)

                if (
                    current_parts
                    and _combined_length(
                        current_parts,
                        part,
                    )
                    <= chunk_size
                ):
                    current_parts.append(part)

                    if current_start is None:
                        current_start = part_start

                    current_end = part_end
                    continue

                if current_parts:
                    chunks.append(
                        _build_chunk(
                            chunk_id=chunk_id,
                            parts=current_parts,
                            start_char=current_start,
                            end_char=current_end,
                        )
                    )
                    chunk_id += 1

                    overlap_text = _get_overlap_text(
                        current_parts,
                        chunk_overlap,
                    )

                    current_parts = (
                        [overlap_text]
                        if overlap_text
                        else []
                    )

                    current_start = (
                        part_start - len(overlap_text)
                        if overlap_text
                        else None
                    )

                    current_end = (
                        part_start
                        if overlap_text
                        else None
                    )

                current_parts.append(part)
                current_start = (
                    part_start
                    if current_start is None
                    else current_start
                )
                current_end = part_end

            continue

        if not current_parts:
            current_parts = [paragraph_text]
            current_start = paragraph_start
            current_end = paragraph_end
            continue

        combined_length = _combined_length(
            current_parts,
            paragraph_text,
        )

        if combined_length <= chunk_size:
            current_parts.append(
                paragraph_text
            )
            current_end = paragraph_end
            continue

        chunks.append(
            _build_chunk(
                chunk_id=chunk_id,
                parts=current_parts,
                start_char=current_start,
                end_char=current_end,
            )
        )
        chunk_id += 1

        overlap_text = _get_overlap_text(
            current_parts,
            chunk_overlap,
        )

        if overlap_text:
            overlap_start = max(
                paragraph_start - len(overlap_text),
                0,
            )

            current_parts = [
                overlap_text,
                paragraph_text,
            ]

            current_start = overlap_start
            current_end = paragraph_end

            if (
                _combined_length(
                    current_parts
                )
                > chunk_size
            ):
                current_parts = [
                    paragraph_text
                ]
                current_start = paragraph_start
                current_end = paragraph_end
        else:
            current_parts = [
                paragraph_text
            ]
            current_start = paragraph_start
            current_end = paragraph_end

    if current_parts:
        chunks.append(
            _build_chunk(
                chunk_id=chunk_id,
                parts=current_parts,
                start_char=current_start,
                end_char=current_end,
            )
        )

    return chunks


def _extract_paragraphs(
    text: str,
) -> list[tuple[str, int, int]]:
    paragraphs: list[
        tuple[str, int, int]
    ] = []

    paragraph_pattern = re.compile(
        r"\S(?:.*?\S)?(?=\n\s*\n|\Z)",
        re.DOTALL,
    )

    for match in paragraph_pattern.finditer(text):
        paragraph = match.group(0).strip()

        if not paragraph:
            continue

        leading_whitespace = (
            len(match.group(0))
            - len(match.group(0).lstrip())
        )

        start = (
            match.start()
            + leading_whitespace
        )

        end = start + len(paragraph)

        paragraphs.append(
            (
                paragraph,
                start,
                end,
            )
        )

    return paragraphs


def _split_long_paragraph(
    paragraph: str,
    chunk_size: int,
) -> list[str]:
    sentences = _split_sentences(
        paragraph
    )

    if len(sentences) == 1:
        return _split_words(
            paragraph,
            chunk_size,
        )

    parts: list[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        if len(sentence) > chunk_size:
            if current:
                parts.append(current)
                current = ""

            parts.extend(
                _split_words(
                    sentence,
                    chunk_size,
                )
            )
            continue

        if not current:
            current = sentence
            continue

        candidate = f"{current} {sentence}"

        if len(candidate) <= chunk_size:
            current = candidate
        else:
            parts.append(current)
            current = sentence

    if current:
        parts.append(current)

    return parts


def _split_sentences(
    text: str,
) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])\s+",
            text,
        )
        if sentence.strip()
    ]


def _split_words(
    text: str,
    chunk_size: int,
) -> list[str]:
    words = text.split()

    if not words:
        return []

    parts: list[str] = []
    current = ""

    for word in words:
        if len(word) > chunk_size:
            if current:
                parts.append(current)
                current = ""

            start = 0

            while start < len(word):
                parts.append(
                    word[
                        start : start + chunk_size
                    ]
                )
                start += chunk_size

            continue

        if not current:
            current = word
            continue

        candidate = f"{current} {word}"

        if len(candidate) <= chunk_size:
            current = candidate
        else:
            parts.append(current)
            current = word

    if current:
        parts.append(current)

    return parts


def _combined_length(
    parts: list[str],
    additional: str | None = None,
) -> int:
    total = sum(
        len(part)
        for part in parts
    )

    if parts:
        total += len(parts) - 1

    if additional:
        if parts:
            total += 1

        total += len(additional)

    return total


def _get_overlap_text(
    parts: list[str],
    overlap: int,
) -> str:
    if overlap <= 0 or not parts:
        return ""

    selected: list[str] = []
    total_length = 0

    for part in reversed(parts):
        additional_length = len(part)

        if selected:
            additional_length += 1

        if (
            total_length + additional_length
            > overlap
        ):
            break

        selected.insert(0, part)
        total_length += additional_length

    return " ".join(selected)


def _build_chunk(
    chunk_id: int,
    parts: list[str],
    start_char: int | None,
    end_char: int | None,
) -> DocumentChunk:
    text = "\n\n".join(
        part.strip()
        for part in parts
        if part.strip()
    ).strip()

    if start_char is None:
        start_char = 0

    if end_char is None:
        end_char = start_char + len(text)

    return DocumentChunk(
        chunk_id=chunk_id,
        text=text,
        start_char=start_char,
        end_char=end_char,
    )