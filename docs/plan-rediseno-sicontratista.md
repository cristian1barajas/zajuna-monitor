# Plan — Adaptar el front de Zajuna Monitor al lenguaje visual de SI Contratista

> Referencia: 10 capturas de `contratistas.sena.edu.co` en `docs/referencias-diseno/sicontratista-2026-10/`.
> Esa carpeta tiene datos personales (cédula, planillas, montos). Está excluida localmente en `.git/info/exclude` y **no se debe versionar**.
> Base: rama `redesign/final` (6 commits sin publicar + cambios sin commit). Fecha: 2026-10-16 · Estado: propuesta.

## 1. Qué cambia (comparativo)

Los colores se muestrearon de las capturas. Son aproximados porque las imágenes vienen en webp comprimido.

| Elemento | SI Contratista | Zajuna Monitor hoy (`redesign/final`) | Cambio |
|---|---|---|---|
| Franja superior | Barra **GOV.CO** azul `#3366CC` a todo el ancho | Franja tricolor de 4 px solo en el login | **Decisión D1** |
| Sidebar | Teal oscuro con gradiente (`#004E63` → `#0B5A6F`), texto blanco, ítem activo en **pastilla verde sólida** (`~#19B400`), botón verde para colapsar en el borde | Claro `#F8F8F6`, activo en tinte verde, ancho arrastrable | **Grande** |
| Usuario | Tarjeta verde redondeada al pie del sidebar: avatar con iniciales, nombre, rol y chevron de menú | `UserBadge` de texto con botón de logout | Medio |
| Encabezado de página | Sin topbar. **Breadcrumb** (casa › sección en verde) + botón "?" de ayuda a la derecha + título grande en negrita | Topbar sticky con `<h1>`, reloj "hace X", tema y Sincronizar | **Grande** (reubicar reloj, tema y sync) |
| Fondo del contenido | Gris azulado `~#E9EEF2` | Blanco | Medio |
| Tarjetas | Blancas, radio ~16 px, **sombra suave**, sin borde | Planas, radio 8 px, borde 1 px, sin sombra | **Revierte** la decisión "flat + hairline" de `redesign/final` |
| Hero | Gradiente teal (`#003A51` → `#005E77`), eyebrow espaciado "SERVICIO NACIONAL DE APRENDIZAJE", "Bienvenido / Nombre", barra de progreso verde, foto o ilustración | Banda navy con saludo, % global y franja de 3 KPI | Adaptar (teal + ilustración) |
| Indicador global | Pastilla "Avance del alistamiento 100 %" arriba a la derecha | % dentro del hero | Pequeño |
| Tarjetas de acción | Grid de 4: **ícono ilustrado** en tile, chip de estado arriba a la derecha ("COMPLETO"), título, descripción y botón redondo verde con flecha | Filas densas de ficha; KPI sin íconos (se quitaron a propósito) | **Decisión D2** |
| Tablas | Cabecera con tinte verde `#E8F4E5`, encabezados en mayúscula pequeña, filas alternas `#F7F7F7`, check verde, estado "• generada", acciones en **botones circulares outline** | "Sectioned surfaces" `divide-y` con hover | Medio |
| Modal | Radio grande, título + subtítulo, *callout* informativo azul con ícono, textareas con contador, pie con Cancelar (outline) y primario verde (pastilla) | Solo `email-preview-modal` hecho a mano | Crear `Dialog` |
| Stepper | 3 tarjetas con número en círculo; la activa con borde y tinte verde; badges "Aprobado" (verde) y "Disponible" (azul) | No existe; "Paso 1 · …" en descargar-evidencias | Crear `Stepper` |
| Tabs | Botones pastilla: activo verde sólido, inactivos outline | Control segmentado gris | Restyle `ui/tabs` |
| Avisos | Callout redondeado con borde de color e ícono (azul info, naranja advertencia) | Caja con `*-soft` y borde | Pequeño |
| Formularios | Inputs outline con **label flotante en el borde** (estilo notched), radio ~10 px | Label arriba + input h-11 | Crear `Input`/`Select` |
| Perfil | Banner teal + avatar circular grande verde + nombre en mayúsculas | No aplica | Opcional para `/cuenta-zajuna` |
| Carga | Mascota + barra + porcentaje | Skeletons | Opcional |
| Flotantes | Botón de accesibilidad (borde derecho) y mascota/chat abajo a la derecha | No | **Decisión D3** |
| Login | Foto a pantalla completa con overlay teal, logo + lema a la izquierda, **tarjeta glass** a la derecha | Panel navy partido + formulario blanco | Rehacer |
| Tipografía | Sans geométrica, similar a Work Sans; títulos más pesados | Work Sans + JetBrains Mono | Mantener; subir peso de títulos |
| Modo oscuro | No se ve en SI Contratista | Completo | Mantener y derivar tokens teal oscuros |

## 2. Decisiones previas

