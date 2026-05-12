"""Unit tests for app.core.validators.

These tests cover success and failure paths for each validator function.
All functions are pure (no DB, no I/O), so they run fast and in isolation.
"""

import hashlib

import pytest

from app.core.validators import (
    MAX_DOCUMENT_NAME_LENGTH,
    MAX_ORIGINAL_FILENAME_LENGTH,
    MAX_PAGINATION_LIMIT,
    calculate_checksum,
    validate_document_id,
    validate_document_name,
    validate_original_filename,
    validate_pdf_extension,
    validate_pdf_file_on_disk,  # tested via a temp file
    validate_pdf_signature,
    validate_pdf_size,
    validate_pagination,
    validate_unique_checksum,
)


# ---------------------------------------------------------------------------
# validate_document_name
# ---------------------------------------------------------------------------
class TestValidateDocumentName:
    def test_valid_name(self):
        assert validate_document_name("Contract") == "Contract"

    def test_name_with_whitespace(self):
        assert validate_document_name("  Contract  ") == "Contract"

    def test_blank_name(self):
        with pytest.raises(ValueError, match="Document name is required"):
            validate_document_name("   ")

    def test_none_name(self):
        with pytest.raises(ValueError, match="Document name is required"):
            validate_document_name(None)

    def test_empty_string(self):
        with pytest.raises(ValueError, match="Document name is required"):
            validate_document_name("")

    def test_name_too_long(self):
        long_name = "A" * (MAX_DOCUMENT_NAME_LENGTH + 1)
        with pytest.raises(ValueError, match="must not exceed"):
            validate_document_name(long_name)

    def test_name_exactly_max_length(self):
        name = "A" * MAX_DOCUMENT_NAME_LENGTH
        assert validate_document_name(name) == name

    def test_non_string_name(self):
        with pytest.raises(ValueError, match="must be a string"):
            validate_document_name(123)


# ---------------------------------------------------------------------------
# validate_original_filename
# ---------------------------------------------------------------------------
class TestValidateOriginalFilename:
    def test_valid_filename(self):
        assert validate_original_filename("doc.pdf") == "doc.pdf"

    def test_filename_with_path(self):
        # Should strip to basename
        assert validate_original_filename("/path/to/doc.pdf") == "doc.pdf"
        assert validate_original_filename("../../../etc/passwd") == "passwd"

    def test_none_filename(self):
        with pytest.raises(ValueError, match="A PDF file is required"):
            validate_original_filename(None)

    def test_empty_filename(self):
        with pytest.raises(ValueError, match="A PDF file is required"):
            validate_original_filename("   ")

    def test_filename_too_long(self):
        long_filename = "A" * (MAX_ORIGINAL_FILENAME_LENGTH + 1)
        with pytest.raises(ValueError, match="must not exceed"):
            validate_original_filename(long_filename)


# ---------------------------------------------------------------------------
# validate_pdf_extension
# ---------------------------------------------------------------------------
class TestValidatePdfExtension:
    def test_valid_pdf(self):
        assert validate_pdf_extension("document.pdf") is None

    def test_uppercase_pdf(self):
        assert validate_pdf_extension("document.PDF") is None

    def test_non_pdf_extension(self):
        with pytest.raises(ValueError, match="Only PDF files are allowed"):
            validate_pdf_extension("document.txt")

    def test_double_extension(self):
        with pytest.raises(ValueError, match="Only PDF files are allowed"):
            validate_pdf_extension("file.pdf.exe")

    def test_no_extension(self):
        with pytest.raises(ValueError, match="Only PDF files are allowed"):
            validate_pdf_extension("document")


# ---------------------------------------------------------------------------
# validate_pdf_size
# ---------------------------------------------------------------------------
class TestValidatePdfSize:
    def test_valid_size(self):
        content = b"%PDF-1.4 some content"
        assert validate_pdf_size(content, max_size_bytes=1024) is None

    def test_empty_content(self):
        with pytest.raises(ValueError, match="empty content"):
            validate_pdf_size(b"", max_size_bytes=1024)

    def test_oversized(self):
        content = b"%PDF-1.4 " + b"x" * 1000
        with pytest.raises(ValueError, match="exceeds maximum"):
            validate_pdf_size(content, max_size_bytes=500)

    def test_exactly_max_size(self):
        max_size = 100
        content = b"%PDF-1.4" + b"x" * (max_size - 8)
        assert validate_pdf_size(content, max_size_bytes=max_size) is None

    def test_max_size_minus_one(self):
        max_size = 100
        content = b"%PDF-1.4" + b"x" * (max_size - 9)
        assert validate_pdf_size(content, max_size_bytes=max_size) is None

    def test_max_size_plus_one(self):
        max_size = 100
        content = b"%PDF-1.4" + b"x" * (max_size - 7)
        with pytest.raises(ValueError, match="exceeds maximum"):
            validate_pdf_size(content, max_size_bytes=max_size)


