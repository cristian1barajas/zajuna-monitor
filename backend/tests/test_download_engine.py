"""Tests for the download engine."""
from unittest.mock import MagicMock

from src.downloader.engine import (
    DownloadConfig,
    DownloadEngine,
    DownloadProgress,
    build_filename,
    get_extension,
    sanitize_filename,
)
from src.parsers.submissions_list import SubmissionEntry, SubmissionsPage


class TestSanitizeFilename:
    def test_removes_invalid_chars(self):
        assert sanitize_filename('file<>:"/\\|?*.pdf') == "file.pdf"

    def test_collapses_spaces(self):
        assert sanitize_filename("hello   world") == "hello world"

    def test_strips_trailing_dots(self):
        assert sanitize_filename("file...") == "file"

    def test_empty_fallback(self):
        assert sanitize_filename("") == "file"

    def test_normal_name_unchanged(self):
        assert sanitize_filename("IRENE LUCIA PRUEBA NUEVE") == "IRENE LUCIA PRUEBA NUEVE"


class TestBuildFilename:
    def test_basic_filename(self):
        result = build_filename(1, "CHRISTIAN ANDRES BARAJAS", ".pdf")
        assert result == "01 CHRISTIAN ANDRES BARAJAS.pdf"

    def test_zero_for_instrument(self):
        result = build_filename(0, "INSTRUMENTO DE EVALUACION", ".pdf")
        assert result == "00 INSTRUMENTO DE EVALUACION.pdf"

    def test_two_digit_padding(self):
        result = build_filename(5, "NOMBRE", ".pdf")
        assert result == "05 NOMBRE.pdf"

    def test_multi_file_index(self):
        result = build_filename(3, "JORGE PRUEBA", ".docx", file_index=1)
        assert result == "03 JORGE PRUEBA - 1.docx"

    def test_multi_file_second(self):
        result = build_filename(3, "JORGE PRUEBA", ".pdf", file_index=2)
        assert result == "03 JORGE PRUEBA - 2.pdf"

    def test_sanitizes_name(self):
        result = build_filename(1, 'Name "With" Quotes', ".pdf")
        assert '"' not in result
        assert result == "01 Name With Quotes.pdf"


class TestGetExtension:
    def test_pdf(self):
        assert get_extension("document.pdf") == ".pdf"

    def test_docx(self):
        assert get_extension("file.DOCX") == ".docx"

    def test_no_extension_defaults_pdf(self):
        assert get_extension("noext") == ".pdf"

    def test_multiple_dots(self):
        assert get_extension("my.file.name.xlsx") == ".xlsx"


def _make_submissions(
    entries: list[SubmissionEntry] | None = None,
    instrument_url: str | None = None,
    instrument_name: str | None = None,
) -> SubmissionsPage:
    return SubmissionsPage(
        cmid=5967181,
        assignment_name="GA1-220501046-AA2-EV01 Taller Ofimatica",
        entries=entries or [],
        instrument_url=instrument_url,
        instrument_name=instrument_name,
    )


def _make_entry(
    user_id: int = 1,
    full_name: str = "TEST STUDENT",
    status: str = "Enviado para calificar",
    is_graded: bool = False,
    file_urls: list[str] | None = None,
    file_names: list[str] | None = None,
) -> SubmissionEntry:
    return SubmissionEntry(
        user_id=user_id,
        full_name=full_name,
        document="123456",
        email="test@test.com",
        status=status,
        is_graded=is_graded,
        file_urls=file_urls or ["https://example.com/file.pdf"],
        file_names=file_names or ["file.pdf"],
    )


