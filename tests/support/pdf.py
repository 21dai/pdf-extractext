"""Shared PDF fixtures and helpers for API tests."""

import hashlib


DEFAULT_PDF_TEXT = "Test Document Content"


def build_pdf_bytes(text: str = DEFAULT_PDF_TEXT) -> bytes:
    """Build a minimal valid single-page PDF containing the given text."""
    escaped_text = (
        text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    )
    stream = f"BT\n/F1 18 Tf\n50 100 Td\n({escaped_text}) Tj\nET\n"
    stream_bytes = stream.encode("utf-8")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        (
            f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("utf-8")
            + stream_bytes
            + b"endstream"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf_bytes = bytearray(b"%PDF-1.4\n")
    offsets = [0]

    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf_bytes))
        pdf_bytes.extend(f"{index} 0 obj\n".encode("utf-8"))
        pdf_bytes.extend(obj)
        pdf_bytes.extend(b"\nendobj\n")

    startxref = len(pdf_bytes)
    pdf_bytes.extend(f"xref\n0 {len(objects) + 1}\n".encode("utf-8"))
    pdf_bytes.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf_bytes.extend(f"{offset:010d} 00000 n \n".encode("utf-8"))
    pdf_bytes.extend(
        (
            f"trailer\n<< /Root 1 0 R /Size {len(objects) + 1} >>\n"
            f"startxref\n{startxref}\n%%EOF\n"
        ).encode("utf-8")
    )

    return bytes(pdf_bytes)


MINIMAL_PDF_BYTES = build_pdf_bytes()


def pdf_checksum(content: bytes = MINIMAL_PDF_BYTES) -> str:
    """Return the expected SHA-256 checksum for the given PDF bytes."""
    return hashlib.sha256(content).hexdigest()


def create_upload_payload(
    name: str = "Test Document",
    filename: str = "test.pdf",
    content: bytes = MINIMAL_PDF_BYTES,
    content_type: str = "application/pdf",
):
    """Build multipart request data for document uploads."""
    return (
        {"name": name},
        {"file": (filename, content, content_type)},
    )
