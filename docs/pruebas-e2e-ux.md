# Pruebas E2E — rediseño de experiencia (PR #4 a #7)

> 25-oct-2026. Hazlas con la rama `feat/ux-f4-f6` (PR #7), que ya trae todo lo anterior porque sale de `master`.
> Entorno: Postgres del CMM en Docker (5433), CMM en 8001, Monitor en 8000 y front en 3000 (`.\dev.ps1`).
> Ficha sugerida: **3389000** (tiene cronograma, consultas y debido proceso).

**Marcas:** 🔴 nunca se probó en vivo · 🟡 se probó por el DOM o en parte · 🟢 ya revisado (solo repasar).
**⚠️** = la prueba escribe datos o entra a Zajuna con tu cuenta.

---

## 1. Primero: lo que nadie ha probado en vivo

### 1.1 🔴⚠️ Agregar grupo (entra a Zajuna al abrir)
1. Abre **Ajustes › Agregar grupo**.
   Debe cargar tus cursos de Zajuna, con el buscador, el selector "Monitoreados / Disponibles" y la barra **Guardar** fija abajo.
2. Escribe "3607" en el buscador.
   Solo deben quedar los cursos que coinciden.
3. Cambia entre **Monitoreados** y **Disponibles**.
   Los conteos deben cuadrar con la lista. Al marcar o desmarcar, las filas no deben saltar de pestaña.
4. Despliega **"N cursos sin ficha"**.
   Deben verse agrupados y sin casilla para monitorear.
5. Marca un curso sin guardar.
   La barra de abajo debe resumir el cambio. Desmárcalo y la barra vuelve a "sin cambios".
6. *(Opcional)* Agrega 3607791 o 3607792 y pulsa **Guardar y sincronizar**.
   Debe sincronizar el grupo nuevo y aparecer en la barra lateral.
7. **Quitar un grupo:** en **Monitoreados** desmarca uno (por ejemplo, el que agregaste en el paso 6).
   La barra debe decir "se quitará del monitor. Sus datos se guardan…" y el botón **Quitar grupo**.
   Al pulsarlo, debe desaparecer **en ese momento** de la barra lateral, del dashboard y de Alertas, sin recargar.
8. **Volver a agregarlo:** búscalo en **Disponibles**, márcalo y pulsa **Guardar y sincronizar**.
   Debe reaparecer con sus datos de antes: reportes, debido proceso, novedades, cronograma y juicios.
9. 3388997 y 3388998, que quitaste en octubre, ya **no** deben aparecer en la barra lateral. Sus datos siguen en disco.

### 1.2 🔴⚠️ Descargar evidencias con `?cmid` (descarga archivos reales)
1. Ve a **Por calificar**, despliega una **tarea** con pendientes y pulsa **"Descargar solo esta tarea"**.
   Debe abrir Descargar evidencias con esa tarea ya elegida, cargar sus envíos solo y mostrar la tabla a todo el ancho, sin scroll interno.
2. Revisa la barra encima de la tabla.
   Debe tener **Estado** (menú), **instrumento** y **ruta**.
3. Cambia el filtro de estado.
   El conteo de archivos del pie debe cambiar.
4. Pulsa **Descargar**.
   Deben bajar los archivos a `Downloads\Zajuna\3389000\<tarea>\`, y luego mostrarse el mensaje para calificar con Claude Code.
5. Entra a Descargar evidencias **desde el menú**, sin `?cmid`.
   Elige una tarea con el buscador y la lista agrupada por guía, pulsa **Ver envíos** y debe cargar.

### 1.3 🔴⚠️ Informes de queja: generar los Word
1. **Informes de queja**. El paso 1 debe arrancar con tus evidencias de Reportes. Pulsa **Buscar candidatos**.
   El paso 1 debe quedar resumido con ✓ y abrirse el paso 2.
2. Marca 1 o 2 aprendices y pulsa **Siguiente**.
   Debe abrirse el paso 3 con coordinador, fecha, carpeta de teléfonos y captura.
3. Revisa la carpeta de teléfonos, pulsa **Importar** y luego sube la captura.
   Deben quedar con ✓ o con el nombre del archivo. Recarga la página: la carpeta debe recordarse.
4. Pulsa **Generar N informes**.
   Debe bajar el `.zip`. Abre un Word y revisa el coordinador, la fecha, los teléfonos y la captura.
5. Vuelve al paso 1 con **Editar** y cambia el umbral.
   El paso 2 debe pedir "busca de nuevo".

### 1.4 🔴 Reportes → Informe de queja (paso entre páginas)
1. En **Reportes**, genera el reporte y marca 2 aprendices.
   Aparece la barra fija abajo.
2. Pulsa **Informe de queja**.
   Debe abrir Informes de queja con las mismas evidencias, los candidatos ya buscados, esos 2 aprendices marcados y el **paso 3 abierto**.

### 1.5 🔴⚠️ Reportes: correos y novedades (escriben en debido proceso y novedades)
1. Marca un aprendiz y pulsa **Generar correos**.
   Debe abrir el diálogo con los borradores. **Cancela** sin confirmar si no quieres registrar el llamado.
2. Pulsa **Novedades** en el encabezado.
   Debe abrir el diálogo con los aprendices activos. Marca y desmarca uno: el conteo del botón debe cambiar y el aprendiz debe salir o volver a la vista "Activos sin novedad".

### 1.6 🔴⚠️ Cronograma: PDF por meses, descartar y eliminar
> Respaldo ya hecho: `backend/data/cronogramas/3389000.respaldo-26oct.json`.
1. En 3389000, pulsa **Subir archivos** y elige **varios PDF** del cronograma (por ejemplo, julio a noviembre).
   Debe aparecer el resumen "N PDF leídos: X evidencias nuevas · Y con fecha cambiada · Z sin cambios", la barra fija de cambios sin guardar y las filas nuevas marcadas **Nueva** (casi todas con su ID de Zajuna).
2. Pulsa **Descartar**.
   Debe volver la versión guardada, sin el resumen ni las marcas.
3. Repite el paso 1 y pulsa **Guardar**.
   Las marcas desaparecen y el total queda con las evidencias sumadas. Sube otra vez un mes ya cargado: debe decir "sin cambios" y no pedir guardar.
4. *(Opcional)* Sube un PDF de **otra ficha**: debe avisar "es de la ficha …; no se tomó".
5. *(Opcional)* Pulsa **Eliminar cronograma**.
   Debe pedir confirmación. **Cancela**, o elimínalo y restaura el respaldo.

### 1.7 🔴⚠️ Juicios: cargar solo un archivo
1. **Juicios › Actualizar datos**.
   Cada tarjeta debe decir "Ya cargado: … · fecha".
2. Sube **solo** el reporte de Sofía y guarda.
   Debe volver a Juicios. Antes se quedaba atrapado en la página.

### 1.8 🔴 Cuenta Zajuna con credenciales rechazadas *(si se presenta)*
- Si Zajuna rechaza tus credenciales guardadas (por ejemplo, después de cambiar la contraseña), el formulario debe **abrirse solo** al entrar a Cuenta Zajuna.

---

## 2. Revisadas por mí: repaso rápido

### 2.1 🟢 Navegación (PR #5)
- La barra lateral de la ficha muestra **Calificar / Seguimiento / Trámites**. "Sin nota" ya no aparece en el menú.
- El contador **amarillo** está en "Por calificar" y junto a la ficha. Después de una consulta nueva en Por calificar, debe actualizarse **sin recargar**.
- Al hacer scroll en una tabla larga, la **franja de arriba** (migas y Sincronizar) queda fija.
- La sincronización ("Hace …") es la misma en Dashboard y en Resumen.

### 2.2 🟢 Dashboard y Alertas (PR #6)
- El dashboard muestra la franja de bienvenida y una sola tabla de fichas. **Despliega una fila**: aparecen sus alertas y "Ver las N alertas" lleva a Alertas filtrado por esa ficha.
- Los accesos ✓ (Por calificar) y 📄 (Reportes) de cada fila abren la página correcta.
- En **Alertas**, pulsa "Revisar": abre Por calificar con la evidencia ya buscada.
- Los conteos de alertas son bajos: 3389000 tiene unas 4 críticas, no 107.

### 2.3 🟢 Reportes (PR #6)
- Pulsa **Cambiar**: el panel de evidencias tiene los filtros **fijos arriba** al hacer scroll. Prueba **"Hasta aquí"** en una evidencia: deben quedar marcadas todas las anteriores.
- Cambia la selección después de generar: aparece el aviso "genéralo de nuevo".
- Los **chips de alerta** filtran la tabla, y al pulsarlos otra vez vuelve a "Activos sin novedad".

### 2.4 🟢 Resumen (PR #7)
- Abre la **pestaña Evidencias**: arranca en "Cierre: Ya cerró" y la flecha despliega los aprendices sin nota.
- Entra a `/fichas/3389000/pendientes`: te lleva a **Resumen › Evidencias**.
- En el **Heatmap**, el menú "Exportar PDF" muestra cuántos aprendices y evidencias van. **Descarga el PDF** y revísalo. Activa "Elegir en el mapa": deben aparecer las casillas por fila y por columna.

### 2.5 🟢 F5: repaso
- **Actividad** abre en "Inactivos 30+ días", solo con activos.
- En **Debido proceso**, pulsa una tarjeta de etapa: filtra la tabla. Despliega una fila: el historial va en una fila completa. "Siguiente llamado" lleva a Reportes.
- **Juicios** abre en "Requiere acción", y pulsar una tarjeta de arriba filtra la tabla.

---

## 3. Transversal: una sola pasada al final

- [ ] **Modo oscuro** (botón ☀/☾): recorre Dashboard, Por calificar, Reportes e Informes de queja. Los textos deben leerse bien y los menús desplegables deben tener fondo.
- [ ] **Ventana angosta** (unos 400 px o el celular): Dashboard, Por calificar, Reportes y Actividad sin scroll lateral de toda la página, y el menú lateral abre con el botón ☰.
- [ ] **Navegar sin recargar**: entra a cada página desde el menú (no con F5) y prueba un enlace que lleve datos en la URL ("Revisar", "Descargar solo esta tarea", "Informe de queja").
- [ ] **Consola del navegador** (F12): sin errores rojos al recorrer las páginas.

---

## Si algo falla
Anota la página, el paso y qué viste (con captura si puedes). Si el PR #7 sigue abierto, el arreglo va en la misma rama.
