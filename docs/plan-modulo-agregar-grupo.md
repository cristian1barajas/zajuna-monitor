# Plan — Módulo "Agregar grupo" (descubrimiento de cursos Zajuna)

> Detonante: grupo TPS **3607707** (Técnico en Programación de Software, inició 13-oct-2026) no aparece en Zajuna Monitor.
> Fecha: 2026-10-16 · Estado: propuesta, sin código.

## 1. Diagnóstico: por qué no aparece

En el sistema no existe la entidad "ficha". El scraper solo conoce **course IDs de Moodle**, y el número de ficha se extrae después, del título del calificador.

| Fuente de course IDs | Dónde |
|---|---|
| Variable `ZAJUNA_COURSE_IDS` del `.env` | `backend/src/config.py:39,60-65` (el mapa ID→ficha solo está como comentario en `.env.example:7-14`) |
| Course IDs que ya están en `latest.json` | `backend/src/main.py:45-60` (`_course_ids_for`) |
| Ficha extraída del `<title>` del grader con `\((\d{7})\)` | `backend/src/parsers/grader.py:21,81-107` |

- `POST /api/scraper/run {fichas:[...]}` solo resuelve fichas que **ya** están en el snapshot (`backend/src/api/routes/scraper.py:60-84`). Una ficha nueva da 400, y hay un test que lo fija (`backend/tests/test_scraper_api.py:166-183`).
- No hay endpoint, UI ni descubrimiento para agregar una ficha. Figura como pendiente en `docs/plan-paso3-multi-instructor.md:46-48` y `README.md:183`.

**Gancho clave:** el login ya hace `GET /zajuna/my/` (`backend/src/auth/manager.py:240-296`), pero descarta el HTML después de leer `M.cfg`. Esa página ("Mis cursos") trae todos los cursos del instructor con un *shortname* parseable:

```
course/view.php?id=89977 → P_228118_V_3388997_R_11_C_9214
                             │       │         │     └ centro
                             │       │         └ versión/regional
                             │       └ ficha
                             └ código de programa (228118 = ADSO)
```

La muestra `docs/html-samples/html_que_devuelve_el_login.html` incluye también `P_233104_V_3118277` y `P_233104_V_3138239`, que son otro programa. Esas dos fichas tienen `data/assignments/*.json`, pero ya no están en el `.env`.

## 2. Fase 0 — Desbloqueo inmediato, sin código

Sirve para empezar a monitorear 3607707 hoy mismo:

1. En Zajuna → *Mis cursos*, abrir el curso de 3607707 y copiar el `id=` de la URL `course/view.php?id=…`.
2. Agregar ese ID a `ZAJUNA_COURSE_IDS` en `backend/.env`. Esto lo hace Christian, porque el agente no toca `.env`.
3. Ejecutar una **sincronización completa** (botón global "Sincronizar"). La sincronización por ficha no sirve todavía.
4. Revisar el resultado (ver §5, compatibilidad TPS).

## 3. Fases del módulo

### Fase 1 — Parser de "Mis cursos" (backend)
- Crear `backend/src/parsers/my_courses.py` → `list[DiscoveredCourse{course_id, shortname, fullname, ficha, program_code}]`.
  - Regex del shortname: `^P_(\d+)_V_(\d{7})_R_\d+_C_\d+$`.
  - Fallback: tomar `(\d{7})` del fullname.
  - Si no hay ficha, se reporta como "curso sin ficha" (no se descarta en silencio).
- Hacer que `AuthManager` conserve el HTML de `/my/` que ya descarga, para no gastar un request extra. Si el bloque "Mis cursos" carga por AJAX, usar como plan B `core_course_get_enrolled_courses_by_timeline_classification` con el `sesskey` que ya se tiene. Hay que verificarlo con la cuenta real.
- Tests con un fixture **anonimizado** derivado de la muestra.

### Fase 2 — Registro de cursos seguidos por instructor (backend)
- Crear el store `data/instructors/<cmm_user_id>/courses.json` con `[{course_id, ficha, program_code, program_label, fullname, tracked, added_at}]`.
- Mapa `program_code → etiqueta` (`228118 → ADSO`, `<código TPS> → TPS`) en `backend/src/config.py` o en un JSON editable.
- Endpoints:
  - `GET /api/courses/discover`: login con la cuenta del vault **del usuario autenticado**, parseo de `/my/` y devolución de los cursos marcados como ya seguidos o no.
  - `PUT /api/courses/tracked`: recibe `{course_ids:[...]}` y persiste la selección.
