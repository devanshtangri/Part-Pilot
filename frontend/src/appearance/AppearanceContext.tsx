import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";

import { useAuth } from "../auth/AuthContext";
import {
  getAppearanceSettings,
  updateAppearanceSettings
} from "../services/settingsClient";
import type {
  AppearanceTheme,
  ResolvedAppearanceTheme
} from "../types/settings";

// PARTPILOT:GLOBAL_APPEARANCE_RUNTIME:V412
const APPEARANCE_RUNTIME_MARKER = "PARTPILOT:GLOBAL_APPEARANCE_RUNTIME:V412";
export const APPEARANCE_STORAGE_KEY = "partpilot.appearance.theme";
const SYSTEM_LIGHT_QUERY = "(prefers-color-scheme: light)";

interface AppearanceContextValue {
  theme: AppearanceTheme;
  resolvedTheme: ResolvedAppearanceTheme;
  lightThemeAvailable: boolean;
  isLoading: boolean;
  isSaving: boolean;
  saved: boolean;
  error: string | null;
  selectTheme: (theme: AppearanceTheme) => Promise<void>;
  reload: () => void;
}

const AppearanceContext = createContext<AppearanceContextValue | null>(null);

function normalizeTheme(value: string | null): AppearanceTheme {
  return value === "light" || value === "system" ? value : "dark";
}

function readStoredTheme(): AppearanceTheme {
  try {
    return normalizeTheme(localStorage.getItem(APPEARANCE_STORAGE_KEY));
  } catch {
    return "dark";
  }
}

function resolveTheme(
  theme: AppearanceTheme
): ResolvedAppearanceTheme {
  if (theme !== "system") {
    return theme;
  }
  return window.matchMedia(SYSTEM_LIGHT_QUERY).matches
    ? "light"
    : "dark";
}

function applyTheme(
  theme: AppearanceTheme
): ResolvedAppearanceTheme {
  const resolved = resolveTheme(theme);
  const root = document.documentElement;

  root.dataset.theme = resolved;
  root.dataset.themePreference = theme;
  root.dataset.partpilotAppearanceRuntime = APPEARANCE_RUNTIME_MARKER;
  root.style.colorScheme = resolved;

  try {
    localStorage.setItem(APPEARANCE_STORAGE_KEY, theme);
  } catch {
    // The in-memory theme remains active when storage is unavailable.
  }

  return resolved;
}

export function AppearanceProvider({
  children
}: {
  children: ReactNode;
}) {
  const { token } = useAuth();
  const [theme, setTheme] = useState<AppearanceTheme>(() =>
    readStoredTheme()
  );
  const [resolvedTheme, setResolvedTheme] =
    useState<ResolvedAppearanceTheme>(() =>
      resolveTheme(readStoredTheme())
    );
  const [lightThemeAvailable, setLightThemeAvailable] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadVersion, setReloadVersion] = useState(0);
  const requestIdRef = useRef(0);
  const mutationIdRef = useRef(0);

  useEffect(() => {
    setResolvedTheme(applyTheme(theme));

    if (theme !== "system") {
      return;
    }

    const media = window.matchMedia(SYSTEM_LIGHT_QUERY);
    const handleSystemChange = () => {
      setResolvedTheme(applyTheme("system"));
    };

    media.addEventListener("change", handleSystemChange);
    return () => {
      media.removeEventListener("change", handleSystemChange);
    };
  }, [theme]);

  useEffect(() => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;

    if (!token) {
      setIsLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setError(null);
    setSaved(false);

    getAppearanceSettings(token)
      .then((settings) => {
        if (cancelled || requestIdRef.current !== requestId) {
          return;
        }
        setLightThemeAvailable(settings.light_theme_available);
        setTheme(settings.theme);
      })
      .catch((caught) => {
        if (cancelled || requestIdRef.current !== requestId) {
          return;
        }
        setError(
          caught instanceof Error
            ? caught.message
            : "Unable to load appearance settings"
        );
      })
      .finally(() => {
        if (!cancelled && requestIdRef.current === requestId) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [reloadVersion, token]);

  const selectTheme = useCallback(
    async (nextTheme: AppearanceTheme): Promise<void> => {
      if (!token) {
        setError("Your session is unavailable. Sign in again.");
        return;
      }
      if (
        nextTheme !== "dark" &&
        !lightThemeAvailable
      ) {
        setError(
          "The light appearance theme is not available for this installation."
        );
        return;
      }
      if (isSaving || nextTheme === theme) {
        return;
      }

      const previousTheme = theme;
      const mutationId = mutationIdRef.current + 1;
      mutationIdRef.current = mutationId;

      setTheme(nextTheme);
      setIsSaving(true);
      setSaved(false);
      setError(null);

      try {
        const settings = await updateAppearanceSettings(token, {
          theme: nextTheme
        });
        if (mutationIdRef.current !== mutationId) {
          return;
        }
        setLightThemeAvailable(settings.light_theme_available);
        setTheme(settings.theme);
        setSaved(true);
      } catch (caught) {
        if (mutationIdRef.current !== mutationId) {
          return;
        }
        setTheme(previousTheme);
        setError(
          caught instanceof Error
            ? caught.message
            : "Unable to save appearance settings"
        );
      } finally {
        if (mutationIdRef.current === mutationId) {
          setIsSaving(false);
        }
      }
    },
    [isSaving, lightThemeAvailable, theme, token]
  );

  const reload = useCallback(() => {
    setReloadVersion((value) => value + 1);
  }, []);

  const value = useMemo(
    () => ({
      theme,
      resolvedTheme,
      lightThemeAvailable,
      isLoading,
      isSaving,
      saved,
      error,
      selectTheme,
      reload
    }),
    [
      error,
      isLoading,
      isSaving,
      lightThemeAvailable,
      reload,
      resolvedTheme,
      saved,
      selectTheme,
      theme
    ]
  );

  return (
    <AppearanceContext.Provider value={value}>
      {children}
    </AppearanceContext.Provider>
  );
}

export function useAppearance(): AppearanceContextValue {
  const context = useContext(AppearanceContext);
  if (!context) {
    throw new Error(
      "useAppearance must be used inside AppearanceProvider"
    );
  }
  return context;
}
