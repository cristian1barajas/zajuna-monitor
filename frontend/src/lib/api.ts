/**
 * Barrel del cliente API del monitor, dividido por dominio en `./api/`.
 * Los consumidores siguen importando de "@/lib/api"; la implementación
 * vive en módulos con una responsabilidad cada uno:
 *
 * - core.ts            → fetch autenticado, refresh de sesión, caché de lecturas
 * - fichas.ts          → health, dashboard, fichas, pendientes, alertas, actividad
 * - cronograma.ts      → cronograma de evidencias
 * - reports.ts         → reportes, debido proceso, informes de queja, novedades
 * - juicios.ts         → cruce RAP / reporte Sofía
 * - scraper.ts         → sincronización (trigger/status)
 * - pending-grading.ts → assignments y pendientes de calificar
 * - forums.ts          → foros: aportes que esperan réplica del instructor
 * - downloads.ts       → descarga de evidencias
 * - zajuna-account.ts  → cuenta Zajuna por instructor
 * - courses.ts         → cursos Zajuna del instructor (agregar grupo)
 * - outlook.ts         → soportes de llamados desde Outlook (PDF en ZIP)
 */

export * from "./api/core";
export * from "./api/fichas";
export * from "./api/cronograma";
export * from "./api/reports";
export * from "./api/juicios";
export * from "./api/scraper";
export * from "./api/pending-grading";
export * from "./api/forums";
export * from "./api/downloads";
export * from "./api/zajuna-account";
export * from "./api/courses";
export * from "./api/outlook";