# ---------------------------------------------------------------------------
# validate_pdf_signature
# ---------------------------------------------------------------------------
class TestValidatePdfSignature:
    def test_valid_signature(self):
        assert validate_pdf_signature(b"%PDF-1.4") is None

    def test_valid_signature_variation(self):
        assert validate_pdf_signature(b"%PDF-1.7") is None

    def test_missing_signature(self):
        with pytest.raises(ValueError, match="missing PDF signature"):
            validate_pdf_signature(b"this is not a pdf")

    def test_empty_bytes(self):
        with pytest.raises(ValueError, match="missing PDF signature"):
            validate_pdf_signature(b"")

    def test_signature_at_wrong_position(self):
        # signature not at start
        with pytest.raises(ValueError, match="missing PDF signature"):
            validate_pdf_signature(b"prefix%PDF-1.4")

    def test_partial_signature(self):
        with pytest.raises(ValueError, match="missing PDF signature"):
            validate_pdf_signature(b"%PDF")  # missing the dash


# ---------------------------------------------------------------------------
# calculate_checksum
# ---------------------------------------------------------------------------
class TestCalculateChecksum:
    def test_known_hash(self):
        content = b"hello world"
        expected = hashlib.sha256(content).hexdigest()
        assert calculate_checksum(content) == expected

    def test_empty_hash(self):
        assert calculate_checksum(b"") == hashlib.sha256(b"").hexdigest()

    def test_different_content(self):
        h1 = calculate_checksum(b"a")
        h2 = calculate_checksum(b"b")
        assert h1 != h2

    def test_same_content_same_hash(self):
        assert calculate_checksum(b"x") == calculate_checksum(b"x")


# ---------------------------------------------------------------------------
# validate_unique_checksum
# ---------------------------------------------------------------------------
class TestValidateUniqueChecksum:
    def test_unique_checksum(self):
        # None means no existing document - should not raise
        assert validate_unique_checksum("abc123", existing_document=None) is None

    def test_duplicate_checksum(self):
        class FakeDoc:
            pass

        with pytest.raises(ValueError, match="same checksum already exists"):
            validate_unique_checksum("abc123", existing_document=FakeDoc())


# ---------------------------------------------------------------------------
# validate_pagination
# ---------------------------------------------------------------------------
class TestValidatePagination:
    def test_defaults(self):
        assert validate_pagination(0, 10) == (0, 10)

    def test_positive_values(self):
        assert validate_pagination(5, 20) == (5, 20)

    def test_negative_skip(self):
        with pytest.raises(ValueError, match="skip must be a non-negative"):
            validate_pagination(-1, 10)

    def test_negative_limit(self):
        with pytest.raises(ValueError, match="limit must be a positive"):
            validate_pagination(0, -5)

    def test_limit_too_high(self):
        # Should cap to MAX_PAGINATION_LIMIT
        skip, limit = validate_pagination(0, 999)
        assert limit == MAX_PAGINATION_LIMIT
        assert skip == 0

    def test_zero_limit(self):
        with pytest.raises(ValueError, match="limit must be a positive"):
            validate_pagination(0, 0)

    def test_invalid_types(self):
        with pytest.raises(ValueError, match="skip must be a non-negative"):
            validate_pagination("five", 10)
        with pytest.raises(ValueError, match="limit must be a positive"):
            validate_pagination(0, "ten")

    def test_limit_exactly_max(self):
        assert validate_pagination(0, MAX_PAGINATION_LIMIT) == (0, MAX_PAGINATION_LIMIT)


# ---------------------------------------------------------------------------
# validate_document_id
# ---------------------------------------------------------------------------
class TestValidateDocumentId:
    def test_valid_id(self):
        assert validate_document_id(1) == 1
        assert validate_document_id(42) == 42

    def test_zero(self):
        with pytest.raises(ValueError, match="must be a positive integer"):
            validate_document_id(0)

    def test_negative(self):
        with pytest.raises(ValueError, match="must be a positive integer"):
            validate_document_id(-5)

    def test_non_int(self):
        with pytest.raises(ValueError, match="must be a positive integer"):
            validate_document_id("abc")

    def test_float(self):
        with pytest.raises(ValueError, match="must be a positive integer"):
            validate_document_id(3.14)


# ---------------------------------------------------------------------------
# validate_pdf_file_on_disk (legacy)
# ---------------------------------------------------------------------------
class TestValidatePdfFileOnDisk:
    def test_valid_pdf_file(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        content = b"%PDF-1.4 test content for disk validation"
        pdf.write_bytes(content)

        # Should not raise
        assert validate_pdf_file_on_disk(pdf, len(content), 1024) is None

    def test_file_not_found(self, tmp_path):
        missing = tmp_path / "missing.pdf"
        with pytest.raises(ValueError, match="File not found"):
            validate_pdf_file_on_disk(missing, 100, 1024)

    def test_wrong_extension(self, tmp_path):
        txt = tmp_path / "test.txt"
        txt.write_bytes(b"%PDF-1.4 some text")
        with pytest.raises(ValueError, match="Only PDF files are allowed"):
            validate_pdf_file_on_disk(txt, 17, 1024)

    def test_size_mismatch(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        content = b"%PDF-1.4 test"
        pdf.write_bytes(content)
        with pytest.raises(ValueError, match="size mismatch"):
            validate_pdf_file_on_disk(pdf, 999, 1024)

    def test_oversized_file(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        content = b"%PDF-1.4 " + b"x" * 200
        pdf.write_bytes(content)
        with pytest.raises(ValueError, match="exceeds maximum"):
            validate_pdf_file_on_disk(pdf, len(content), 100)

    def test_invalid_signature(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"not a pdf signature but has .pdf extension")
        with pytest.raises(ValueError, match="missing PDF signature"):
            validate_pdf_file_on_disk(pdf, len(pdf.read_bytes()), 1024)
