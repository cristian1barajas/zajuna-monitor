# Seguridad — Zajuna Monitor

> Revisión del 30-oct-2026 antes del despliegue. Rama `feat/seguridad`.

## 1. Herramientas usadas (todas gratuitas)

| Herramienta | Qué revisa | Resultado inicial | Después de los cambios |
|---|---|---|---|
| gitleaks 8.30 | Secretos en todo el historial de git (117 commits) | 7 coincidencias en `docs/zajuna_login_flow.har` | Archivo fuera del árbol; hallazgos históricos en `.gitleaksignore` |
| Semgrep 1.182 (`p/default`, python, typescript, react, owasp-top-ten) | Código (SAST) | 6 avisos | 0 |
| bandit 1.9 | Código Python | 2 de severidad media | 0 de severidad media o alta |
| pip-audit 2.10 | CVE en dependencias de Python | 0 | 0 |
| npm audit | CVE en dependencias del frontend | 43 (2 críticas, 19 altas) | 0 en producción; 22 en herramientas de desarrollo |
| Trivy 0.76 | CVE y configuración | Next 16.1.6 con 4 críticas y 18 altas; xlsx 0.18.5 altas | 0 altas o críticas |
| OSV-Scanner | CVE (segunda opinión) | Coincide con Trivy | — |
| OWASP ZAP (API scan + baseline) | Ataque dinámico sin sesión contra la API y el frontend | — | 0 fallas (119 + 64 pruebas superadas) |

**Sobre SonarQube y Veracode.** No hace falta pagar:

- **Veracode:** solo ofrece prueba gratis.
- **SonarQube Cloud:** es gratis solo para repos públicos, y este es privado.
- **SonarQube Community Build:** gratis si se instala en tu máquina con Docker. Sirve como revisión extra de calidad, no de vulnerabilidades.
- **CodeQL y el secret scanning de GitHub:** en repos privados de una organización piden GitHub Advanced Security, que es de pago.
- **Lo que cubre esos huecos sin costo:** los escáneres de arriba en el CI y Dependabot.

## 2. Hallazgos y correcciones

### Críticos

1. **Cualquiera podía fabricar un token de instructor.**
   - `auth.py` caía a la clave pública `"tu_secreto_que_sea_dificil"` si faltaba `CMM_JWT_SECRET_KEY`.
   - Además, la leía solo de las variables de entorno y nunca del `backend/.env`, así que en la práctica siempre usaba esa clave.
   - **Corrección:** la clave sale del entorno o del `.env` (`src/api/security.py`) y debe tener al menos 32 bytes; las claves conocidas se rechazan. Sin ella la API no arranca. Solo se aceptan HS256/384/512, y el token debe traer `exp` y `sub`.
2. **Next.js 16.1.6 con vulnerabilidades críticas.** Actualizado a 16.4.3.

### Altos

3. **Acceso a grupos ajenos.**
   - Las rutas `/fichas/{ficha}/…` no verificaban que el grupo fuera del instructor.
   - Los stores por ficha son globales, así que un instructor podía leer o borrar el reporte de Sofía, los cronogramas o el debido proceso de otro.
   - **Corrección:** un guard global (`require_ficha_access`) exige que la ficha esté en el snapshot del instructor. Si no, responde 404.
4. **Path traversal por el número de ficha.** `data/<store>/{ficha}.json` se armaba sin validar, y en Windows `..\` pasaba. **Corrección:** la ficha solo acepta dígitos.
5. **Un instructor sin datos propios veía el snapshot global**, que tiene los grupos de otro instructor. **Corrección:** recibe 503 hasta su primera sincronización.
6. **Lectura de carpetas del servidor.**
   - `POST /api/fichas/phone-data/import` leía cualquier carpeta del servidor y guardaba teléfonos de cualquier ficha.
   - **Corrección:** ahora es una herramienta local (`LOCAL_TOOLS_ENABLED`, apagada en producción) y solo guarda fichas del instructor.
   - Lo mismo aplica a Soportes de Outlook, que abre un Chrome en el servidor, y a Descargar evidencias, que escribe en una carpeta del servidor indicada por el cliente (`target_dir`; añadido el 31-oct en `feat/multi-instructor`).
7. **SheetJS (`xlsx`) 0.18.5** tenía prototype pollution y ReDoS al leer los Excel que se suben. Actualizado a 0.20.3 desde el CDN oficial de SheetJS, que ya no publica en npm.
8. **Captura de red del login a Zajuna versionada** (`docs/zajuna_login_flow.har`, commit inicial). Se sacó del árbol y `*.har` quedó en `.gitignore`. **Sigue en el historial:** ver la sección 4.

### Medios y bajos

9. **Documentación de la API.** `/docs`, `/redoc` y `/openapi.json` quedan apagados con `APP_ENV=production`.
10. **CORS:** los orígenes salen de `CORS_ORIGINS`, y las cabeceras permitidas se limitan a `Authorization` y `Content-Type`.
11. **Cabeceras de seguridad.**
    - **API:** `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, COOP, CORP, CSP `default-src 'none'`, `Cache-Control: no-store` en `/api`, y HSTS en producción.
    - **Frontend:** CSP con `connect-src` limitado a las dos APIs (el token vive en localStorage), `frame-ancestors 'none'`, `nosniff`, COOP y HSTS; se quita `X-Powered-By`.
