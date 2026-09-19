"""Genera los archivos de targets para Vegeta.

Uso:
    python tests/load/vegeta/make_targets.py SALIDA --base-url http://localhost:8000 \
        --pages 279 --variants 60 --document-id 1

Crea en SALIDA:
    health.txt       GET /health
    get_document.txt GET /api/v1/documents/{document-id}
    post_document.txt POST /api/v1/documents, un PDF distinto por linea
    bodies/*.bin     cuerpos multipart de cada POST

Vegeta recorre los targets en orden y vuelve a empezar, por eso `variants`
debe ser >= rate * duration si se quiere que ningun POST repita checksum.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_pdf import build_pdf  # noqa: E402

BOUNDARY = "vegetaBoundary7f3a9c1e"


def multipart_body(name: str, filename: str, pdf: bytes) -> bytes:
    """Arma a mano el cuerpo multipart/form-data que espera el endpoint."""
    crlf = b"\r\n"
    boundary = f"--{BOUNDARY}".encode()
    parts = [
        boundary,
        b'Content-Disposition: form-data; name="name"',
        b"",
        name.encode(),
        boundary,
        (
            f'Content-Disposition: form-data; name="file"; filename="{filename}"'
        ).encode(),
        b"Content-Type: application/pdf",
        b"",
        pdf,
        boundary + b"--",
        b"",
    ]
    return crlf.join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--pages", type=int, default=279)
    parser.add_argument("--variants", type=int, default=60)
    parser.add_argument("--document-id", type=int, default=1)
    args = parser.parse_args()

    out = args.output
    bodies = out / "bodies"
    bodies.mkdir(parents=True, exist_ok=True)
    api = f"{args.base_url}/api/v1/documents"

    (out / "health.txt").write_text(f"GET {args.base_url}/health\n", newline="\n")
    (out / "get_document.txt").write_text(
        f"GET {api}/{args.document_id}\n", newline="\n"
    )

    lines = []
    total = 0
    for seed in range(args.variants):
        pdf = build_pdf(args.pages, seed)
        body = multipart_body(
            f"vegeta {args.pages}p seed {seed}", f"vegeta_{seed}.pdf", pdf
        )
        path = bodies / f"post_{seed}.bin"
        path.write_bytes(body)
        total += len(body)
        lines.append(
            f"POST {api}\n"
            f"Content-Type: multipart/form-data; boundary={BOUNDARY}\n"
            f"@{path.resolve()}\n"
        )
    (out / "post_document.txt").write_text("\n".join(lines), newline="\n")

    print(f"targets en {out}")
    print(f"  {args.variants} PDFs de {args.pages} paginas, {total / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
