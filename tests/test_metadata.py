from app.documents.metadata import DocumentMeta, build_chunk_meta


def test_document_meta_to_dict():
    doc = DocumentMeta(
        document_id="doc123",
        filename="test.pdf",
        file_type="pdf",
        checksum="abcd123",
        department="hr",
        tags=["leave", "vacation"],
        access_roles=["employee", "hr_admin"],
    )
    d = doc.to_dict()
    assert d["document_id"] == "doc123"
    assert d["tags"] == "leave,vacation"
    assert d["access_roles"] == "employee,hr_admin"


def test_chunk_meta_to_chroma():
    doc = DocumentMeta(
        document_id="doc123",
        filename="test.pdf",
        file_type="pdf",
        checksum="abcd123",
        department="hr",
        tags=["leave"],
        access_roles=["employee"],
    )
    chunk = build_chunk_meta(
        chunk_id="chunk1",
        doc_meta=doc,
        chunk_index=0,
        content_hash="hash1",
        page_number=1,
        section_title="Intro",
        content_type="text",
        extraction_method="pdfplumber",
    )
    chroma_meta = chunk.to_chroma_metadata()
    assert chroma_meta["chunk_id"] == "chunk1"
    assert chroma_meta["department"] == "hr"
    assert chroma_meta["tags"] == "leave"
    assert chroma_meta["access_roles"] == "employee"
    assert chroma_meta["page_number"] == 1
    # Check that None properties are represented as empty string for Chroma
    assert chroma_meta["table_index"] == ""
