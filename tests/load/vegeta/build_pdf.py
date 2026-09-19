"""Genera PDFs de N paginas con texto para las pruebas de carga.

Uso:
    python tests/load/vegeta/build_pdf.py salida.pdf --pages 279
    python tests/load/vegeta/build_pdf.py salida.pdf --pages 279 --seed 7

Cada pagina tiene varias lineas de texto para que la extraccion tenga
trabajo real. El `seed` cambia el contenido y por lo tanto el checksum,
lo que permite generar variantes distintas del mismo tamanio (el service
rechaza checksums repetidos).
"""

import argparse
from pathlib import Path

LINES_PER_PAGE = 40
PAGE_WIDTH = 595
PAGE_HEIGHT = 842
FONT_SIZE = 11
LINE_HEIGHT = 16
MARGIN = 50


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _page_stream(page_number: int, seed: int) -> bytes:
    parts = ["BT", f"/F1 {FONT_SIZE} Tf", f"{MARGIN} {PAGE_HEIGHT - MARGIN} Td"]
    for line in range(LINES_PER_PAGE):
        text = (
            f"Pagina {page_number} linea {line + 1} semilla {seed}: "
            f"texto de prueba para medir la extraccion de PDF."
        )
        parts.append(f"({_escape(text)}) Tj")
        parts.append(f"0 -{LINE_HEIGHT} Td")
    parts.append("ET")
    return ("\n".join(parts) + "\n").encode("latin-1")


def build_pdf(pages: int, seed: int = 0) -> bytes:
    """Arma un PDF valido de `pages` paginas con texto Helvetica."""
    # Objetos: 1 catalogo, 2 pages, 3 fuente, luego (page, contents) por pagina.
    objects: list[bytes] = []
    first_page_obj = 4
    kids = " ".join(f"{first_page_obj + 2 * i} 0 R" for i in range(pages))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for i in range(pages):
        page_obj = first_page_obj + 2 * i
        contents_obj = page_obj + 1
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} "
                f"{PAGE_HEIGHT}] /Contents {contents_obj} 0 R "
                f"/Resources << /Font << /F1 3 0 R >> >> >>"
            ).encode()
        )
        stream = _page_stream(i + 1, seed)
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"endstream"
        )

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    startxref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(
        (
            f"trailer\n<< /Root 1 0 R /Size {len(objects) + 1} >>\n"
            f"startxref\n{startxref}\n%%EOF\n"
        ).encode()
    )
    return bytes(pdf)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--pages", type=int, default=279)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    data = build_pdf(args.pages, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f"{args.output}: {args.pages} paginas, {len(data):,} bytes")


if __name__ == "__main__":
    main()
