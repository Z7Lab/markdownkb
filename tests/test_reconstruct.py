"""Tests for chunk → document reconstruction (app.ingestion.reconstruct)."""

from app.ingestion.parser import chunk_text, parse_and_chunk
from app.ingestion.reconstruct import reconstruct_chunks


def _paragraphs(n: int, words_per: int = 30) -> list[str]:
    """Build n distinct paragraphs of plain text."""
    return [
        " ".join(f"para{i}word{j}" for j in range(words_per))
        for i in range(n)
    ]


def test_round_trip_paragraph_chunks():
    """Paragraph-aligned chunks rebuild the original text exactly."""
    text = "\n\n".join(_paragraphs(8))
    chunks = chunk_text(text, max_size=512, overlap=50)
    assert len(chunks) > 1, "test text must actually be chunked"
    assert reconstruct_chunks(chunks) == text


def test_overlap_not_duplicated_on_sentence_splits():
    """A long paragraph split by sentences rebuilds without repeated seams."""
    sentences = [
        f"Sentence number {i} carries some unique payload text {i}."
        for i in range(40)
    ]
    text = " ".join(sentences)
    chunks = chunk_text(text, max_size=512, overlap=50)
    assert len(chunks) > 1
    rebuilt = reconstruct_chunks(chunks)
    for sentence in sentences:
        assert rebuilt.count(sentence) == 1


def test_overlap_zero_passes_through():
    """With no overlap at index time, nothing is stripped from the seams."""
    text = "\n\n".join(_paragraphs(8))
    chunks = chunk_text(text, max_size=512, overlap=0)
    assert len(chunks) > 1
    assert reconstruct_chunks(chunks) == text


def test_breadcrumbs_stripped_from_parsed_file(tmp_path):
    """parse_and_chunk output rebuilds without breadcrumbs or seam repeats."""
    sentences = [
        f"Body sentence {i} with its own distinct marker {i}." for i in range(30)
    ]
    md = (
        "# Section One\n\n"
        + " ".join(sentences[:15])
        + "\n\n# Section Two\n\n"
        + " ".join(sentences[15:])
        + "\n"
    )
    f = tmp_path / "doc.md"
    f.write_text(md, encoding="utf-8")

    chunks = parse_and_chunk(str(f), str(tmp_path), max_chunk_size=512, overlap=50)
    assert len(chunks) > 2
    rebuilt = reconstruct_chunks([c.content for c in chunks])

    assert "From:" not in rebuilt
    assert "# Section One" in rebuilt
    assert "# Section Two" in rebuilt
    for sentence in sentences:
        assert rebuilt.count(sentence) == 1


def test_single_and_empty_inputs():
    assert reconstruct_chunks([]) == ""
    assert reconstruct_chunks(["only chunk"]) == "only chunk"
