# Estado de migración multi-instructor

> Actualizado: 17-jul-2026. Los pasos principales de partición y cron multi-cuenta fueron implementados el 16-jul-2026. Este documento registra lo completado y el hardening pendiente.

## Objetivo

Cada instructor autenticado debe ver y modificar únicamente sus datos, y el cron debe sincronizar cada cuenta conectada con sus propias credenciales Zajuna.

## Completado

- Middleware JWT CMM deja `request.state.user = {id, role}`.
- Vault cifrado de credenciales por `cmm_user_id`.
- Layout `data/instructors/<cmm_user_id>/latest.json` y `snapshots/`.
- `json_store` y runner admiten directorio/usuario opcional sin romper ejecución legada.
- Resolución y caché de snapshot por usuario.
- Jobs de sincronización lanzados con el usuario autenticado.
- Credenciales del runner resueltas por usuario.
- Cron itera cuentas vigentes y ejecuta sincronizaciones escalonadas.
- Migración suave: el snapshot global permanece como fallback si el usuario aún no tiene snapshot propio.

Commits principales: `15dd09b`, `17901f9`, `616ce30` y `22aded2`.

## Diseño vigente

```text
data/
├── latest.json                         fallback temporal
├── snapshots/                          historial legado
└── instructors/
    └── <cmm_user_id>/
        ├── latest.json
        └── snapshots/
```

El ID de usuario CMM es el límite primario. La ficha no debe considerarse por sí sola un tenant.

## Pendiente

### Prioridad alta

1. Validar en todas las rutas por ficha que la ficha exista en el snapshot del usuario; devolver 403 cuando no pertenezca.
2. Particionar o autorizar explícitamente los stores secundarios: cronogramas, novedades, debido proceso, RAP, Sofía, assignments, estados de envío y teléfonos.
3. Retirar el fallback global después de migrar los datos de todos los instructores.
4. Añadir pruebas de aislamiento entre dos usuarios con fichas diferentes.

### Descubrimiento de cursos

Los course IDs todavía pueden provenir de configuración. La solución preferida es descubrir los cursos desde `/zajuna/my/` cuando se valida la cuenta, permitir confirmación del instructor y persistir la selección por usuario.

### Producción

- Configurar `CMM_JWT_SECRET_KEY` real y compartido.
- Configurar y respaldar `ZAJUNA_CRED_KEY`; perderla hace irrecuperables las credenciales cifradas.
- Deshabilitar secretos por defecto.
- Establecer permisos de filesystem, backups y rotación.

## Criterio de finalización

La migración multi-instructor se considera completa cuando:

- no existe lectura cruzada entre usuarios;
- todos los stores tienen límite de propietario verificable;
- no se usa el snapshot global;
- los cursos se configuran o descubren por cuenta;
- existen pruebas automáticas de aislamiento;
- el cron reporta fallos por cuenta sin afectar a las demás.