class TestDownloadEngine:
    def setup_method(self):
        self.client = MagicMock()
        self.client.download_file.return_value = (b"fake pdf content", "file.pdf")
        self.engine = DownloadEngine(self.client)

    def test_creates_folder(self, tmp_path):
        entries = [_make_entry()]
        submissions = _make_submissions(entries=entries)
        config = DownloadConfig(target_dir=str(tmp_path))
        progress = DownloadProgress()

        self.engine.execute(submissions, config, progress)

        folder = tmp_path / "GA1-220501046-AA2-EV01 Taller Ofimatica"
        assert folder.is_dir()

    def test_downloads_student_file(self, tmp_path):
        entries = [_make_entry(full_name="IRENE PRUEBA")]
        submissions = _make_submissions(entries=entries)
        config = DownloadConfig(target_dir=str(tmp_path))
        progress = DownloadProgress()

        self.engine.execute(submissions, config, progress)

        folder = tmp_path / "GA1-220501046-AA2-EV01 Taller Ofimatica"
        assert (folder / "01 IRENE PRUEBA.pdf").exists()
        assert progress.status == "completed"
        assert progress.downloaded == 1

    def test_incremental_ids(self, tmp_path):
        entries = [
            _make_entry(user_id=1, full_name="STUDENT A"),
            _make_entry(user_id=2, full_name="STUDENT B"),
            _make_entry(user_id=3, full_name="STUDENT C"),
        ]
        submissions = _make_submissions(entries=entries)
        config = DownloadConfig(target_dir=str(tmp_path))
        progress = DownloadProgress()

        self.engine.execute(submissions, config, progress)

        folder = tmp_path / "GA1-220501046-AA2-EV01 Taller Ofimatica"
        assert (folder / "01 STUDENT A.pdf").exists()
        assert (folder / "02 STUDENT B.pdf").exists()
        assert (folder / "03 STUDENT C.pdf").exists()
        assert progress.downloaded == 3

    def test_downloads_instrument(self, tmp_path):
        entries = [_make_entry()]
        submissions = _make_submissions(
            entries=entries,
            instrument_url="/Repositorio/IE-EV01.pdf",
            instrument_name="IE-EV01.pdf",
        )
        config = DownloadConfig(target_dir=str(tmp_path), include_instrument=True)
        progress = DownloadProgress()

        self.engine.execute(submissions, config, progress)

        folder = tmp_path / "GA1-220501046-AA2-EV01 Taller Ofimatica"
        assert (folder / "00 INSTRUMENTO DE EVALUACION.pdf").exists()
        assert progress.downloaded == 2  # instrument + 1 student

    def test_skips_instrument_when_disabled(self, tmp_path):
        entries = [_make_entry()]
        submissions = _make_submissions(
            entries=entries,
            instrument_url="/Repositorio/IE-EV01.pdf",
        )
        config = DownloadConfig(target_dir=str(tmp_path), include_instrument=False)
        progress = DownloadProgress()

        self.engine.execute(submissions, config, progress)

        folder = tmp_path / "GA1-220501046-AA2-EV01 Taller Ofimatica"
        assert not (folder / "00 INSTRUMENTO DE EVALUACION.pdf").exists()
        assert progress.downloaded == 1

    def test_filters_by_status(self, tmp_path):
        entries = [
            _make_entry(user_id=1, full_name="SUBMITTED", status="Enviado para calificar"),
            _make_entry(user_id=2, full_name="NO SUBMIT", status="Sin entrega", file_urls=[], file_names=[]),
            _make_entry(user_id=3, full_name="GRADED", status="Enviado para calificar", is_graded=True),
        ]
        submissions = _make_submissions(entries=entries)
        config = DownloadConfig(
            target_dir=str(tmp_path),
            status_filter=["Enviado para calificar"],
            include_instrument=False,
        )
        progress = DownloadProgress()

        self.engine.execute(submissions, config, progress)

        # Student 1: "Enviado para calificar", not graded -> downloaded
        # Student 2: "Sin entrega" -> excluded by status filter
        # Student 3: "Enviado para calificar" but is_graded=True -> excluded
        assert progress.downloaded == 1

    def test_multiple_files_per_student(self, tmp_path):
        entries = [
            _make_entry(
                full_name="JORGE PRUEBA",
                file_urls=["https://example.com/part1.docx", "https://example.com/part2.pdf"],
                file_names=["Parte1.docx", "Parte2.pdf"],
            ),
        ]
        submissions = _make_submissions(entries=entries)
        config = DownloadConfig(target_dir=str(tmp_path), include_instrument=False)
        progress = DownloadProgress()

        self.engine.execute(submissions, config, progress)

        folder = tmp_path / "GA1-220501046-AA2-EV01 Taller Ofimatica"
        assert (folder / "01 JORGE PRUEBA - 1.docx").exists()
        assert (folder / "01 JORGE PRUEBA - 2.pdf").exists()
        assert progress.downloaded == 2

    def test_handles_download_error_gracefully(self, tmp_path):
        self.client.download_file.side_effect = [
            Exception("Network error"),
            (b"ok content", "file.pdf"),
        ]
        entries = [
            _make_entry(user_id=1, full_name="FAIL"),
            _make_entry(user_id=2, full_name="SUCCESS"),
        ]
        submissions = _make_submissions(entries=entries)
        config = DownloadConfig(target_dir=str(tmp_path), include_instrument=False)
        progress = DownloadProgress()

        self.engine.execute(submissions, config, progress)

        assert progress.status == "completed"
        assert progress.downloaded == 1
        assert len(progress.errors) == 1
        assert "FAIL" in progress.errors[0]

    def test_progress_to_dict(self, tmp_path):
        entries = [_make_entry()]
        submissions = _make_submissions(entries=entries)
        config = DownloadConfig(target_dir=str(tmp_path), include_instrument=False)
        progress = DownloadProgress()

        self.engine.execute(submissions, config, progress)

        d = progress.to_dict()
        assert d["status"] == "completed"
        assert d["downloaded"] == 1
        assert isinstance(d["files"], list)
        assert d["folder_path"] is not None

    def test_empty_entries_completes(self, tmp_path):
        submissions = _make_submissions(entries=[])
        config = DownloadConfig(target_dir=str(tmp_path), include_instrument=False)
        progress = DownloadProgress()

        self.engine.execute(submissions, config, progress)

        assert progress.status == "completed"
        assert progress.downloaded == 0
