"""Conversion of extracted PDF lines to Markdown.

PDFium entrega el texto de cada pagina linea por linea; para cada linea se
mide la altura de sus letras. Con eso alcanza para reconstruir la estructura
que importa en un documento: los titulos son las lineas cortas con letra
claramente mas grande que la del cuerpo. Es una heuristica deliberadamente
simple: no agrega dependencias (las librerias que generan Markdown de PDF son
AGPL o usan modelos de ML) y casi no suma tiempo a la extraccion.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

# Cuanto mas grande que el cuerpo tiene que ser la letra para cada nivel.
HEADING_LEVELS = ((1.8, "#"), (1.35, "##"), (1.15, "###"))
MAX_HEADING_LENGTH = 100
BULLETS = frozenset("•●▪◦‣∙·–-*")
# PDFium marca con U+FFFE el lugar donde el PDF cortaba una palabra con guion.
HYPHENATION_MARK = chr(0xFFFE)
ESCAPED_LINE_STARTS = ("#", ">")


@dataclass(frozen=True, slots=True)
class TextLine:
    """A line of text and the height of its letters, in points (0 if unknown)."""

    text: str
    height: float


def to_markdown(pages: Sequence[Sequence[TextLine]]) -> str:
    """Convert the lines of every page to a Markdown document."""
    builder = _MarkdownBuilder(body_height=_body_height(pages))
    for page in pages:
        builder.paragraph_break()  # cada pagina empieza un parrafo nuevo
        for line in page:
            builder.add(line)
    return builder.build()


def _body_height(pages: Sequence[Sequence[TextLine]]) -> float:
    """Most common letter height, weighted by characters: the body text."""
    heights: Counter[float] = Counter()
    for page in pages:
        for line in page:
            if line.height > 0:
                heights[round(line.height, 1)] += len(line.text)
    return heights.most_common(1)[0][0] if heights else 0.0


class _MarkdownBuilder:
    """Accumulate output lines, with "" as paragraph break."""

    def __init__(self, body_height: float):
        self.body_height = body_height
        self.lines: list[str] = []
        # Altura de la ultima linea si fue titulo: un titulo partido en dos
        # lineas tiene las dos con la misma altura.
        self.heading_height: float | None = None

    def paragraph_break(self) -> None:
        self.lines.append("")
        self.heading_height = None

    def add(self, line: TextLine) -> None:
        text = line.text.replace(HYPHENATION_MARK, "").strip()
        if not text:
            self.paragraph_break()
            return

        marker = self._heading_marker(line, text)
        if marker:
            self._add_heading(marker, text, line.height)
            return

        self.heading_height = None
        if text[0] in BULLETS and len(text) > 1 and text[1].isspace():
            if self.lines and self.lines[-1] and not self.lines[-1].startswith("- "):
                self.lines.append("")
            self.lines.append("- " + text[2:].strip())
            return

        if text.startswith(ESCAPED_LINE_STARTS):
            text = "\\" + text
        self.lines.append(text)

    def build(self) -> str:
        """Join the lines, collapsing consecutive paragraph breaks into one."""
        output: list[str] = []
        for line in self.lines:
            if line or (output and output[-1]):
                output.append(line)
        return "\n".join(output).strip()

    def _heading_marker(self, line: TextLine, text: str) -> str | None:
        if self.body_height <= 0 or line.height <= 0:
            return None
        if len(text) > MAX_HEADING_LENGTH or not any(c.isalpha() for c in text):
            return None
        ratio = line.height / self.body_height
        for minimum_ratio, marker in HEADING_LEVELS:
            if ratio >= minimum_ratio:
                return marker
        return None

    def _add_heading(self, marker: str, text: str, height: float) -> None:
        # Un titulo deja [..., "# Titulo", ""]: si la linea anterior fue un
        # titulo de la misma altura, es el mismo titulo partido en dos lineas.
        if self.heading_height == height and len(self.lines) >= 2:
            self.lines[-2] = f"{self.lines[-2]} {text}"
            return
        self.lines.extend(["", f"{marker} {text}", ""])
        self.heading_height = height
