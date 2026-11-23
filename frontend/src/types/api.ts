export interface HealthResponse {
  status: string;
  last_scrape: string | null;
  courses_count: number;
  errors_count: number;
}

export interface FichaSummaryItem {
  ficha: string;
  course_name: string;
  course_id: number;
  total_students: number;
  /** Aprendices con matrícula activa (base de pendientes y avance). */
  total_active: number;
  total_evidences: number;
  total_pending: number;
  /** Celdas evaluadas (aprobadas + desaprobadas) de aprendices activos. */
  total_graded: number;
  completion_percentage: number;
}

export interface DashboardResponse {
  fichas: FichaSummaryItem[];
  total_students: number;
  /** Aprendices con matrícula activa en todas las fichas. */
  total_active: number;
  total_evidences: number;
  total_pending: number;
  overall_completion: number;
  last_scrape: string | null;
  alerts_count: number;
}

export interface GradeItem {
  evidence_id: number;
  value: string;
  passed: boolean;
}

export interface StudentItem {
  user_id: number;
  full_name: string;
  document: string;
  email: string;
  approved: number;
  disapproved: number;
  pending: number;
  grades: Record<string, GradeItem>;
  status: string;
}

export interface EvidenceItem {
  item_id: number;
  name: string;
  category: string;
  total_approved: number;
  total_disapproved: number;
  total_pending: number;
}

export interface FichaDetailResponse {
  ficha: string;
  course_id: number;
  course_name: string;
  total_students: number;
  /** Aprendices con matrícula activa (base del avance). */
  total_active: number;
  total_evidences: number;
  completion_percentage: number;
  students: StudentItem[];
  evidences: EvidenceItem[];
}

export interface PendingEvidence {
  item_id: number;
  name: string;
  category: string;
  pending_count: number;
  pending_percentage: number;
}

export interface PendingStudent {
  user_id: number;
  full_name: string;
  document: string;
  pending_count: number;
  pending_evidences: number[];
}

export interface PendingSubmissionsResponse {
  ficha: string;
  by_evidence: PendingEvidence[];
  by_student: PendingStudent[];
}

export interface AlertItem {
  type: string;
  severity: string;
  ficha: string;
  message: string;
  evidence_name: string | null;
  /** item_id de la evidencia; null en alertas de toda la ficha. */
  item_id: number | null;
  /** Alertas de foros (forum_reply_overdue): foro de la bandeja a abrir. */
  forum_id?: number | null;
  pending_count: number | null;
  percentage: number | null;
}

export interface AlertsResponse {
  alerts: AlertItem[];
  total: number;
}

export interface ParticipantItem {
  user_id: number;
  full_name: string;
  document: string;
  email: string;
  role: string;
  groups: string;
  last_access_raw: string;
  last_access_days: number;
  status: string;
}

export interface ActivityResponse {
  ficha: string;
  course_id: number;
  total_active: number;
  total_suspended: number;
  participants: ParticipantItem[];
}

export interface ActivitySummaryItem {
  ficha: string;
  course_id: number;
  total_participants: number;
  total_active: number;
  total_suspended: number;
  avg_days_since_access: number;
  inactive_30_plus: number;
}

export interface CronogramaEntry {
  evidence_name: string;
  evidence_item_id: number | null;
  cutoff_date: string;
}

export interface CronogramaResponse {
  ficha: string;
  entries: CronogramaEntry[];
  updated_at: string;
}

export interface CronogramaPdfPreview {
  entries: CronogramaEntry[];
  warnings: string[];
  files: { filename: string; entries: number }[];
}

export interface OverdueEvidence {
  item_id: number;
  name: string;
  category: string;
}

export interface StudentReportItem {
  user_id: number;
  full_name: string;
  document: string;
  email: string;
  status: string;
  last_access_days: number;
  last_access_raw: string;
  overdue_evidences: OverdueEvidence[];
  overdue_count: number;
}

export interface ReportResponse {
  ficha: string;
  selected_evidences_count: number;
  total_students_with_overdue: number;
  total_students: number;
  students: StudentReportItem[];
}

export interface ScraperStep {
  label: string;
  status: "pending" | "running" | "completed" | "failed";
}

export interface ScraperStatus {
  job_id: string | null;
  status: "idle" | "running" | "completed" | "failed";
  progress: string | null;
  courses_total: number;
  courses_done: number;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  error: string | null;
  steps: ScraperStep[];
}

export interface DueProcessHistoryEntry {
  stage: string;
  stage_label: string;
  date: string;
  evidence_ids: number[];
  evidence_names: string[];
  email_generated: boolean;
}

export interface DueProcessRecord {
  user_id: number;
  full_name: string;
  document: string;
  current_stage: string;
  current_stage_label: string;
  history: DueProcessHistoryEntry[];
}

export interface DueProcessResponse {
  ficha: string;
  updated_at: string | null;
  records: DueProcessRecord[];
  total_records: number;
}

export interface EmailDraft {
  user_id: number;
  full_name: string;
  document: string;
  email: string;
  stage: string;
  stage_label: string;
  subject: string;
  body: string;
}

