from app.documents.chunker import TextChunk, chunk_pages, chunk_text


def test_chunk_text_basic():
    text = "Hello world. This is a simple text segment. " * 20
    chunks = chunk_text(text, target_tokens=10, max_tokens=15, overlap_tokens=2)
    assert len(chunks) > 0
    assert all(isinstance(c, TextChunk) for c in chunks)
    assert all(c.text.strip() != "" for c in chunks)


def test_chunk_text_empty():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_chunk_text_headings():
    text = "# Heading 1\nThis is paragraph one.\n\n## Subheading\nThis is paragraph two."
    chunks = chunk_text(text, target_tokens=10, max_tokens=25, overlap_tokens=0)
    assert len(chunks) >= 2
    # The last chunk should carry the section heading detected
    assert chunks[-1].section_title in ("Subheading", "Heading 1")


def test_chunk_pages():
    pages = [
        (1, "This is the content of page one. It has some text."),
        (2, "This is page two. More text content here."),
    ]
    chunks = chunk_pages(pages, target_tokens=10, max_tokens=20, overlap_tokens=2)
    assert len(chunks) >= 2
    # Verify page numbers are preserved
    assert chunks[0].page_number == 1
    assert chunks[-1].page_number == 2