12. **Límites de tamaño y frecuencia.**
    - Cuerpo de hasta 30 MB (`MAX_BODY_MB`).
    - 600 peticiones por minuto por usuario (`RATE_LIMIT_PER_MINUTE`).
    - Se rechaza el envío chunked sin `Content-Length`.
13. **Mensajes de error genéricos** donde antes se devolvía el texto de la excepción (importación de teléfonos, entregas de Zajuna).
14. **`API_HOST` por defecto `127.0.0.1`**, no `0.0.0.0`; en producción la API va detrás de Nginx.
15. **CI.**
    - Acciones de GitHub fijadas por SHA y `permissions: contents: read`.
    - Nuevo workflow `Seguridad` (gitleaks, Semgrep, bandit, pip-audit, npm audit, Trivy) en cada PR, en master y cada lunes.
    - Dependabot semanal con 7 días de cooldown.

### Aceptados (por ahora)

- **CSP con `script-src 'unsafe-inline'`.** Next inyecta scripts inline al hidratar. Quitarlo exige una CSP con nonce por petición (middleware y render dinámico); queda como mejora.
- **22 avisos de npm en herramientas de desarrollo** (eslint 9 y el CLI de shadcn). No llegan al build de producción. Dependabot propondrá las versiones nuevas.
- **El límite de frecuencia es por proceso.** Con varios workers de uvicorn, conviene también `limit_req` en Nginx.

## 3. Variables nuevas en `backend/.env`

| Variable | Desarrollo | Producción |
|---|---|---|
| `CMM_JWT_SECRET_KEY` | **obligatoria**, igual a `JWT_SECRET_KEY` del CMM | igual, generada aparte |
| `APP_ENV` | `development` | `production` |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | solo el dominio del frontend |
| `MAX_BODY_MB` | 30 | 30 (y `client_max_body_size 30m` en Nginx) |
| `RATE_LIMIT_PER_MINUTE` | 600 | 600 |
| `LOCAL_TOOLS_ENABLED` | (sin definir = activas) | (sin definir = apagadas) |

Para generar el secreto en los dos `.env` sin que se muestre:

```powershell
powershell -File scripts\generar_secreto_jwt.ps1
.\dev.ps1 restart
```

## 4. Pendientes que no se pueden cerrar desde el código

1. **Secreto del CMM.** Si el `.env` del backend CMM usa `tu_secreto_que_sea_dificil`, el script de arriba lo reemplaza. En producción, el CMM debe tener su propio secreto fuerte.
2. **Al desplegar:**
   - HTTPS con Nginx (`limit_req`, `client_max_body_size 30m`), firewall 22/80/443 y `.env` con permisos 600.
   - `ZAJUNA_CRED_KEY` real con respaldo, y quitar las credenciales de Zajuna del `.env` una vez que el vault esté estable.
3. **Antes de abrirla a más instructores:** particionar los stores por instructor y usar la cuenta Zajuna de cada uno.

## 5. Cómo repetir el escaneo en local

```bash
# Secretos en el historial
docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:v8.30.1 git /repo --redact
# Código
docker run --rm -v "$PWD:/src" semgrep/semgrep:1.182.1 semgrep scan --config p/default --exclude docs --metrics=off /src
# Dependencias
docker run --rm -v "$PWD:/src" aquasec/trivy:0.76.1 fs --scanners vuln,misconfig /src
# Dinámico, con la API corriendo en el puerto 8000
docker run --rm zaproxy/zap-stable zap-api-scan.py -t http://host.docker.internal:8000/openapi.json -f openapi
```
