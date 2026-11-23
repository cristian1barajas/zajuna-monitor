"""API endpoints for downloading student submission files from Zajuna."""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_config
from src.api.schemas import (
    BatchDownloadStatusResponse,
    DownloadPendingRequest,
    DownloadRequest,
    DownloadStatusResponse,
    SubmissionInfo,
    SubmissionsListResponse,
)
from src.api.security import get_security_settings
from src.auth.manager import AuthManager
from src.client.zajuna import FetchError, ZajunaClient
from src.config import ZajunaConfig
from src.downloader.engine import (
    BatchDownloadProgress,
    BatchItem,
    DownloadConfig,
    DownloadEngine,
    DownloadProgress,
)
from src.parsers.submissions_list import (
    SubmissionsPage,
    parse_instrument_url,
    parse_submissions_page,
)
from src.store.instructor_scope import start_thread

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fichas", tags=["download-evidences"])

# In-memory job stores for download progress tracking
_jobs: dict[str, tuple[DownloadProgress, datetime]] = {}
_batch_jobs: dict[str, tuple[BatchDownloadProgress, datetime]] = {}
_jobs_lock = threading.Lock()
_JOB_TTL = timedelta(hours=1)


def _cleanup_old_jobs() -> None:
    """Remove jobs older than TTL."""
    now = datetime.now()
    with _jobs_lock:
        for store in (_jobs, _batch_jobs):
            expired = [jid for jid, (_, ts) in store.items() if now - ts > _JOB_TTL]
            for jid in expired:
                del store[jid]


def _get_client(config: ZajunaConfig) -> tuple[AuthManager, ZajunaClient]:
    """Create and authenticate a Zajuna client."""
    try:
        auth = AuthManager(config)
        client = ZajunaClient(auth, config)
        auth.login()
        return auth, client
    except Exception as e:
        logger.error("Zajuna authentication failed: %s: %s", type(e).__name__, e)
        raise HTTPException(
            status_code=503,
            detail=f"Error de conexión con Zajuna: {type(e).__name__} - {e}",
        ) from e


def _require_local_tools() -> None:
    """Las descargas escriben en ``target_dir`` de la máquina del servidor:
    solo sirven cuando el servidor es el PC del instructor."""
    if not get_security_settings().local_tools:
        raise HTTPException(status_code=404, detail="No disponible en este servidor")


@router.get("/{ficha}/submissions/{cmid}", response_model=SubmissionsListResponse)
def get_submissions(
    ficha: str,
    cmid: int,
    config: ZajunaConfig = Depends(get_config),
):
    """Fetch and parse the submissions list for an assignment.

    On-demand scraping: authenticates with Zajuna, fetches the grading
    page, and parses submission data including file info and statuses.
    Also fetches instrument URL from the assignment detail page.
    """
    _, client = _get_client(config)

    # Fetch and parse submissions list
    try:
        html = client.fetch_submissions_list(cmid)
        page = parse_submissions_page(html, cmid)
    except FetchError as e:
        logger.warning("No se pudieron leer las entregas: %s", e)
        raise HTTPException(status_code=502, detail="No se pudieron leer las entregas en Zajuna") from e

    # Also fetch instrument from detail page (without action=grading)
    if page.instrument_url is None:
        try:
            detail_html = client.fetch_assignment_detail(cmid)
            inst_url, inst_name = parse_instrument_url(detail_html)
            page.instrument_url = inst_url
            page.instrument_name = inst_name
        except FetchError:
            pass  # Instrument is optional

    return SubmissionsListResponse(
        ficha=ficha,
        cmid=cmid,
        assignment_name=page.assignment_name,
        total_submissions=len(page.entries),
        submissions=[
            SubmissionInfo(
                user_id=e.user_id,
                full_name=e.full_name,
                document=e.document,
                email=e.email,
                status=e.status,
                is_graded=e.is_graded,
                file_count=len(e.file_urls),
                last_modified=e.last_modified,
            )
            for e in page.entries
        ],
        instrument_available=page.instrument_url is not None,
        statuses=page.statuses,
    )


@router.post("/{ficha}/download-evidence")
def start_download(
    ficha: str,
    body: DownloadRequest,
    config: ZajunaConfig = Depends(get_config),
):
    """Start downloading submission files to a local folder.

    Runs in a background thread. Returns a job_id for polling progress.
    """
    _require_local_tools()
    _cleanup_old_jobs()

    _, client = _get_client(config)

    # Fetch submissions
    try:
        html = client.fetch_submissions_list(body.cmid)
        page = parse_submissions_page(html, body.cmid)
    except FetchError as e:
        logger.warning("No se pudieron leer las entregas: %s", e)
        raise HTTPException(status_code=502, detail="No se pudieron leer las entregas en Zajuna") from e

    # Fetch instrument URL from detail page if needed
    if body.include_instrument and page.instrument_url is None:
        try:
            detail_html = client.fetch_assignment_detail(body.cmid)
            inst_url, inst_name = parse_instrument_url(detail_html)
            page.instrument_url = inst_url
            page.instrument_name = inst_name
        except FetchError:
            pass

    # Create job
    job_id = str(uuid.uuid4())[:8]
    progress = DownloadProgress()
    with _jobs_lock:
        _jobs[job_id] = (progress, datetime.now())

    download_config = DownloadConfig(
        target_dir=body.target_dir,
        include_instrument=body.include_instrument,
        status_filter=body.status_filter,
    )

    # Run in background thread
    engine = DownloadEngine(client)
    start_thread(engine.execute, page, download_config, progress)

    return {"job_id": job_id}


@router.post("/{ficha}/download-pending")
def start_pending_download(
    ficha: str,
    body: DownloadPendingRequest,
    config: ZajunaConfig = Depends(get_config),
):
    """Download, in one job, the submissions waiting to be graded.

    Same rule as a single download (sent for grading and not graded),
    applied to every cmid in order with one Zajuna session: parallel
    logins with the same account invalidate each other.
    """
    _require_local_tools()
    _cleanup_old_jobs()

    _, client = _get_client(config)

    def fetch_page(cmid: int) -> SubmissionsPage:
        page = parse_submissions_page(client.fetch_submissions_list(cmid), cmid)
        if body.include_instrument and page.instrument_url is None:
            try:
                inst_url, inst_name = parse_instrument_url(client.fetch_assignment_detail(cmid))
                page.instrument_url = inst_url
                page.instrument_name = inst_name
            except FetchError:
                pass  # Instrument is optional
        return page

    job_id = str(uuid.uuid4())[:8]
    batch = BatchDownloadProgress(items=[BatchItem(cmid=c) for c in body.cmids])
    with _jobs_lock:
        _batch_jobs[job_id] = (batch, datetime.now())

    download_config = DownloadConfig(
        target_dir=body.target_dir,
        include_instrument=body.include_instrument,
    )
    engine = DownloadEngine(client)
    start_thread(engine.execute_batch, fetch_page, download_config, batch)

    return {"job_id": job_id}


@router.get(
    "/{ficha}/download-pending-status/{job_id}",
    response_model=BatchDownloadStatusResponse,
)
def get_pending_download_status(ficha: str, job_id: str):
    """Poll the progress of a batch download."""
    with _jobs_lock:
        job = _batch_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    batch, _ = job
    return BatchDownloadStatusResponse(job_id=job_id, **batch.to_dict())


@router.get("/{ficha}/download-status/{job_id}", response_model=DownloadStatusResponse)
def get_download_status(ficha: str, job_id: str):
    """Poll download progress."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    progress, _ = job
    data = progress.to_dict()
    return DownloadStatusResponse(job_id=job_id, **data)
