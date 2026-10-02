"""Unit tests for the Markdown conversion of extracted PDF lines.

`to_markdown` is pure: it receives the lines of each page with the height of
their letters and returns Markdown, so every rule is tested without a PDF.
"""

from app.core.markdown import TextLine, to_markdown

BODY = 12.0
LONG_BODY = "Texto del cuerpo con suficientes palabras para dominar la medicion"
# Marca que PDFium deja donde el PDF cortaba una palabra con guion.
HYPHENATION_MARK = chr(0xFFFE)


def page(*lines: tuple[str, float]) -> list[TextLine]:
    return [TextLine(text, height) for text, height in lines]


class TestHeadings:
    def test_heading_level_depends_on_how_much_bigger_than_the_body(self):
        markdown = to_markdown(
            [
                page(
                    ("Titulo", 24),
                    (LONG_BODY, BODY),
                    ("Seccion", 18),
                    (LONG_BODY, BODY),
                    ("Subseccion", 14),
                )
            ]
        )

        assert markdown == (
            f"# Titulo\n\n{LONG_BODY}\n\n## Seccion\n\n{LONG_BODY}\n\n### Subseccion"
        )

    def test_consecutive_lines_of_the_same_heading_are_merged(self):
        markdown = to_markdown(
            [page(("Informacion necesaria", 24), ("de usuario", 24), (LONG_BODY, BODY))]
        )

        assert markdown == f"# Informacion necesaria de usuario\n\n{LONG_BODY}"

    def test_long_lines_are_never_headings(self):
        long_line = "Una linea grande que en realidad es un parrafo destacado " * 2

        markdown = to_markdown([page((long_line.strip(), 24), (LONG_BODY, BODY))])

        assert not markdown.startswith("#")

    def test_lines_without_letters_are_never_headings(self):
        markdown = to_markdown([page(("123", 30), (LONG_BODY, BODY))])

        assert markdown == f"123\n{LONG_BODY}"

    def test_lines_whose_height_could_not_be_measured_are_body(self):
        markdown = to_markdown([page(("Titulo", 0), (LONG_BODY, BODY))])

        assert markdown == f"Titulo\n{LONG_BODY}"


class TestBody:
    def test_empty_line_separates_paragraphs(self):
        markdown = to_markdown(
            [page(("primer parrafo", BODY), ("", 0), ("segundo", BODY))]
        )

        assert markdown == "primer parrafo\n\nsegundo"

    def test_pages_are_separated_by_a_blank_line(self):
        markdown = to_markdown([page(("pagina uno", BODY)), page(("pagina dos", BODY))])

        assert markdown == "pagina uno\n\npagina dos"

    def test_bullets_become_list_items(self):
        markdown = to_markdown(
            [
                page(
                    ("Introduccion al tema", BODY),
                    ("• primer punto", BODY),
                    ("● segundo punto", BODY),
                    ("continuacion del segundo punto", BODY),
                )
            ]
        )

        assert markdown == (
            "Introduccion al tema\n\n- primer punto\n- segundo punto\n"
            "continuacion del segundo punto"
        )

    def test_markdown_symbols_at_the_start_of_body_lines_are_escaped(self):
        markdown = to_markdown(
            [page(("# no es un titulo", BODY), (">no es cita", BODY))]
        )

        assert markdown == "\\# no es un titulo\n\\>no es cita"

    def test_hyphenation_marks_from_pdfium_are_removed(self):
        markdown = to_markdown(
            [page((f"los pro{HYPHENATION_MARK}cesos actuales", BODY))]
        )

        assert markdown == "los procesos actuales"

    def test_document_without_text_is_empty(self):
        assert to_markdown([page(), page(("", 0))]) == ""
