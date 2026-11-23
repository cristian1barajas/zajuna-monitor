import { apiFetch, apiPost } from "./core";

// --- Cursos Zajuna del instructor (descubrimiento + registro de seguidos) ---

export interface ZajunaCourse {
  course_id: number;
  /** 7 dígitos, o "" si el curso no trae número de ficha. */
  ficha: string;
  shortname: string;
  fullname: string;
  program_code: string;
  /** "ADSO", "TPS"… o el nombre del curso si el programa no es conocido. */
  program_label: string;
  tracked: boolean;
}

export interface DiscoverCoursesResponse {
  courses: ZajunaCourse[];
  /** Moodle ocultó cursos detrás de "Más..." — la lista puede estar incompleta. */
  truncated: boolean;
}

export interface TrackedCoursesResponse {
  /** false = el instructor aún no ha guardado una selección (modo legado). */
  configured: boolean;
  courses: ZajunaCourse[];
}

/** Hace login real contra Zajuna (10-30 s). */
export function discoverCourses() {
  return apiFetch<DiscoverCoursesResponse>("/api/courses/discover");
}

export function fetchTrackedCourses() {
  return apiFetch<TrackedCoursesResponse>("/api/courses/tracked");
}

export function saveTrackedCourses(courses: ZajunaCourse[]) {
  return apiPost<TrackedCoursesResponse>("/api/courses/tracked", {
    courses: courses.map(({ course_id, ficha, shortname, fullname, program_code }) => ({
      course_id,
      ficha,
      shortname,
      fullname,
      program_code,
    })),
  });
}
