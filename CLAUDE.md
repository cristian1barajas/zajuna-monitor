# Contexto técnico — Zajuna Monitor

> Resumen vigente al 17-jul-2026. Las reglas de implementación están en `AGENTS.md`.

## Rol del repositorio

Aplicación de formación virtual integrada al ecosistema SENA CMM. El backend CMM es la autoridad de identidad; este repositorio gestiona la conexión de cada instructor con Zajuna y sus datos académicos.

## Flujo de identidad

1. Login contra la API CMM.
2. JWT CMM compartido con el frontend y API del monitor.
3. Middleware del monitor valida firma, expiración, tipo `access` y rol.
4. `request.state.user.id` define el espacio de datos del instructor.
5. La cuenta Zajuna se conecta aparte y se guarda cifrada.

## Flujo externo de Zajuna

Zajuna usa un wrapper sobre Moodle:

1. POST al wrapper de login y extracción del formulario oculto.
2. POST a Moodle con los campos recibidos.
3. Seguimiento del redirect de sesión.
4. Validación de `/zajuna/my/` y cookie Moodle.

La interacción se implementa con `requests.Session`; no requiere Selenium. Los selectores y detalles se verifican con fixtures sanitizados bajo `backend/tests/fixtures`.

## Estado de datos

- Snapshots principales por usuario CMM.
- Stores secundarios por ficha todavía en proceso de hardening.
- Vault cifrado local para credenciales.
- Persistencia PostgreSQL e historial siguen como fase futura.

## Puntos sensibles

- No exponer credenciales ni datos personales en commits o logs.
- No usar el snapshot global como autorización.
- No confiar únicamente en el rol contenido en el frontend; la API siempre valida el JWT.
- Mantener `CMM_JWT_SECRET_KEY` sincronizado con el backend CMM.
- Tratar los documentos de arquitectura iniciales como historia cuando contradigan `AGENTS.md` o el código.

## Comandos

```powershell
# Backend
cd backend
pytest
python -m uvicorn src.api.server:app --reload --port 8000

# Frontend
cd frontend
npm run dev
npm run lint
npm run typecheck
```
