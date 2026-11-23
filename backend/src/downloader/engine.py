"""Download engine for student submission files from Zajuna.

Downloads files sequentially with human-like delays, renames them
with incremental IDs and student names, and tracks progress.
"""
from __future__ import annotations

import logging
import re
import shutil
import threading
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from src.client.zajuna import ZajunaClient
from src.parsers.submissions_list import SubmissionsPage

logger = logging.getLogger(__name__)

# Characters invalid in Windows filenames
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*]')


@dataclass
class DownloadConfig:
    """Configuration for a download job."""

    target_dir: str
    include_instrument: bool = True
    status_filter: list[str] = field(default_factory=lambda: ["Enviado para calificar"])


@dataclass
class DownloadProgress:
    """Mutable progress state for a download job."""

    total_files: int = 0
    downloaded: int = 0
    current_file: str | None = None
    errors: list[str] = field(default_factory=list)
    status: str = "pending"  # pending | running | completed | failed
    files: list[str] = field(default_factory=list)
    folder_path: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "total_files": self.total_files,
                "downloaded": self.downloaded,
                "current_file": self.current_file,
                "errors": list(self.errors),
                "status": self.status,
                "files": list(self.files),
                "folder_path": self.folder_path,
            }


@dataclass
class BatchItem:
    """One assignment inside a batch download."""

    cmid: int
    name: str | None = None
    progress: DownloadProgress = field(default_factory=DownloadProgress)


@dataclass
class BatchDownloadProgress:
    """Progress of several assignments downloaded one after another."""

    items: list[BatchItem]
    status: str = "pending"  # pending | running | completed | failed
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def to_dict(self) -> dict:
        with self._lock:
            status = self.status
        items = []
        current_file = None
        for item in self.items:
            data = item.progress.to_dict()
            items.append({
                "cmid": item.cmid,
                "name": item.name,
                "status": data["status"],
                "total_files": data["total_files"],
                "downloaded": data["downloaded"],
                "folder_path": data["folder_path"],
                "errors": data["errors"],
            })
            if data["status"] == "running" and data["current_file"]:
                current_file = data["current_file"]
        return {
            "status": status,
            "total_files": sum(i["total_files"] for i in items),
            "downloaded": sum(i["downloaded"] for i in items),
            "current_file": current_file,
            "items": items,
        }


def sanitize_filename(name: str) -> str:
    """Remove invalid characters for Windows filenames."""
    sanitized = _INVALID_CHARS.sub("", name)
    # Collapse multiple spaces
    sanitized = " ".join(sanitized.split())
    # Remove trailing dots/spaces (Windows restriction)
    sanitized = sanitized.rstrip(". ")
    return sanitized or "file"


def build_filename(index: int, full_name: str, extension: str, file_index: int | None = None) -> str:
    """Build a filename with incremental ID and student name.

    Args:
        index: Sequential number (0 for instrument, 1+ for students).
        full_name: Student full name or "INSTRUMENTO DE EVALUACION".
        extension: File extension including dot (e.g., ".pdf").
        file_index: For multiple files per student, 1-based sub-index.

    Returns:
        Sanitized filename like "01 CHRISTIAN ANDRES BARAJAS.pdf"
        or "01 NOMBRE - 1.pdf" for multiple files.
    """
    prefix = f"{index:02d} {full_name}"
    if file_index is not None:
        prefix = f"{prefix} - {file_index}"
    return sanitize_filename(f"{prefix}{extension}")


def get_extension(filename: str) -> str:
    """Extract file extension from a filename, defaulting to .pdf."""
    if "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    return ".pdf"


_ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z"}


def _extract_archive(file_path: Path) -> bool:
    """Extract a .zip/.rar archive into a folder with the same base name.

    The archive file is deleted after successful extraction.
    Returns True if extraction succeeded.
    """
    ext = file_path.suffix.lower()
    dest = file_path.with_suffix("")  # e.g. "01 NOMBRE.zip" → "01 NOMBRE/"

    if ext == ".zip":
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                zf.extractall(dest)
            file_path.unlink()
            logger.info("Extracted ZIP: %s → %s", file_path.name, dest.name)
            return True
        except (zipfile.BadZipFile, Exception) as exc:
            logger.warning("Failed to extract ZIP %s: %s", file_path.name, exc)
            return False

    if ext in (".rar", ".7z"):
        # Try using system tools (unrar / 7z) if available
        unrar = shutil.which("unrar")
        seven_z = shutil.which("7z")

        if ext == ".rar" and unrar:
            import subprocess
            dest.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                [unrar, "x", "-y", str(file_path), str(dest) + "/"],
                capture_output=True, timeout=120,
            )
            if result.returncode == 0:
                file_path.unlink()
                logger.info("Extracted RAR: %s → %s", file_path.name, dest.name)
                return True
            logger.warning("unrar failed for %s: %s", file_path.name, result.stderr.decode(errors="ignore"))
            return False

        if seven_z:
            import subprocess
            dest.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                [seven_z, "x", f"-o{dest}", "-y", str(file_path)],
                capture_output=True, timeout=120,
            )
            if result.returncode == 0:
                file_path.unlink()
                logger.info("Extracted archive: %s → %s", file_path.name, dest.name)
                return True
            logger.warning("7z failed for %s: %s", file_path.name, result.stderr.decode(errors="ignore"))
            return False

        logger.warning(
            "Cannot extract %s: no unrar/7z found. Keeping archive as-is.",
            file_path.name,
        )
    return False


