"""Pydantic response models for the Zajuna Monitor API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# --- Health ---

class HealthResponse(BaseModel):
    status: str
    last_scrape: datetime | None
    courses_count: int
    errors_count: int


# --- Dashboard ---

class FichaSummaryItem(BaseModel):
    ficha: str
    course_name: str
    course_id: int
    total_students: int
    total_active: int = 0  # aprendices con matrícula activa
    total_evidences: int
    total_pending: int  # solo de aprendices activos
    total_graded: int = 0  # celdas evaluadas (aprob+desaprob) de activos
    completion_percentage: float  # solo de aprendices activos


class DashboardResponse(BaseModel):
    fichas: list[FichaSummaryItem]
    total_students: int
    total_active: int = 0  # aprendices con matrícula activa
    total_evidences: int
    total_pending: int
    overall_completion: float
    last_scrape: datetime | None
    alerts_count: int


# --- Ficha detail ---

class GradeItem(BaseModel):
    evidence_id: int
    value: str
    passed: bool


class StudentItem(BaseModel):
    user_id: int
    full_name: str
    document: str
    email: str
    approved: int
    disapproved: int
    pending: int
    grades: dict[int, GradeItem]
    status: str = "Activo"


class EvidenceItem(BaseModel):
    item_id: int
    name: str
    category: str
    total_approved: int
    total_disapproved: int
    total_pending: int


class FichaDetailResponse(BaseModel):
    ficha: str
    course_id: int
    course_name: str
    total_students: int
    total_active: int = 0  # aprendices con matrícula activa
    total_evidences: int
    completion_percentage: float  # solo de aprendices activos
    students: list[StudentItem]
    evidences: list[EvidenceItem]


# --- Pendientes ---

class PendingEvidence(BaseModel):
    item_id: int
    name: str
    category: str
    pending_count: int
    pending_percentage: float


class PendingStudent(BaseModel):
    user_id: int
    full_name: str
    document: str
    pending_count: int
    pending_evidences: list[int]


class PendingSubmissionsResponse(BaseModel):
    ficha: str
    by_evidence: list[PendingEvidence]
    by_student: list[PendingStudent]


# --- Alerts ---

class AlertItem(BaseModel):
    type: str
    severity: str
    ficha: str
    message: str
    evidence_name: str | None = None
    # item_id de la evidencia: el front enlaza la alerta con Por Calificar
    item_id: int | None = None
    # Alertas de foros: el front enlaza con la bandeja de ese foro
    forum_id: int | None = None
    pending_count: int | None = None
    percentage: float | None = None


class AlertsResponse(BaseModel):
    alerts: list[AlertItem]
    total: int


# --- Activity ---

class ParticipantItem(BaseModel):
    user_id: int
    full_name: str
    document: str
    email: str
    role: str
    groups: str
    last_access_raw: str
    last_access_days: int
    status: str


class ActivityResponse(BaseModel):
    ficha: str
    course_id: int
    total_active: int
    total_suspended: int
    participants: list[ParticipantItem]


class ActivitySummaryItem(BaseModel):
    ficha: str
    course_id: int
    total_participants: int
    total_active: int
    total_suspended: int
    avg_days_since_access: float
    inactive_30_plus: int


# --- Cronograma ---

class CronogramaEntryInput(BaseModel):
    evidence_name: str
    cutoff_date: str  # "YYYY-MM-DD"


class CronogramaInput(BaseModel):
    ficha: str
    entries: list[CronogramaEntryInput]


class CronogramaEntryResponse(BaseModel):
    evidence_name: str
    evidence_item_id: int | None
    cutoff_date: str


class CronogramaResponse(BaseModel):
    ficha: str
    entries: list[CronogramaEntryResponse]
    updated_at: str


class CronogramaPdfFile(BaseModel):
    filename: str
    entries: int


class CronogramaPdfPreview(BaseModel):
    """Filas leídas de los PDF, sin guardar: el instructor las revisa antes."""
    entries: list[CronogramaEntryResponse]
    warnings: list[str]
    files: list[CronogramaPdfFile]


# --- Reports ---

class OverdueEvidence(BaseModel):
    item_id: int
    name: str
    category: str


class StudentReportItem(BaseModel):
    user_id: int
    full_name: str
    document: str
    email: str
    status: str
    last_access_days: int
    last_access_raw: str
    overdue_evidences: list[OverdueEvidence]
    overdue_count: int


class ReportRequest(BaseModel):
    evidence_ids: list[int]


class ReportResponse(BaseModel):
    ficha: str
    selected_evidences_count: int
    total_students_with_overdue: int
    total_students: int
    students: list[StudentReportItem]


# --- Scraper ---


class ScraperRunRequest(BaseModel):
    fichas: list[str] | None = None  # None = all configured fichas


class ScraperStepStatus(BaseModel):
    label: str
    status: str  # "pending" | "running" | "completed" | "failed"


class ScraperStatusResponse(BaseModel):
    job_id: str | None = None
    status: str = "idle"  # "idle" | "running" | "completed" | "failed"
    progress: str | None = None
    courses_total: int = 0
    courses_done: int = 0
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    error: str | None = None
    steps: list[ScraperStepStatus] = []


# --- Due Process ---


class DueProcessHistoryEntry(BaseModel):
    stage: str
    stage_label: str
    date: str
    evidence_ids: list[int]
    evidence_names: list[str]
    email_generated: bool


class DueProcessRecord(BaseModel):
    user_id: int
    full_name: str
    document: str
    current_stage: str
    current_stage_label: str
    history: list[DueProcessHistoryEntry]


class DueProcessResponse(BaseModel):
    ficha: str
    updated_at: str | None = None
    records: list[DueProcessRecord]
    total_records: int


class DueProcessStudentResponse(BaseModel):
    ficha: str
    record: DueProcessRecord


# --- Email Drafts ---


class EmailDraftRequest(BaseModel):
    user_ids: list[int]
    evidence_ids: list[int]


class EmailDraft(BaseModel):
    user_id: int
    full_name: str
    document: str
    email: str
    stage: str
    stage_label: str
    subject: str
    body: str


class EmailDraftsResponse(BaseModel):
    ficha: str
    drafts: list[EmailDraft]
    total: int


class EmlDraftInput(BaseModel):
    """Borrador ya generado que se exporta como .eml (no se persiste)."""

    user_id: int
    full_name: str = Field(max_length=200)
    email: str = Field(default="", max_length=320)
    subject: str = Field(max_length=500)
    body: str = Field(max_length=50_000)
    stage: str = Field(max_length=50)


class EmlExportRequest(BaseModel):
    drafts: list[EmlDraftInput] = Field(min_length=1, max_length=300)
    # "Descargar todos" pide siempre .zip, aunque haya un solo borrador.
    as_zip: bool = False


class AdvanceRequest(BaseModel):
    user_ids: list[int]
    evidence_ids: list[int]


class AdvanceResponse(BaseModel):
    ficha: str
    advanced: int
    records: list[DueProcessRecord]


# --- Juicios (RAP Cross-Reference) ---


class RapEvidenciaInput(BaseModel):
    code: str
    item_id: int | None = None
    name: str
    matched: bool = False


class RapMappingEntry(BaseModel):
    fase: str
    competencia: str
    rap: str
    # Código RAP de Sofia Plus (6 dígitos). Llave exacta del cruce con los
    # juicios; vacío en mapeos guardados antes de existir este campo.
    rap_sofia_code: str = ""
    evidencias: list[RapEvidenciaInput]


class RapMappingStats(BaseModel):
    total_raps: int
    total_evidencias: int
    matched_evidencias: int
    unmatched_evidencias: int


class RapMappingInput(BaseModel):
    program_name: str
    mappings: list[RapMappingEntry]
    stats: RapMappingStats


class RapMappingResponse(BaseModel):
    ficha: str
    program_name: str
    updated_at: str
    mappings: list[RapMappingEntry]
    stats: RapMappingStats


class SofiaJudgment(BaseModel):
    competencia_code: str
    competencia_desc: str
    rap_code: str
    rap_desc: str
    juicio: str


class SofiaStudent(BaseModel):
    document: str
    full_name: str
    student_status: str
    judgments: list[SofiaJudgment]


class SofiaReportInput(BaseModel):
    program_name: str
    total_students: int
    total_raps: int
    students: list[SofiaStudent]
    competency_map: dict[str, str]


class SofiaReportResponse(BaseModel):
    ficha: str
    program_name: str
    uploaded_at: str
    total_students: int
    total_raps: int
    students_count: int
    competency_map: dict[str, str]


class RapCrossResult(BaseModel):
    rap: str
    competencia: str
    zajuna_status: str
    sofia_juicio: str
    resultado: str
    evidencias_total: int
    evidencias_aprobadas: int


class StudentCrossResult(BaseModel):
    document: str
    full_name: str
    status: str = "Activo"
    raps: list[RapCrossResult]
    total_raps: int
    listos_para_aprobar: int
    correctos: int
    pendientes: int
    con_problemas: int
    inconsistencias: int
    aprobados_anticipados: int


class AprendizPorAsignar(BaseModel):
    document: str
    full_name: str
    total: int
    aprobadas: int
    desaprobadas: int
    sin_entregar: int
    fuera_de_corte: int


class RapPorAsignar(BaseModel):
    """Un RAP con los textos de Sofía (para encontrarlo allá) y sus aprendices en orden alfabético."""

    competencia_code: str
    competencia_desc: str
    competencia_programa: str
    rap_code: str
    rap_desc: str
    rap_programa: str
    fase: str
    aprendices: list[AprendizPorAsignar]


class JuiciosPorAsignarResponse(BaseModel):
    ficha: str
    aprobar: list[RapPorAsignar]
    no_aprobar: list[RapPorAsignar]
    # Aprendices que no se listan, por motivo.
    fuera_de_formacion: int
    con_novedad: int
    suspendidos: int


class RapCrossResponse(BaseModel):
    ficha: str
    total_students: int
    total_raps: int
    students: list[StudentCrossResult]
    summary: dict[str, int]


# --- Pending Grading (Assignments) ---


class PendingGradingRequest(BaseModel):
    item_ids: list[int]


class AssignmentMappingItem(BaseModel):
    name: str
    cmid: int
    item_id: int | None = None
    module_type: str = "assign"


class AssignmentMappingResponse(BaseModel):
    ficha: str
    course_id: int
    updated_at: str
    assignments: list[AssignmentMappingItem]


class GradingWaitingStudent(BaseModel):
    """An apprentice whose submission is waiting to be graded."""

    user_id: int
    full_name: str
    last_modified: str | None = None
    file_count: int = 0


class PendingGradingResult(BaseModel):
    item_id: int
    cmid: int | None = None
    name: str | None = None
    module_type: str = "assign"
    participants: int | None = None
    submitted: int | None = None
    needs_grading: int | None = None
    drafts: int | None = None
    total_discussions: int | None = None
    # Quiz-specific: grade counts from grader report (no scraping needed)
    quiz_approved: int | None = None
    quiz_disapproved: int | None = None
    quiz_pending: int | None = None
    # Assignments only: who is waiting, filled when needs_grading > 0
    pending_students: list[GradingWaitingStudent] = []
    error: str | None = None


class PendingGradingResponse(BaseModel):
    ficha: str
    results: list[PendingGradingResult]
    checked_at: str


# --- Foros: réplicas pendientes (SAVA 9.1.6) ---


class ForumContribution(BaseModel):
    """Aporte de un aprendiz que espera réplica del instructor."""

    post_id: int
    discussion_id: int
    discussion_title: str
    parent_id: int | None = None
    author_name: str
    author_user_id: int | None = None
    created_at: str | None = None
    excerpt: str
    first_reply_at: str | None = None
    gradable: bool = False
    grade: str | None = None
    # Calculados a la fecha de la consulta
    reply_due: str | None = None
    status: str
    business_days_waiting: int = 0
    url: str


class ForumCounts(BaseModel):
    contributions: int = 0
    overdue: int = 0
    due_today: int = 0
    on_time: int = 0
    replied: int = 0
    replied_late: int = 0
    ungraded: int = 0


class ForumInboxResponse(BaseModel):
    ficha: str
    forum_id: int
    item_id: int | None = None
    name: str
    checked_at: str
    total_discussions: int
    peer_replies: int
    failed_discussions: list[int] = []
    counts: ForumCounts
    contributions: list[ForumContribution]


class ForumSummaryItem(BaseModel):
    """Foro del grupo con el resumen de su última revisión (si la hay)."""

    forum_id: int
    item_id: int | None = None
    name: str
    graded: bool
    checked_at: str | None = None
    counts: ForumCounts | None = None


class ForumListResponse(BaseModel):
    ficha: str
    today: str
    forums: list[ForumSummaryItem]


# --- Download Evidences ---


class SubmissionInfo(BaseModel):
    user_id: int
    full_name: str
    document: str
    email: str
    status: str
    is_graded: bool
    file_count: int
    last_modified: str | None = None


class SubmissionsListResponse(BaseModel):
    ficha: str
    cmid: int
    assignment_name: str
    total_submissions: int
    submissions: list[SubmissionInfo]
    instrument_available: bool
    statuses: list[str]


class DownloadRequest(BaseModel):
    cmid: int
    target_dir: str
    include_instrument: bool = True
    status_filter: list[str] = ["Enviado para calificar"]


class DownloadPendingRequest(BaseModel):
    """Download the submissions waiting to be graded for several assignments."""

    cmids: list[int] = Field(min_length=1)
    target_dir: str
    include_instrument: bool = True


class BatchDownloadItem(BaseModel):
    cmid: int
    name: str | None = None
    status: str  # pending | running | completed | failed
    total_files: int = 0
    downloaded: int = 0
    folder_path: str | None = None
    errors: list[str] = []


class BatchDownloadStatusResponse(BaseModel):
    job_id: str
    status: str  # pending | running | completed | failed
    total_files: int = 0
    downloaded: int = 0
    current_file: str | None = None
    items: list[BatchDownloadItem] = []


class DownloadStatusResponse(BaseModel):
    job_id: str
    status: str  # pending | running | completed | failed
    total_files: int = 0
    downloaded: int = 0
    current_file: str | None = None
    errors: list[str] = []
    folder_path: str | None = None
    files: list[str] = []