export interface EmailDraftsResponse {
  ficha: string;
  drafts: EmailDraft[];
  total: number;
}

export interface AdvanceResponse {
  ficha: string;
  advanced: number;
  records: DueProcessRecord[];
}

// --- Juicios (RAP Cross-Reference) ---

export interface RapEvidenciaInput {
  code: string;
  item_id: number | null;
  name: string;
  matched: boolean;
}

export interface RapMappingEntry {
  fase: string;
  competencia: string;
  rap: string;
  /** Código RAP de Sofia Plus (6 dígitos) — llave exacta del cruce de juicios. */
  rap_sofia_code?: string;
  evidencias: RapEvidenciaInput[];
}

export interface RapMappingStats {
  total_raps: number;
  total_evidencias: number;
  matched_evidencias: number;
  unmatched_evidencias: number;
}

export interface RapMappingInput {
  program_name: string;
  mappings: RapMappingEntry[];
  stats: RapMappingStats;
}

export interface RapMappingResponse {
  ficha: string;
  program_name: string;
  updated_at: string;
  mappings: RapMappingEntry[];
  stats: RapMappingStats;
}

export interface SofiaJudgment {
  competencia_code: string;
  competencia_desc: string;
  rap_code: string;
  rap_desc: string;
  juicio: string;
}

export interface SofiaStudent {
  document: string;
  full_name: string;
  student_status: string;
  judgments: SofiaJudgment[];
}

export interface SofiaReportInput {
  program_name: string;
  total_students: number;
  total_raps: number;
  students: SofiaStudent[];
  competency_map: Record<string, string>;
}

export interface SofiaReportResponse {
  ficha: string;
  program_name: string;
  uploaded_at: string;
  total_students: number;
  total_raps: number;
  students_count: number;
  competency_map: Record<string, string>;
}

export interface RapCrossResult {
  rap: string;
  competencia: string;
  zajuna_status: string;
  sofia_juicio: string;
  resultado: string;
  evidencias_total: number;
  evidencias_aprobadas: number;
}

export interface StudentCrossResult {
  document: string;
  full_name: string;
  status: string;
  raps: RapCrossResult[];
  total_raps: number;
  listos_para_aprobar: number;
  correctos: number;
  pendientes: number;
  con_problemas: number;
  inconsistencias: number;
  aprobados_anticipados: number;
}

export interface RapCrossResponse {
  ficha: string;
  total_students: number;
  total_raps: number;
  students: StudentCrossResult[];
  summary: Record<string, number>;
}

// --- Pending Grading (Assignments) ---

export interface AssignmentMapping {
  name: string;
  cmid: number;
  item_id: number | null;
  module_type: string;
}

export interface AssignmentMappingResponse {
  ficha: string;
  course_id: number;
  updated_at: string;
  assignments: AssignmentMapping[];
}

export interface PendingGradingResult {
  item_id: number;
  cmid: number | null;
  name: string | null;
  module_type: string;
  participants: number | null;
  submitted: number | null;
  needs_grading: number | null;
  drafts: number | null;
  total_discussions: number | null;
  // Quiz-specific: grade counts from grader report
  quiz_approved: number | null;
  quiz_disapproved: number | null;
  quiz_pending: number | null;
  // Solo tareas: quién espera calificación (se llena si needs_grading > 0)
  pending_students: GradingWaitingStudent[];
  error: string | null;
}

export interface GradingWaitingStudent {
  user_id: number;
  full_name: string;
  last_modified: string | null;
  file_count: number;
}

export interface PendingGradingResponse {
  ficha: string;
  results: PendingGradingResult[];
  checked_at: string;
}

// --- Complaint Reports (Informes de Queja) ---

export interface ComplaintPendingEvidence {
  item_id: number;
  name: string;
  category: string;
}

export interface ComplaintCandidate {
  user_id: number;
  full_name: string;
  document: string;
  email: string;
  last_access_days: number;
  pending_count: number;
  total_selected: number;
  pending_evidences: ComplaintPendingEvidence[];
}

export interface ComplaintCandidatesResponse {
  ficha: string;
  candidates: ComplaintCandidate[];
  total: number;
}

// --- Novedades ---

export interface NovedadRecord {
  user_id: number;
  full_name: string;
  document: string;
  type: string;
  type_label: string;
  note: string;
  created_at: string;
  updated_at: string;
}

export interface NovedadesResponse {
  ficha: string;
  total: number;
  types: Record<string, string>;
  records: NovedadRecord[];
}

// --- Download Evidences ---

export interface SubmissionInfo {
  user_id: number;
  full_name: string;
  document: string;
  email: string;
  status: string;
  is_graded: boolean;
  file_count: number;
  last_modified: string | null;
}

export interface SubmissionsListResponse {
  ficha: string;
  cmid: number;
  assignment_name: string;
  total_submissions: number;
  submissions: SubmissionInfo[];
  instrument_available: boolean;
  statuses: string[];
}