> **Resueltas el 16-oct-2026 (Christian):**
> - **D1 → sin barra GOV.CO.** Se conserva solo la franja tricolor delgada del login.
> - **D2 → tarjetas con ícono solo en accesos.** Se usan en los accesos a módulos (dashboard y Resumen de ficha); las cifras y los KPI siguen en bandas sin íconos.
> - **D3 → sin mascota ni widget flotante** (recomendación por defecto).
> - **D4 → sin fotos del SENA.** El hero y el login usan el patrón de marca o gradiente teal (recomendación por defecto).

- **D1. Barra GOV.CO.** Es obligatoria en portales del Estado (lineamientos GOV.CO). Zajuna Monitor es una herramienta interna del ecosistema CMM y no un portal oficial: ponerla puede dar a entender que es un servicio oficial. *Recomendación:* no incluirla, o solo en el login.
- **D2. Íconos en tarjetas y KPI.** `redesign/final` los quitó a propósito (densidad de datos). SI Contratista los usa en tarjetas de **navegación o acción**. *Recomendación:* tarjetas con ícono solo en el dashboard (accesos a módulos de la ficha) y mantener las bandas de KPI sin íconos para los datos.
- **D3. Widget de accesibilidad y mascota.** *Recomendación:* omitir la mascota (asset ajeno). Lo de accesibilidad se puede valorar después (tamaño de texto y contraste).
- **D4. Fotos e ilustraciones.** La foto del hero y la del login son assets del SENA. Hay que confirmar si se pueden reutilizar o si se usan ilustraciones propias o el patrón de marca de la skill `sena-design`.

## 3. Fases

### R0 — Preparación
- Hacer commit de los cambios pendientes de `redesign/final` (docs + CORS de dev) o apartarlos.
- Crear la rama `redesign/sicontratista` desde `redesign/final`.
- Limpiar los worktrees y ramas `worktree-agent-*` y `redesign/{hibrido,institucional-sobrio,producto-moderno}` ya absorbidos. Solo con confirmación.

### R1 — Tokens (`frontend/src/app/globals.css` + `lib/status-colors.ts`)
- Familia **teal**: `--sena-teal-900 #003A51`, `--sena-teal-800 #004E63`, `--sena-teal-700 #0B5A6F`, `--sena-teal-600 #005E77` y tokens `on-teal`.
- Ajustar `sidebar*` a teal, `--background` a gris azulado y `--card` a blanco.
- `--radius` de 8 → 12–16 px; tokens de sombra `--shadow-card` y `--shadow-pop`.
- Tinte de cabecera de tabla (`--table-head`) y verde activo más saturado (validar contraste AA de blanco sobre verde).
- Equivalentes en modo oscuro y espejo hex en `lib/status-colors.ts` para los PDF.

### R2 — Primitivas (`frontend/src/components/ui/`)
- `Button` (primary pastilla / outline / ghost / icon-circle), `Input` y `Select` con label flotante, `Dialog` (Radix), `Breadcrumb`, `Avatar`, `Progress`, `Stepper`, `StatusChip`, `Callout`, `PageHeader` y `ActionCard`.
- Restyle de `Tabs` (pastillas) y `Table` (cabecera tintada, filas alternas).
- De paso se elimina la deuda de clases de botón e input copiadas en cada archivo.

### R3 — Shell
- `sidebar.tsx`: fondo teal, activo en pastilla verde, botón de colapsar en el borde, tarjeta de usuario con menú (perfil, tema, cerrar sesión), selector de ficha restilizado.
- Quitar `topbar.tsx` y reemplazarlo por `PageHeader` (breadcrumb + título + acciones a la derecha: última sincronización, Sincronizar, ayuda).
- Afecta 14 páginas que hoy renderizan `Topbar`.

### R4 — Login
- Fondo de imagen o patrón con overlay teal, marca a la izquierda y tarjeta glass a la derecha. Se conservan email/contraseña + enlace mágico.

### R5 — Dashboard
- Hero teal con saludo y progreso global, pastilla de avance, y grid de fichas como `ActionCard` o como lista dentro de una tarjeta (según D2).
- El panel de alertas pasa a tarjeta.

### R6 — Páginas de ficha
Se puede paralelizar en worktrees, como se hizo con `restyle/*`:
- **juicios:** `Stepper` para el flujo mapeo RAP → reporte Sofía → cruce; tablas.
- **ficha-core:** resumen, pendientes, actividad, cronograma.
- **reportes / procesos:** reportes, debido proceso, informes de queja, descargar evidencias (stepper), por calificar.
- **globales:** alertas, cuenta Zajuna (perfil con banner), y el **nuevo "Agregar grupo"** del otro plan.

### R7 — Verificación
- Preview a 1440 px y 375 px, modo claro y oscuro, comparando lado a lado con las capturas.
- `npm run lint`, `npm run typecheck`, `pytest` (el backend no cambia).
- Revisar que los PDF (heatmap, RAP) sigan con los colores correctos.

## 4. Relación con el módulo "Agregar grupo"
La UI de ese módulo (Fase 3 del otro plan) debe construirse **después de R2**, con `Dialog`, `Button` y `StatusChip` nuevos, para no hacerla dos veces. El backend (Fases 1–2) puede avanzar en paralelo desde `master`.