class DownloadEngine:
    """Sequential file downloader with progress tracking."""

    def __init__(self, client: ZajunaClient) -> None:
        self.client = client

    def execute(
        self,
        submissions: SubmissionsPage,
        config: DownloadConfig,
        progress: DownloadProgress,
    ) -> None:
        """Download files to disk. Updates progress in-place.

        This method is designed to run in a background thread.
        """
        with progress._lock:
            progress.status = "running"

        try:
            self._do_execute(submissions, config, progress)
        except Exception as exc:
            logger.exception("Download job failed: %s", exc)
            with progress._lock:
                progress.status = "failed"
                progress.errors.append(f"Fatal: {exc}")

    def execute_batch(
        self,
        pages: Callable[[int], SubmissionsPage],
        config: DownloadConfig,
        batch: BatchDownloadProgress,
    ) -> None:
        """Download several assignments in order with the same session.

        ``pages`` fetches the submissions page of one cmid. A failure in one
        assignment is recorded on its item and the batch moves on.
        """
        with batch._lock:
            batch.status = "running"
        for item in batch.items:
            try:
                page = pages(item.cmid)
            except Exception as exc:
                logger.error("Batch: could not read cmid=%d: %s", item.cmid, exc)
                with item.progress._lock:
                    item.progress.status = "failed"
                    item.progress.errors.append(f"No se pudo leer la tarea: {exc}")
                continue
            item.name = page.assignment_name
            self.execute(page, config, item.progress)
        with batch._lock:
            batch.status = "completed"

    def _do_execute(
        self,
        submissions: SubmissionsPage,
        config: DownloadConfig,
        progress: DownloadProgress,
    ) -> None:
        # Create target folder: {target_dir}/{assignment_name}/
        folder_name = sanitize_filename(submissions.assignment_name)
        folder = Path(config.target_dir) / folder_name
        folder.mkdir(parents=True, exist_ok=True)

        with progress._lock:
            progress.folder_path = str(folder)

        # Filter entries by status and grading state.
        # Moodle shows "Enviado para calificar" + "Calificado" together
        # for already-graded submissions. When the filter is
        # "Enviado para calificar", exclude those already graded.
        filtered = [
            e for e in submissions.entries
            if e.status in config.status_filter
            and e.file_urls
            and not (e.status == "Enviado para calificar" and e.is_graded)
        ]

        # Count total files
        total = sum(len(e.file_urls) for e in filtered)
        if config.include_instrument and submissions.instrument_url:
            total += 1

        with progress._lock:
            progress.total_files = total

        student_index = 1

        # Download instrument as "00 INSTRUMENTO DE EVALUACION.ext"
        if config.include_instrument and submissions.instrument_url:
            with progress._lock:
                progress.current_file = "INSTRUMENTO DE EVALUACION"
            try:
                content, orig_name = self.client.download_file(
                    submissions.instrument_url
                )
                ext = get_extension(
                    submissions.instrument_name or orig_name
                )
                fname = build_filename(0, "INSTRUMENTO DE EVALUACION", ext)
                (folder / fname).write_bytes(content)
                with progress._lock:
                    progress.downloaded += 1
                    progress.files.append(fname)
                logger.info("Downloaded instrument: %s", fname)
            except Exception as exc:
                logger.error("Failed to download instrument: %s", exc)
                with progress._lock:
                    progress.errors.append(f"Instrument: {exc}")

        # Download student files
        for entry in filtered:
            num_files = len(entry.file_urls)
            for i, (url, orig_name) in enumerate(
                zip(entry.file_urls, entry.file_names, strict=False)
            ):
                with progress._lock:
                    progress.current_file = entry.full_name

                ext = get_extension(orig_name)
                file_idx = (i + 1) if num_files > 1 else None
                fname = build_filename(student_index, entry.full_name, ext, file_idx)

                try:
                    content, _ = self.client.download_file(url)
                    file_path = folder / fname
                    file_path.write_bytes(content)

                    # Auto-extract archives (.zip, .rar, .7z)
                    if ext.lower() in _ARCHIVE_EXTENSIONS:
                        _extract_archive(file_path)

                    with progress._lock:
                        progress.downloaded += 1
                        progress.files.append(fname)
                    logger.info("Downloaded: %s", fname)
                except Exception as exc:
                    logger.error("Failed to download %s: %s", fname, exc)
                    with progress._lock:
                        progress.errors.append(f"{entry.full_name}: {exc}")

            student_index += 1

        with progress._lock:
            progress.current_file = None
            progress.status = "completed"
        logger.info(
            "Download complete: %d/%d files in %s",
            progress.downloaded, progress.total_files, folder,
        )
