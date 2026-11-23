# Zajuna Monitor

**Le dice al instructor de formación virtual qué calificar, quién va atrasado y qué trámite sigue.**

Zajuna es el LMS (basado en Moodle) donde el SENA dicta su formación virtual. Tiene todos los datos, pero no responde las preguntas que un instructor se hace cada día con varios grupos de 30 a 50 aprendices al tiempo. Zajuna Monitor sincroniza esa información y la convierte en listas de trabajo.

Lo construí siendo instructor de Análisis y Desarrollo de Software, para resolver mi propio trabajo. Lo usé con mis grupos reales.

> Proyecto personal. No es un producto oficial del SENA. **Todos los datos de este repositorio son ficticios**: nombres, documentos y correos de las pruebas se reemplazaron por datos de ejemplo.

---

## Qué problema resuelve

| El instructor necesita saber… | Lo que hace Zajuna Monitor |
|---|---|
| ¿Qué me falta calificar? | **Por calificar:** tareas, foros y cuestionarios sin nota, con filtros por guía, fase y fecha de cierre, y **descarga en lote solo de las entregas pendientes**, organizadas por aprendiz. |
| ¿Quién va atrasado y a quién debo llamar? | **Alertas** solo de evidencias ya vencidas según el cronograma. Antes eran más de 100 por grupo y nadie las leía; con la regla nueva un grupo pasó de **107 a 4 alertas críticas**. |
| ¿Qué entregas vencen y cuándo? | **Cronograma** leído directo del PDF oficial (con vista previa de los cambios antes de guardar) y una línea de tiempo por competencia. |
| ¿Qué juicio pongo en el sistema académico? | **Juicios por resultado de aprendizaje:** cruza las notas del LMS con el mapeo evidencia ↔ RAP y genera las listas de aprobar y no aprobar, en PDF. |
| ¿Cómo documento el debido proceso? | **Debido proceso:** borradores de correo por etapa, soportes de los llamados en PDF, actas del equipo ejecutor e informes de queja en Word. |
| ¿Quién responde en los foros? | **Foros:** aportes de aprendices que esperan réplica del instructor, con plazo de 1 día hábil (festivos de Colombia incluidos). |

## Arquitectura

```text
                 ┌────────────── JWT (HS256, secreto compartido) ──────────────┐
                 │                                                              │
Sistema académico (identidad) ──► Frontend Next.js 16 ──► API FastAPI ──► Sincronizador ──► Zajuna (Moodle)
                                                             │               (requests + BeautifulSoup,
                                                             │                sin navegador, con pausas)
                                                             ├─ Datos aislados por instructor
                                                             ├─ Credenciales del LMS cifradas por instructor
                                                             └─ Parsers HTML → modelos Pydantic
```

- **Backend:** Python 3.12, FastAPI, Pydantic, requests, BeautifulSoup/lxml, pdfplumber, python-docx, PyJWT y cryptography.
- **Frontend:** Next.js 16 (App Router), React 19, TypeScript y Tailwind CSS 4. Más de 15 vistas por grupo: resumen, por calificar, alertas, reportes, cronograma, juicios, foros, debido proceso, actividad y descarga de evidencias.
- **Identidad delegada:** el monitor no tiene usuarios propios. Valida el JWT que emite el sistema académico que lideré con un equipo de aprendices (firma, expiración, tipo de token y rol), así que un instructor usa las dos herramientas con una sola sesión.
- **Multi-instructor:** cada petición fija el instructor en un `ContextVar` desde el middleware de autenticación. Los datos, las sincronizaciones y las credenciales del LMS quedan separados por cuenta, y la API valida que cada grupo consultado pertenezca a quien pregunta.
- **Sincronización:** inicio de sesión programático en el LMS (flujo de 3 pasos sobre su capa de autenticación), un pedido por curso al reporte de calificaciones para no cargar el servidor y una mezcla incremental con el snapshot anterior.

### Estructura

```text
backend/
  src/auth        inicio de sesión en el LMS
  src/client      transporte HTTP autenticado con pausas y reintentos
  src/parsers     calificaciones, participantes, tareas, foros, cuestionarios y cronograma PDF
  src/scraper     trabajos de sincronización por instructor
  src/store       almacenes por dominio, aislados por instructor
  src/api         middleware JWT, caché, modelos y rutas
  tests/          607 pruebas con HTML de ejemplo sanitizado
frontend/
  src/app         rutas (App Router)
  src/lib/api     clientes de API por dominio
  src/components  componentes por dominio y primitivas de UI
```

## Seguridad

Antes de desplegar hice una revisión con escáneres gratuitos (gitleaks, Semgrep, Trivy, OSV, OWASP ZAP, bandit y pip-audit) y corregí lo que encontraron. Está documentado en [`docs/seguridad.md`](docs/seguridad.md). Lo principal:

- El secreto JWT es **obligatorio y de al menos 32 bytes**: sin él, la API no arranca. Antes tenía un valor por defecto público.
- Control de acceso por grupo en todas las rutas y sin respaldo a datos de otros instructores.
- CORS, tamaño máximo de cuerpo, límite de peticiones por minuto, cabeceras de seguridad y CSP en el frontend.
- Las herramientas que solo tienen sentido en el equipo del instructor (por ejemplo, abrir Outlook Web para imprimir soportes) se apagan fuera de local.
- CI con pytest + ruff, workflow de seguridad, Dependabot y acciones de GitHub fijadas por SHA.

## Cómo lo construí

Lo desarrollé con **Claude Code** como herramienta principal, con estas reglas:

- **Primero el plan, después el código.** Cada frente grande (multi-instructor, rediseño de UX en 6 fases, agregar grupo) empezó con un plan escrito con sus decisiones y preguntas abiertas. Algunos están en [`docs/`](docs/).
- **Reglas para los agentes en el repositorio:** [`AGENTS.md`](AGENTS.md) y [`CLAUDE.md`](CLAUDE.md) fijan la arquitectura, lo que no se toca y cómo se prueba. Así cada sesión con IA parte del mismo criterio.
- **Las pruebas son el contrato.** Toda ruta nueva entra con pruebas; los parsers se prueban contra HTML real sanitizado.
- **Revisión humana de todo lo que entra**, por pull request, y prueba de punta a punta con mis grupos antes de fusionar.

## Correr en local

Requisitos: Python 3.11 o superior, Node.js 20 o superior y el servicio de identidad (o cualquier emisor de JWT HS256 con el mismo secreto).

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env        # completar CMM_JWT_SECRET_KEY (32+ bytes)
python -m uvicorn src.api.server:app --reload --host 127.0.0.1 --port 8000

# Frontend
cd frontend
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

Swagger queda en `http://127.0.0.1:8000/docs`.

### Pruebas

```powershell
cd backend
pytest            # 607 pruebas; no se conectan al LMS
ruff check .

cd ..\frontend
npm run lint
npm run typecheck
```

## Lo que sigue

- Migrar los almacenes JSON a PostgreSQL, con historial.
- Desplegar con HTTPS y sincronización programada en la madrugada.
- Extenderlo a la formación presencial a través del sistema académico.

---

Christian Barajas · Ingeniero Electrónico, Magíster en TIC aplicadas a la educación · Bogotá, Colombia