export interface BatchDownloadItem {
  cmid: number;
  name: string | null;
  status: "pending" | "running" | "completed" | "failed";
  total_files: number;
  downloaded: number;
  folder_path: string | null;
  errors: string[];
}

export interface BatchDownloadStatusResponse {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed";
  total_files: number;
  downloaded: number;
  current_file: string | null;
  items: BatchDownloadItem[];
}

export interface DownloadStatusResponse {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed";
  total_files: number;
  downloaded: number;
  current_file: string | null;
  errors: string[];
  folder_path: string | null;
  files: string[];
}

// --- Soportes de llamados desde Outlook ---

export type OutlookSessionState =
  "idle" | "waiting_login" | "connected" | "error";

export interface OutlookSessionStatus {
  status: OutlookSessionState;
  message: string;
  account: string | null;
  expires_at: string | null;
}

export interface CorreoLlamado {
  id: string;
  subject: string;
  sent_at: string;
  sent_date: string;
  stage: string;
  student_name: string;
  to: string[];
}

export interface ZipJobStatus {
  job_id: string;
  status: "running" | "done" | "error";
  done: number;
  total: number;
  message: string;
  /** Un ZIP por día de envío, del más antiguo al más reciente. */
  archivos: string[];
}

export interface BuscarLlamadosResponse {
  ficha: string;
  correos: CorreoLlamado[];
  revisados: number;
}

// --- Actas del equipo ejecutor ---

export interface ActaAsistente {
  nombre: string;
  dependencia: string;
}

export interface FechaActa {
  fecha_envio: string;
  llamados: number;
  por_etapa: Record<string, number>;
  soportes: number;
  acta_numero: number | null;
}

/** Correo impreso desde Outlook y en qué ZIP quedó. */
export interface SoporteRegistro {
  message_id: string;
  stage: string;
  student_name: string;
  sent_at: string;
  to: string[];
  archivo: string;
  zip: string;
  descargado_at: string;
}

export interface ActasResponse {
  ficha: string;
  asistentes: ActaAsistente[];
  siguiente_numero: number;
  hora_inicio: string;
  hora_fin: string;
  fechas: FechaActa[];
  soportes: SoporteRegistro[];
}

export interface ActaRequest {
  fecha_envio: string;
  numero: number;
  fecha_acta: string;
  hora_inicio: string;
  hora_fin: string;
  asistentes: ActaAsistente[];
}

// --- Juicios por asignar en Sofía Plus ---

export interface AprendizPorAsignar {
  document: string;
  full_name: string;
  total: number;
  aprobadas: number;
  desaprobadas: number;
  sin_entregar: number;
  fuera_de_corte: number;
}

/** Un RAP con los textos de Sofía y sus aprendices en orden alfabético. */
export interface RapPorAsignar {
  competencia_code: string;
  competencia_desc: string;
  competencia_programa: string;
  rap_code: string;
  rap_desc: string;
  rap_programa: string;
  fase: string;
  aprendices: AprendizPorAsignar[];
}

export interface JuiciosPorAsignarResponse {
  ficha: string;
  aprobar: RapPorAsignar[];
  no_aprobar: RapPorAsignar[];
  /** Aprendices que no se listan, por motivo. */
  fuera_de_formacion: number;
  con_novedad: number;
  suspendidos: number;
}

// --- Foros: aportes que esperan réplica del instructor (SAVA 9.1.6) ---

export type ForumContributionStatus =
  | "vencido"
  | "vence_hoy"
  | "a_tiempo"
  | "respondido"
  | "respondido_tarde";

export interface ForumContribution {
  post_id: number;
  discussion_id: number;
  discussion_title: string;
  parent_id: number | null;
  author_name: string;
  author_user_id: number | null;
  /** ISO con zona horaria de Zajuna. */
  created_at: string | null;
  excerpt: string;
  first_reply_at: string | null;
  gradable: boolean;
  /** Nota que muestra Zajuna; null = sin calificar. */
  grade: string | null;
  /** YYYY-MM-DD: día hábil siguiente al aporte. */
  reply_due: string | null;
  status: ForumContributionStatus;
  business_days_waiting: number;
  /** Enlace directo a la publicación en Zajuna. */
  url: string;
}

export interface ForumCounts {
  contributions: number;
  overdue: number;
  due_today: number;
  on_time: number;
  replied: number;
  replied_late: number;
  ungraded: number;
}

export interface ForumInboxResponse {
  ficha: string;
  forum_id: number;
  item_id: number | null;
  name: string;
  checked_at: string;
  total_discussions: number;
  peer_replies: number;
  failed_discussions: number[];
  counts: ForumCounts;
  contributions: ForumContribution[];
}

export interface ForumSummaryItem {
  forum_id: number;
  item_id: number | null;
  name: string;
  /** Foro calificable (tiene columna en el calificador). */
  graded: boolean;
  checked_at: string | null;
  counts: ForumCounts | null;
}

export interface ForumListResponse {
  ficha: string;
  today: string;
  forums: ForumSummaryItem[];
}
