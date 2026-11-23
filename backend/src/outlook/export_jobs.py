"""Trabajo en segundo plano: imprimir los correos elegidos con Outlook y armar los ZIP.

Cada correo tarda unos segundos (Outlook Web abre el correo y prepara la
impresión), así que la API responde con un id de trabajo y el frontend
consulta el avance. Sale un ZIP por día de envío (cada uno va a Zajuna con
el acta de ese día); quedan en memoria hasta que se descargan.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from src.outlook.chrome import ChromeError
from src.outlook.llamados import PdfEntry, build_zip, classify_subject, zip_filename
from src.outlook.mail_client import MailApiError
from src.outlook.printer import OutlookPrinter
from src.outlook.session import EXPIRED_MESSAGE, OutlookConnection
from src.store.instructor_scope import start_thread
from src.store.soportes_store import record_soportes

logger = logging.getLogger(__name__)

JOB_TTL_S = 3600


class ExportBusy(RuntimeError):
    """Ya hay una descarga en curso con esta sesión de Outlook."""


@dataclass
class ExportJob:
    id: str
    user_id: str
    ficha: str
    total: int
    done: int = 0
    status: str = "running"  # running | done | error
    message: str = ""
    # Un ZIP por día de envío: (nombre, contenido), del día más antiguo al más reciente.
    files: list[tuple[str, bytes]] = field(default_factory=list)
    created: float = 0.0

    def public(self) -> dict:
        return {
            "job_id": self.id,
            "status": self.status,
            "done": self.done,
            "total": self.total,
            "message": self.message,
            "archivos": [name for name, _data in self.files],
        }


class ExportJobs:
    def __init__(self, printer_factory: Callable = OutlookPrinter, record_fn: Callable = record_soportes):
        self._printer_factory = printer_factory
        self._record_fn = record_fn
        self._jobs: dict[str, ExportJob] = {}
        self._lock = threading.Lock()

    def start(
        self,
        user_id: str,
        ficha: str,
        conn: OutlookConnection,
        message_ids: list[str],
        on_expired: Callable[[], None] = lambda: None,
    ) -> ExportJob:
        if not conn.lock.acquire(blocking=False):
            raise ExportBusy("Ya hay una descarga en curso; espera a que termine")
        job = ExportJob(id=uuid.uuid4().hex, user_id=user_id, ficha=ficha, total=len(message_ids), created=time.time())
        with self._lock:
            self._prune()
            self._jobs[job.id] = job
        # El hilo hereda el instructor: record_soportes guarda en su carpeta.
        start_thread(self._run, job, conn, message_ids, on_expired)
        return job

    def get(self, user_id: str, job_id: str) -> ExportJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job if job and job.user_id == user_id else None

    def _prune(self) -> None:
        now = time.time()
        for jid in [j.id for j in self._jobs.values() if now - j.created > JOB_TTL_S]:
            del self._jobs[jid]

    def _run(self, job: ExportJob, conn: OutlookConnection, message_ids: list[str], on_expired) -> None:
        try:
            client = conn.creds.client()
            messages = []
            for mid in dict.fromkeys(message_ids):
                msg = client.get_message(mid)
                info = classify_subject(msg.subject)
                # El ZIP solo lleva llamados de este grupo, aunque el id venga de otro lado.
                if info is None or info.ficha != job.ficha:
                    raise ValueError(f"Un correo no es un llamado del grupo {job.ficha}")
                messages.append((msg, info))

            entries = []
            with self._printer_factory(conn.chrome, conn.page) as printer:
                for msg, info in messages:
                    pdf = printer.print_pdf(msg.id, msg.subject)
                    entries.append(
                        PdfEntry(
                            stage=info.stage,
                            student_name=info.student_name,
                            subject=msg.subject,
                            sent_date=msg.sent_at.date().isoformat(),
                            pdf=pdf,
                        )
                    )
                    job.done += 1

            by_day: dict[date, list[int]] = {}
            for i, (msg, _info) in enumerate(messages):
                by_day.setdefault(msg.sent_at.date(), []).append(i)
            for day, idxs in sorted(by_day.items()):
                data, paths = build_zip([entries[i] for i in idxs])
                day_messages = [messages[i] for i in idxs]
                name = zip_filename(job.ficha, {info.stage for _msg, info in day_messages}, day)
                job.files.append((name, data))
                # Registro por aprendiz: qué correo se imprimió y en qué ZIP quedó (para el acta).
                self._record_fn(
                    job.ficha,
                    [
                        {
                            "message_id": msg.id,
                            "stage": info.stage,
                            "student_name": info.student_name,
                            "subject": msg.subject,
                            "sent_at": msg.sent_at.isoformat(),
                            "to": msg.to,
                            "archivo": path,
                        }
                        for (msg, info), path in zip(day_messages, paths, strict=True)
                    ],
                    name,
                )
            job.status = "done"
        except MailApiError as exc:
            job.status = "error"
            if exc.status == 401:
                job.message = EXPIRED_MESSAGE
                on_expired()
            else:
                job.message = str(exc)
        except (ChromeError, ValueError) as exc:
            job.status, job.message = "error", str(exc)
        except Exception as exc:  # noqa: BLE001 — el detalle no debe exponer datos del correo
            logger.warning("Falló la descarga de soportes: %s", type(exc).__name__)
            job.status, job.message = "error", "No se pudieron imprimir los correos"
        finally:
            conn.lock.release()


export_jobs = ExportJobs()
