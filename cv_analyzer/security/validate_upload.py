"""Upload validation — every uploaded CV is untrusted input.

Checks, in order:
1. Size cap (rejected *before* any parsing attempt).
2. Extension allow-list.
3. Magic-byte content check — a renamed ``.exe`` or a ``.txt`` carrying a
   ``.pdf`` extension is caught here, not by the parser.
4. Zip-bomb guard for docx (total uncompressed size capped before reading).

No user-supplied filename is ever used as a filesystem path; ingestion works
on in-memory bytes (BytesIO), and any temp artifact uses an internal UUID name
(see ``ingest/extract_text.py``).
"""
from __future__ import annotations

import io
import os
import zipfile
from dataclasses import dataclass

MAX_ZIP_ENTRIES = 2_000

# extensions we accept, mapped to a human-readable type name
ALLOWED_EXTENSIONS: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "text",
    ".md": "text",
}


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    kind: str          # "pdf" | "docx" | "text" | ""
    errors: list[str]
    size_bytes: int

    @property
    def error_message(self) -> str:
        return "; ".join(self.errors)


def _looks_like_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


def _looks_like_docx(data: bytes) -> bool:
    # docx is a ZIP container; Office files also carry a PK header.
    return len(data) > 4 and data[:2] == b"PK"


def _looks_like_text(data: bytes) -> bool:
    """Heuristic: decodable as UTF-8/latin-1 with no control blobs."""
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        try:
            data.decode("latin-1")
        except UnicodeDecodeError:
            return False
    # null-byte blobs are binary even when latin-1 decodes
    return b"\x00" not in data[:1024]


def _safe_zip_info(data: bytes, max_total_uncompressed: int) -> list[str]:
    """Inspect a zip container without extracting. Returns a list of problems."""
    problems: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                problems.append(f"archive contains too many entries ({len(infos)})")
            total = sum(i.file_size for i in infos)
            if total > max_total_uncompressed:
                problems.append(
                    f"uncompressed archive size {total} exceeds cap {max_total_uncompressed} (possible zip bomb)"
                )
            for info in infos:
                if info.file_size > max_total_uncompressed:
                    problems.append(f"entry {info.filename!r} uncompressed size exceeds cap")
                    break
    except zipfile.BadZipFile:
        problems.append("declared docx but content is not a valid zip archive")
    return problems


def validate_upload(
    data: bytes,
    original_filename: str,
    max_mb: float = 5.0,
    ) -> ValidationReport:
    """Run all pre-parse safety checks on an upload.

    ``original_filename`` is used ONLY for its extension — never as a path.
    """
    errors: list[str] = []
    size = len(data)

    if size == 0:
        return ValidationReport(False, "", ["file is empty"], 0)

    if size > max_mb * 1024 * 1024:
        return ValidationReport(False, "", [f"file exceeds the {max_mb:g} MB size cap ({size} bytes)"], size)

    ext = os.path.splitext(original_filename.lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        errors.append(f"extension {ext or '(none)'} is not allowed (allowed: {sorted(ALLOWED_EXTENSIONS)})")
        return ValidationReport(False, "", errors, size)

    declared = ALLOWED_EXTENSIONS[ext]

    # content-vs-extension agreement (magic bytes)
    if declared == "pdf" and not _looks_like_pdf(data):
        errors.append("declared PDF but content does not start with a PDF signature (possible renamed file)")
    elif declared == "docx":
        if not _looks_like_docx(data):
            errors.append("declared docx but content lacks a zip/Office signature (possible renamed file)")
        else:
            errors.extend(_safe_zip_info(data, max_mb * 4 * 1024 * 1024))
    elif declared == "text":
        # accept text bytes regardless of declared pdf/docx? No — text ext must be text-like
        if not _looks_like_text(data):
            errors.append("declared text but content is not decodable text (possible binary file)")

    # Content that contradicts the declared type is a hard error, EXCEPT:
    # a .txt that actually contains a PDF/zip is still rejected (mismatch), and
    # a .pdf/.docx that is plain text is rejected too.
    if not errors and declared == "text" and (_looks_like_pdf(data) or _looks_like_docx(data)):
        errors.append("declared text but content is a PDF/zip container (mismatched content)")

    return ValidationReport(ok=not errors, kind=declared if not errors else "", errors=errors, size_bytes=size)
