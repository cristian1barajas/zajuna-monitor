"use client";

/**
 * Preferencias personales del instructor, persistidas en localStorage:
 * - qué fichas se muestran en el dashboard (las demás se ocultan)
 * - el ancho del sidebar (ajustable arrastrando su borde)
 *
 * Se comparten entre el Sidebar (donde se togglean/redimensiona) y el
 * Dashboard (que filtra y recalcula el resumen).
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

const STORAGE_KEY = "zajuna-dashboard-prefs";

export const SIDEBAR_MIN = 208;
export const SIDEBAR_MAX = 420;
export const SIDEBAR_DEFAULT = 256;

interface DashboardPrefs {
  hiddenFichas: Set<string>;
  isFichaVisible: (ficha: string) => boolean;
  toggleFichaVisible: (ficha: string) => void;
  sidebarWidth: number;
  setSidebarWidth: (width: number) => void;
}

const DashboardPrefsContext = createContext<DashboardPrefs>({
  hiddenFichas: new Set(),
  isFichaVisible: () => true,
  toggleFichaVisible: () => {},
  sidebarWidth: SIDEBAR_DEFAULT,
  setSidebarWidth: () => {},
});

export function useDashboardPrefs() {
  return useContext(DashboardPrefsContext);
}

function clampWidth(w: number): number {
  return Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, w));
}

export function DashboardPrefsProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [hiddenFichas, setHiddenFichas] = useState<Set<string>>(new Set());
  const [sidebarWidth, setSidebarWidthState] = useState(SIDEBAR_DEFAULT);
  const [loaded, setLoaded] = useState(false);

  // Cargar preferencias al montar (evita mismatch de hidratación SSR).
  /* eslint-disable react-hooks/set-state-in-effect -- TODO(code-quality): sincroniza estado con localStorage (sistema externo) tras hidratar; necesario para no romper SSR */
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as {
          hiddenFichas?: string[];
          sidebarWidth?: number;
        };
        if (parsed.hiddenFichas) setHiddenFichas(new Set(parsed.hiddenFichas));
        if (parsed.sidebarWidth)
          setSidebarWidthState(clampWidth(parsed.sidebarWidth));
      }
    } catch {
      /* localStorage no disponible */
    }
    setLoaded(true);
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  // Persistir en cada cambio (tras la carga inicial)
  useEffect(() => {
    if (!loaded) return;
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          hiddenFichas: [...hiddenFichas],
          sidebarWidth,
        })
      );
    } catch {
      /* ignore */
    }
  }, [hiddenFichas, sidebarWidth, loaded]);

  const isFichaVisible = useCallback(
    (ficha: string) => !hiddenFichas.has(ficha),
    [hiddenFichas]
  );

  const toggleFichaVisible = useCallback((ficha: string) => {
    setHiddenFichas((prev) => {
      const next = new Set(prev);
      if (next.has(ficha)) next.delete(ficha);
      else next.add(ficha);
      return next;
    });
  }, []);

  const setSidebarWidth = useCallback((width: number) => {
    setSidebarWidthState(clampWidth(width));
  }, []);

  const value = useMemo(
    () => ({
      hiddenFichas,
      isFichaVisible,
      toggleFichaVisible,
      sidebarWidth,
      setSidebarWidth,
    }),
    [hiddenFichas, isFichaVisible, toggleFichaVisible, sidebarWidth, setSidebarWidth]
  );

  return (
    <DashboardPrefsContext.Provider value={value}>
      {children}
    </DashboardPrefsContext.Provider>
  );
}
