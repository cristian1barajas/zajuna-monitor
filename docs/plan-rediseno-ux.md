# Plan — Rediseño de experiencia (distribución, no estilos)

> 24-oct-2026. Sale de la revisión de las 15 páginas después de rehacer Por Calificar (PR #4).
> Las rutas son relativas a `frontend/src/`.

## Lo que aprendimos en Por Calificar

Dos columnas iguales (`lg:grid-cols-2`) con una lista de altura fija a un lado y resultados al otro dejan espacio vacío, aprietan la tabla y repiten nombres. Funciona mejor:

- **una tabla a todo el ancho**, que se llena en el sitio y tiene detalle expandible;
- **filtros compactos** en una fila de menús;
- **por defecto, solo lo que pide acción del instructor**, y el resto a un clic.

## Hallazgos que cruzan varias páginas

1. **"Pendientes" no es "por calificar".** El dashboard, las alertas y la sección Pendientes cuentan celdas sin nota (`-`), que incluyen trabajos nunca enviados o que aún no vencen. El hero dice "evidencias por calificar" (`components/dashboard/stats-overview.tsx:46-51`). Solo Por Calificar responde "enviado y sin nota", y es la 8.ª sección del menú.
2. **El mismo esquema roto se repite.** Dos columnas desiguales con lista de altura fija: Reportes (`reportes/page.tsx:272`), Informes de queja (`informes-queja/page.tsx:234`) y Descargar evidencias (`descargar-evidencias/page.tsx:223`).
3. **Hay cuatro selectores de evidencias distintos.** Ninguno recuerda lo que eligió otra página. Conviene uno compartido (`EvidencePicker`) sobre `EvidenceFilters` y `applyFilters`.
4. **Las páginas no se enlazan entre sí.** Hacen falta estos pasos directos: Reportes → Informes de queja, Por Calificar → Descargar evidencias de una tarea, Alertas → Por Calificar y Juicios → Reportes.
5. **Encabezados duplicados.** Cada página trae h1, h2 y breadcrumb. El topbar no queda fijo y el botón de sincronizar se pierde al hacer scroll.

## Fases propuestas

### F1 — Navegación y lenguaje (M) · mayor impacto diario
- **Agrupar las 10 secciones de la ficha:**
  - **Calificar:** Por calificar, Descargar evidencias.
  - **Seguimiento:** Resumen, Actividad, Cronograma, Reportes.
  - **Trámites:** Debido proceso, Informes de queja, Juicios.

  Las secciones están en `components/layout/sidebar.tsx:41-52`.
- **Barra lateral, modo ficha:** mantener un pie global con Alertas y Ajustes; hoy desaparecen.
- **Barra lateral, lista de fichas:** mostrar en cada ficha cuántas entregas tiene sin calificar, según la última consulta.
- **Topbar:**
  - un solo título, con el nombre de la sección;
  - espacio para una descripción y para acciones;
  - fijo arriba (`sticky top-0`);
  - quitar los h2 repetidos.
- **Resumen:** quitar las 4 tarjetas de acceso, que repiten el menú y empujan la tabla hacia abajo (`app/fichas/[ficha]/page.tsx:155-165`).
- **Lenguaje:** llamar "sin nota" a lo que hoy se llama "pendientes" o "por calificar" en el hero, las alertas y Pendientes.
- **Barras flotantes:** evitar que la barra de sincronización múltiple tape el aviso de progreso.

### F2 — Reportes (M) · donde se hace el debido proceso
- **Barra superior:** "Evidencias: 12 seleccionadas · Cambiar". Abre un panel con el selector compartido, donde "Cierre: ya cerró" reemplaza la fecha de corte y el select "hasta evidencia".
- **Debajo, a todo el ancho:**
  - indicadores;
  - alertas como chips que filtran la tabla;
  - filtros en menús (Estado, Novedad, Matrícula), con "Pendientes" por defecto;
  - la tabla.
- **Acciones fijas** al pie de la tabla: Generar correos, Marcar novedad e Informe de queja con los seleccionados.
- **Novedades:** pasan a un diálogo "Novedades (n)", en vez de una segunda lista de los mismos aprendices.
- **Selector compartido:** aquí se construye el `EvidencePicker`, que después usan F4 y F5.

### F3 — Dashboard y Alertas (M)
- **Dashboard:**
  - hero en una sola línea: saludo, avance global y última sincronización;
  - una tabla de fichas a todo el ancho con Activos, Sin nota, Alertas, Avance y acciones de fila (Por calificar, Reportes);
  - cada fila se expande y muestra las alertas de esa ficha. Se quita la columna de alertas 50/50.
- **Alertas:**
  - una tabla con Ficha, Evidencia, Sin nota y Severidad;
  - filtros en menús;
  - cada fila enlaza a Por Calificar con el filtro puesto;
  - sin la banda de conteos ni el tope de 20.

### F4 — Informes de queja (M)
- **Pasos a todo el ancho:** 1. Evidencias + umbral de días; 2. Candidatos; 3. Datos del informe y Generar. Solo se abre el paso actual; los anteriores quedan resumidos en una línea con "Editar".
- **Campo mal ubicado:** el nombre de la coordinadora pasa al paso 3.
- **Recibe desde Reportes** (`?evidences=&students=`): llega directo al paso 2 o 3.
- **Aviso de desactualizado** si cambian las evidencias o el umbral después de buscar.

### F5 — Arreglos rápidos (S cada uno)
- **Actividad:** por defecto "Inactivos 30+ días" y solo activos, con un control segmentado en lugar de 5 tarjetas. Correo y cédula pasan al detalle de la fila.
- **Debido proceso:**
  - las tarjetas de etapa filtran, y se quita el select duplicado;
  - la columna "Acciones" pasa a llamarse "Último llamado";
  - el historial va en una fila de detalle a todo el ancho;
  - enlace "Siguiente etapa" hacia Reportes.
- **Cronograma:**
  - con datos cargados, el área para subir el archivo queda contraída en "Reemplazar CSV";
  - aviso fijo arriba de "cambios sin guardar";
  - Eliminar pide confirmación y deja de estar junto a Guardar;
  - filas ordenadas por fecha.
- **Juicios:** por defecto "Requiere acción" (listos e inconsistencias); los indicadores filtran y las columnas se pueden ordenar.
- **Descargar evidencias:**
  - buscador de tarea agrupado por guía;
  - tabla a todo el ancho, sin scroll interno;
  - el filtro de estado como menú;
  - recibe `?cmid=` desde cada fila de Por Calificar.
- **Agregar grupo:**
  - barra fija con Guardar;
  - buscador y "Monitoreados / Disponibles";
  - los cursos sin ficha se agrupan aparte;
  - pasa a llamarse "Mis grupos".

### F6 — Resumen y Pendientes (M)
- **Pestaña Evidencias:** filtros compartidos y una fila de detalle con los aprendices sin nota.
- **Pendientes:** se vuelve la pestaña "Sin nota" dentro de Resumen, con "Cierre: ya cerró" por defecto. Por aprendiz, el detalle muestra qué evidencias debe.
- **Heatmap:** las opciones del PDF van en un menú "Exportar PDF"; se quita "Verificar entregas", que repite Por Calificar.

## Errores funcionales encontrados en la revisión (fuera de la distribución)

- **Cuenta Zajuna:** si Zajuna rechaza las credenciales, el formulario no se abre solo. Hoy depende de `connected`, no de `status` (`app/cuenta-zajuna/page.tsx:39`).
- **Juicios, carga:** si solo se actualiza el reporte de Sofía, "Guardar y continuar" no sale de la página (`app/fichas/[ficha]/juicios/upload/page.tsx:41`).
- **Cronograma:** Eliminar no pide confirmación.
- **Informes de queja:** la ruta de importación de teléfonos está fija en el código (`informes-queja/page.tsx:155`).
