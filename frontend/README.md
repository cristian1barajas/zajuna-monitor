# Frontend · Zajuna Monitor

Dashboard Next.js del monitor académico para instructores de formación virtual.

## Estado

- Next.js 16.1, React 19, TypeScript y Tailwind CSS 4.
- Autenticación contra la API del Sistema CMM.
- Acceso para roles `instructor` y `admin`.
- Dashboard, fichas, actividad, alertas, cronogramas, juicios, debido proceso, pendientes, informes y descarga de evidencias.
- Clientes API por dominio y componentes reutilizables bajo `src/`.

## Estructura

```text
src/
├── app/                 páginas App Router
├── components/          UI por dominio y componentes base
├── lib/                 auth, clientes API y lógica de dominio
└── types/               contratos de la API
```

La sesión CMM vive exclusivamente en `src/lib/cmm-auth.ts`. No se deben duplicar claves o lecturas de `localStorage` en otros módulos.

## Configuración

Crear `.env.local` a partir de `.env.local.example`:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_CMM_API_URL=http://localhost:8001/api/v1
NEXT_PUBLIC_CMM_FRONT_URL=http://localhost:3001
```

Ajustar puertos según el entorno. El backend CMM es obligatorio para login, refresh, magic links y `/auth/me`.

## Ejecución

```powershell
npm install
npm run dev
```

## Verificación

```powershell
npm run lint
npm run typecheck
npm run format:check
npm run build
```

## Convenciones

Consultar `../docs/convenciones.md`. Las páginas orquestan; la lógica reutilizable vive en `lib/` y la UI por dominio en `components/`.