- Resolución en el scraper:
  - `_course_ids_for` y `_resolve_fichas_to_course_ids` consultan primero `courses.json`.
  - El `.env` queda solo como semilla o legado.
  - Se quita el *fallback* silencioso a "todos los cursos" (`scraper.py:82-84`).
  - Una ficha recién agregada se puede sincronizar sola.
- Ajustar el test del 400: debe seguir fallando para una ficha **no seguida** y pasar para una ficha seguida que aún no tiene snapshot.

### Fase 3 — UI "Agregar grupo" (frontend)
- Entrada desde el sidebar (sección FICHAS → "+ Agregar grupo") y desde `/cuenta-zajuna` justo después de vincular la cuenta.
- Modal o página con la lista de cursos descubiertos: ficha en mono, nombre del curso, chip de programa (ADSO/TPS), check de "ya seguido".
- Acción **"Agregar y sincronizar"**: guarda la selección y dispara `POST /api/scraper/run {fichas:[nueva]}` con el progreso existente (`sync-progress`).
- Estado vacío y de error: cuenta Zajuna no vinculada, credenciales inválidas, curso sin ficha.
- Se construye con las primitivas nuevas del rediseño (Dialog, Button, StatusChip). Ver `plan-rediseno-sicontratista.md`.

### Fase 4 — Compatibilidad con programas distintos de ADSO
Hay que validarla con el primer scrape real de 3607707:

| Supuesto ADSO | Dónde | Qué pasa si TPS no cumple |
|---|---|---|
| El título del grader contiene `(3607707)` | `grader.py:21` | ficha = `""` y fallan todas las funciones que dependen de la ficha → usar la ficha del registro (Fase 2) como fuente de verdad |
| Notas solo `A` / `D` / `-` | `schemas.py:9-13`, `grader.py:297-305` | se descartan las notas numéricas → soportar escala numérica o mapearla |
| Evidencias en `catlevel2` | `grader.py:109-191` | no aparecen evidencias |
| Código `GA<n>-<comp>-AA<n>-EV<n>` | `assignments_index.py:127`, `rap_cross_engine.py:9`, `docx_generator.py:15-16`, `lib/grading.ts:23,43`, `heatmap.tsx:135-136,292-293` | todo sale "Productiva" en el heatmap y el cruce RAP/docx se degrada |
| Mapeo RAP en Excel ADSO | `rap-mapping-uploader.tsx:201`, `docs/sofia-plus/Evidencias_RAP_ADSO.xlsx` | se necesita un `Evidencias_RAP_TPS.xlsx` |

- Guardar `program_code` en el `CourseData` del snapshot para que el front adapte las etiquetas.
- Cargar el cronograma, el reporte Sofía y el mapeo RAP del grupo TPS.

### Fase 5 — Deuda que conviene cerrar en la misma rama
- **Bug:** `backend/src/api/routes/pending_grading.py:150` llama `get_snapshot()` sin `request` (la firma exige `request`, ver `dependencies.py:85`). El `except` se traga el `TypeError`, así que los conteos de quiz **siempre** dan (0, 0, 0).
- El nombre del instructor está fijo en el código: `complaint_reports.py:335`. Debe salir del usuario o la cuenta.
- Guarda contra colisiones de ficha `""` cuando varios cursos no traen número.
- Los stores por ficha (`assignments/`, `submission_status/`…) son globales y no están particionados por instructor. Es aceptable mientras haya un solo instructor, pero hay que dejarlo anotado.

## 4. Orden y ramas sugeridas
1. **Fase 0** ya (manual).
2. **Fases 1 y 2 + bug de Fase 5** en `feat/descubrir-cursos` desde `master`. El backend de `redesign/final` es idéntico al de `master`, así que no hay conflicto.
3. **Fase 3** después de las primitivas del rediseño (Fase R1 del otro plan), en la rama del rediseño o rebasada sobre ella.
4. **Fase 4** se dimensiona tras el primer scrape de 3607707.

## 5. Preguntas abiertas
- ¿Cuál es el `course_id` y el shortname de 3607707? Con eso se confirma el código del programa TPS (¿es 233104, el de 3118277/3138239?).
- ¿El calificador de TPS usa A/D o notas numéricas? ¿Las evidencias siguen la convención GA…EV?
- ¿El agregado es solo para Christian o ya autoservicio para cualquier instructor (presencial incluido)? El diseño de la Fase 2 sirve para ambos casos.
