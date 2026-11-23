# AGENTS.md — Zajuna Monitor

Reglas de arquitectura para trabajar en este repositorio. Actualizadas: 17-jul-2026.

## Contexto

Zajuna Monitor es la aplicación del dominio de formación virtual. Pertenece al ecosistema SENA CMM y usa el backend CMM como proveedor de identidad. No crear un segundo sistema de usuarios dentro de este repo.

## Arquitectura vigente

```text
Frontend Next.js
  ├── cmm-auth / cmm-api ───────► Backend CMM (identidad)
  └── lib/api/* ────────────────► API Zajuna Monitor
                                         │
                               middleware JWT CMM
                                         │
             ┌───────────────────────────┼──────────────────────────┐
             │                           │                          │
        scraper/client              parsers/stores            downloader/reports
             │                           │                          │
             └──────────────► data por instructor ◄────────────────┘
```

## Backend

### Capas

- `src/api/routes`: HTTP, validación de entrada y traducción de errores.
- `src/api/auth.py`: validación del JWT CMM y roles permitidos.
- `src/api/dependencies.py`: config y resolución de snapshot del usuario.
- `src/auth`: autenticación externa contra Zajuna/Moodle.
- `src/client`: requests autenticados; no parsea HTML.
- `src/parsers`: transforma HTML en modelos.
- `src/scraper`: orquesta login, consultas, merge y guardado.
- `src/store`: persistencia JSON por dominio.
- `src/downloader`: descarga binaria y empaquetado de evidencias.
- `src/models`: contratos internos del scraper.

Las rutas no deben parsear HTML ni manipular archivos directamente si existe una capa de dominio adecuada.

### Autenticación y autorización

- La API del monitor no emite tokens.
- Todas las rutas `/api/*`, salvo health y documentación, exigen `Authorization: Bearer <JWT CMM>`.
- El middleware acepta actualmente `instructor` y `admin`.
- El usuario autenticado queda en `request.state.user` con `id` y `role`.
- Las operaciones por ficha deben comprobar que la ficha pertenece al snapshot del usuario antes de acceder a stores secundarios.
- No volver a introducir API key como autenticación principal. `verify_api_key` es legado y debe retirarse cuando no tenga consumidores.

### Datos multi-instructor

- Snapshot principal: `data/instructors/<cmm_user_id>/latest.json`.
- Historial: `data/instructors/<cmm_user_id>/snapshots/`.
- El snapshot global es fallback temporal de migración, no el diseño final.
- Los trabajos lanzados desde API reciben el `cmm_user_id` autenticado.
- El cron itera cuentas válidas del vault y escalona las ejecuciones.
- No asumir que una ficha siempre pertenecerá a un único instructor como sustituto permanente de autorización.

### Credenciales

- Solo `src/store/zajuna_accounts_store.py` persiste credenciales Zajuna.
- Las credenciales se cifran con Fernet usando `ZAJUNA_CRED_KEY`.
- `CMM_JWT_SECRET_KEY` debe coincidir con `JWT_SECRET_KEY` del backend CMM.
- Producción no puede usar secretos por defecto ni claves locales autogeneradas no respaldadas.
- Nunca escribir contraseñas, cookies, tokens o documentos completos en logs.

### Scraping responsable

- Mantener delays configurables y límites de requests.
- Preferir grader reports agregados antes que requests por estudiante/evidencia.
- Reintentar solo errores de red transitorios.
- Detectar sesión expirada y reautenticar de forma controlada.
- Los cambios de selectores HTML requieren fixture sanitizado y pruebas.

### Tests

- Toda ruta o parser nuevo incluye pruebas.
- Los tests de API deben usar el fixture JWT de `tests/conftest.py`.
- No usar servicios reales de Zajuna en la suite.
- Ejecutar `pytest` antes de entregar cambios de backend.

## Frontend

### Estructura

- `src/app`: páginas y layouts; orquestación, no lógica de dominio compleja.
- `src/components/<dominio>`: UI reutilizable por dominio.
- `src/lib/api`: clientes HTTP del monitor separados por dominio.
- `src/lib/cmm-api.ts`: transporte hacia el proveedor de identidad.
- `src/lib/cmm-auth.ts`: única fuente de sesión del cliente.
- `src/types/api.ts`: contratos compartidos con la API.

### Sesión

- Las claves vigentes son `cmm_access_token` y `cmm_refresh_token`.
- No crear nuevas claves ni almacenar tokens en componentes.
- Ante 401, intentar el flujo de refresh definido; si falla, limpiar sesión y redirigir al login.
- El callback `/auth/callback` es un handoff provisional del portal CMM.
- Evitar poner tokens en query strings; el callback actual usa fragmento y lo limpia inmediatamente.

### UI y calidad

- Usar tokens de color de `globals.css`, no colores arbitrarios.
- Mantener lenguaje de dominio en español y nombres técnicos consistentes en inglés.
- Extraer componentes cuando una página supera aproximadamente 300 líneas o mezcla responsabilidades.
- No usar `any`.
- Ejecutar `npm run lint`, `npm run typecheck` y `npm run format:check`.

## Contratos y compatibilidad

- Un cambio de esquema requiere actualización atómica de backend, `src/types/api.ts`, cliente API y consumidores.
- Preservar compatibilidad durante migraciones de datos; documentar fallbacks y su fecha de retiro.
- No mezclar el dominio presencial en los stores del monitor. La integración transversal es identidad/autorización, no una base de datos única inmediata.

## Documentación obligatoria

Actualizar en el mismo cambio:

- `README.md` si cambia estado, setup o arquitectura pública.
- `docs/convenciones.md` si cambia una convención.
- `docs/plan-paso3-multi-instructor.md` si cambia el aislamiento.
- `sena-dev-2026-lineamientos/ARQUITECTURA_ACTUAL.md` si cambia la relación entre repositorios.
