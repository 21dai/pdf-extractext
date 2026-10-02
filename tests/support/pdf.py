"""Shared PDF fixtures and helpers for API tests."""

DEFAULT_PDF_TEXT = "Test Document Content"


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _assemble_pdf(stream_bytes: bytes, media_box: str) -> bytes:
    """Wrap a content stream in a valid single-page PDF using Helvetica."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [{media_box}] ".encode("utf-8")
            + b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
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


def build_pdf_bytes(text: str = DEFAULT_PDF_TEXT) -> bytes:
    """Build a minimal valid single-page PDF containing the given text."""
    stream = f"BT\n/F1 18 Tf\n50 100 Td\n({_escape_pdf_text(text)}) Tj\nET\n"
    return _assemble_pdf(stream.encode("utf-8"), "0 0 300 144")


def build_pdf_with_lines(lines: list[tuple[str, float]]) -> bytes:
    """Build a single-page PDF with one text line per (text, font size), top-down.

    Lets the Markdown tests control which lines are bigger than the body text.
    """
    commands = []
    y = 760.0
    for text, size in lines:
        commands.append(
            f"BT\n/F1 {size} Tf\n50 {y:.0f} Td\n({_escape_pdf_text(text)}) Tj\nET\n"
        )
        y -= size * 2
    return _assemble_pdf("".join(commands).encode("latin-1"), "0 0 612 792")


MINIMAL_PDF_BYTES = build_pdf_bytes()
SHA256_MINIMAL_PDF = "21963b097010d276edb6a984f1dd54cb5c7c762222c4aeed1c6a436b75f4eb4f"


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
