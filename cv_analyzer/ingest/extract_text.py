"""Text ingestion: text passthrough + best-effort PDF/docx extraction.

Scope policy (DECISIONS.md menu 1, "1a + 1b"): text/paste is the first-class
input; PDF and docx are best-effort with graceful failure — on any parse
problem we return a failure asking the user to paste text, we never crash and
never retry indefinitely.

Safety rules implemented here:
- The user's filename is never used as a filesystem path. PDF/docx parsing
  works on in-memory bytes (BytesIO). Where a real temp file is unavoidable
  (some pdfminer paths), we generate an internal UUID name in a private temp
  dir and delete it immediately after use.
- Every parse runs under a hard timeout (config: ``parse_timeout_seconds``).
  On timeout/malformed content we fail closed with a paste-text request.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from pathlib import Path

from cv_analyzer.config import Config
from cv_analyzer.security.validate_upload import ValidationReport, validate_upload

DEFAULT_CONFIG = Config()


class IngestError(RuntimeError):
    """Raised when ingestion fails; user-facing message asks for pasted text."""


@dataclass(frozen=True)
class IngestResult:
    text: str
    source_name: str          # internal name — never the user's filename
    kind: str                 # "pdf" | "docx" | "text"
    warnings: list[str]


def _run_with_timeout(fn, seconds: float, *args):
    """Run ``fn`` in a worker thread; raise IngestError if it exceeds ``seconds``.

    ThreadPoolExecutor + future.result(timeout) gives us the same guard for
    CPU-bound parse calls that signal.alarm gives on POSIX — and works on
    Windows, where this project is developed.
    """
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(fn, *args)
        return future.result(timeout=seconds)
    except FutureTimeoutError as exc:
        raise IngestError(
            f"parsing timed out after {seconds:g}s — please paste the CV text instead"
        ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _extract_pdf(data: bytes) -> str:
    """Best-effort PDF text extraction. pdfminer.six first, pypdf fallback."""
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract

        text = _run_with_timeout(pdfminer_extract, DEFAULT_CONFIG.parse_timeout_seconds, io.BytesIO(data))
        if text and text.strip():
            return text
    except IngestError:
        raise
    except Exception:  # noqa: BLE001 — pdfminer can raise a wide variety of parse errors
        pass

    # fallback: pypdf
    from pypdf import PdfReader

    def _pypdf_read(buf: io.BytesIO) -> str:
        reader = PdfReader(buf)
        if getattr(reader, "is_encrypted", False):
            raise ValueError("encrypted PDF")
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    try:
        text = _run_with_timeout(_pypdf_read, DEFAULT_CONFIG.parse_timeout_seconds, io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise IngestError(
            "could not extract text from this PDF (it may be scanned or malformed) — "
            "please paste the CV text instead"
        ) from exc
    if not text.strip():
        raise IngestError(
            "this PDF contains no extractable text (likely a scan) — please paste the CV text instead"
        )
    return text


def _extract_docx(data: bytes) -> str:
    """Best-effort docx extraction with a bounded temp file (internal name)."""
    import docx

    tmp_dir = Path(tempfile.gettempdir()) / "cv_analyzer_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"{uuid.uuid4().hex}.docx"   # internal name, never user-supplied
    tmp_path.write_bytes(data)
    try:
        def _parse(path: Path) -> str:
            document = docx.Document(str(path))
            parts = [p.text for p in document.paragraphs]
            for table in document.tables:
                for row in table.rows:
                    parts.append(" | ".join(cell.text for cell in row.cells))
            return "\n".join(parts)

        text = _run_with_timeout(_parse, DEFAULT_CONFIG.parse_timeout_seconds, tmp_path)
    except IngestError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise IngestError(
            "could not read this docx file — please paste the CV text instead"
        ) from exc
    finally:
        _safe_delete(tmp_path)
    if not text.strip():
        raise IngestError("this docx appears to be empty — please paste the CV text instead")
    return text


def _safe_delete(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass  # best-effort cleanup; the temp dir is also swept on process start


def _sweep_stale_temp() -> None:
    """Remove leftover temp artifacts from previous runs (defensive hygiene)."""
    tmp_dir = Path(tempfile.gettempdir()) / "cv_analyzer_tmp"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)


def ingest_bytes(data: bytes, original_filename: str, config: Config | None = None) -> IngestResult:
    """Ingest untrusted bytes. Validation runs BEFORE any parsing library."""
    cfg = config or DEFAULT_CONFIG
    report: ValidationReport = validate_upload(data, original_filename, max_mb=cfg.max_upload_mb)
    if not report.ok:
        raise IngestError(f"upload rejected: {report.error_message}")

    internal_name = f"upload_{uuid.uuid4().hex[:12]}"
    if report.kind == "text":
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("latin-1")
        return IngestResult(text=text, source_name=internal_name, kind="text", warnings=[])
    if report.kind == "pdf":
        return IngestResult(text=_extract_pdf(data), source_name=internal_name, kind="pdf", warnings=[
            "PDF extraction is best-effort; check the report against your original file."
        ])
    if report.kind == "docx":
        return IngestResult(text=_extract_docx(data), source_name=internal_name, kind="docx", warnings=[])
    raise IngestError(f"unsupported file kind {report.kind!r}")


def ingest_text(text: str, config: Config | None = None) -> IngestResult:
    """First-class path: pasted/known-clean text, no validation gauntlet."""
    cfg = config or DEFAULT_CONFIG
    if len(text.encode("utf-8")) > cfg.max_upload_mb * 1024 * 1024:
        raise IngestError(f"text exceeds the {cfg.max_upload_mb:g} MB cap")
    return IngestResult(text=text, source_name=f"paste_{uuid.uuid4().hex[:12]}", kind="text", warnings=[])


_sweep_stale_temp()
