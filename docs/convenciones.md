# Convenciones de código · Zajuna Monitor

> Reglas de diseño del proyecto. El linter hace cumplir lo mecánico
> (ESLint/Prettier en frontend, ruff en backend, CI en cada push);
> este documento cubre lo que las herramientas no ven.

## Idioma

- **Dominio en español**: ficha, aprendiz, evidencia, juicio, RAP, novedad —
  en labels de UI, mensajes y nombres de rutas (`/cuenta-zajuna`).
- **Código en inglés**: variables, funciones, componentes, campos de API
  (`fetchFichaDetail`, `overdue_students`). Comentarios en español está bien.

## Frontend (Next.js + TypeScript)

- **Tamaño**: un componente > ~300 líneas es señal de partirlo. Nada de
  componentes definidos dentro del render de otro (regla
  `react-hooks/static-components` — extraer a nivel de módulo con props).
- **Dónde vive cada cosa**:
  - `src/app/**` — páginas: orquestan datos y componen; sin lógica de dominio.
  - `src/components/<dominio>/` — UI por dominio (fichas, juicios, reports…).
  - `src/lib/` — clientes API, helpers de dominio puros (testeables sin React).
  - Generación de documentos (PDF/print HTML) NO va dentro de componentes:
    extraer a `src/lib/pdf/` (pendiente: heatmap y rap-heatmap).
- **Colores**: solo tokens (`bg-ok-soft`, `text-danger-fg`, `sena-*`).
  Prohibido `bg-red-500` o hex sueltos — ver familias en `globals.css`.
- **Estado global**: la sesión CMM vive en `lib/cmm-auth`; no duplicar
  lectura de localStorage por fuera de ese módulo.
- **`any` prohibido** (ESLint lo marca): tipar contra `types/api.ts`.

## Backend (FastAPI + Python)

- **Capas**: `api/routes` (HTTP puro) → `store`/`scraper`/`client` (lógica).
  Las rutas no parsean HTML ni tocan archivos directamente.
- **Credenciales**: solo el vault (`store/zajuna_accounts_store`) toca
  contraseñas; nunca en logs (enmascarar documentos: `doc[:4] + "****"`).
- **Config**: todo por `get_config()` / env vars; nada hardcodeado.
- **Errores**: excepciones de dominio (`AuthError`) → HTTPException en la
  ruta con mensaje en español para el usuario; `raise ... from exc`.
- **Tests**: toda ruta nueva llega con test; la suite corre autenticada
  (fixture JWT en `tests/conftest.py`). `pytest` verde antes de commit.

## Git

- Ramas `feat/<tema>` desde master; merge fast-forward tras validación E2E.
- Commits imperativos en inglés, cuerpo con el porqué; atómicos por tema.
- No se mergea con CI en rojo.

## Deuda registrada (TODO(code-quality))

- Cluster juicios/cruce RAP: claves de contrato JSON con palabras españolas
  no-dominio (`listos_para_aprobar`, `con_problemas`, `inconsistencias`,
  `aprobado_anticipado`…) en ~13 archivos front + backend + tests.
  Diferido conscientemente (2026-07-16): renombrar exige cambio atómico de
  contrato con beneficio bajo (varias claves rozan dominio). Si se aborda,
  limitar a las claramente no-dominio y en un solo commit.

- 6 `eslint-disable` de `set-state-in-effect` en efectos de montaje
  (localStorage/SSO): revisar al migrar a un estado de sesión centralizado.
