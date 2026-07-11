import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState
} from "react";

import {
  AUTH_TOKEN_STORAGE_KEY,
  completeApplicationSetup,
  getCurrentUser,
  getSetupStatus,
  loginUser,
  logoutUser,
  setupFirstUser
} from "../services/authClient";
import type {
  AuthTokenResponse,
  AuthUser,
  LoginRequest,
  SetupPreferencesRequest,
  SetupRequest,
  SetupStatusResponse
} from "../types/auth";

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  accountExists: boolean | null;
  setupComplete: boolean | null;
  defaultCurrency: string | null;
  timezone: string | null;
  isBooting: boolean;
  authError: string | null;
  setup: (payload: SetupRequest) => Promise<void>;
  completeSetup: (payload: SetupPreferencesRequest) => Promise<void>;
  login: (payload: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  clearAuthError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function authUserFromTokenResponse(response: AuthTokenResponse): AuthUser {
  return {
    id: 0,
    username: response.username,
    display_name: response.display_name,
    is_active: true
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
  );
  const [accountExists, setAccountExists] = useState<boolean | null>(null);
  const [setupComplete, setSetupComplete] = useState<boolean | null>(null);
  const [defaultCurrency, setDefaultCurrency] = useState<string | null>(null);
  const [timezone, setTimezone] = useState<string | null>(null);
  const [isBooting, setIsBooting] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);

  const applySetupStatus = useCallback((status: SetupStatusResponse) => {
    setAccountExists(status.account_exists);
    setSetupComplete(status.setup_complete);
    setDefaultCurrency(status.default_currency);
    setTimezone(status.timezone);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function bootAuth() {
      try {
        const status = await getSetupStatus();

        if (cancelled) {
          return;
        }

        applySetupStatus(status);

        const storedToken = localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
        if (status.account_exists && storedToken) {
          try {
            const currentUser = await getCurrentUser(storedToken);

            if (!cancelled) {
              setToken(storedToken);
              setUser(currentUser);
            }
          } catch {
            localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);

            if (!cancelled) {
              setToken(null);
              setUser(null);
            }
          }
        }
      } catch (error) {
        if (!cancelled) {
          setAuthError(
            error instanceof Error
              ? error.message
              : "Unable to reach the auth service"
          );
        }
      } finally {
        if (!cancelled) {
          setIsBooting(false);
        }
      }
    }

    bootAuth();

    return () => {
      cancelled = true;
    };
  }, [applySetupStatus]);

  const persistAuth = useCallback((response: AuthTokenResponse) => {
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, response.token);
    setToken(response.token);
    setUser(authUserFromTokenResponse(response));
  }, []);

  const setup = useCallback(
    async (payload: SetupRequest) => {
      setAuthError(null);
      const response = await setupFirstUser(payload);
      persistAuth(response);
      setAccountExists(true);
      setSetupComplete(true);
      setDefaultCurrency(payload.defaultCurrency.trim().toUpperCase());
      setTimezone(payload.timezone.trim());
    },
    [persistAuth]
  );

  const completeSetup = useCallback(
    async (payload: SetupPreferencesRequest) => {
      if (!token) {
        throw new Error("Sign in before completing setup");
      }

      setAuthError(null);
      const status = await completeApplicationSetup(token, payload);
      applySetupStatus(status);
    },
    [applySetupStatus, token]
  );

  const login = useCallback(
    async (payload: LoginRequest) => {
      setAuthError(null);
      const response = await loginUser(payload);
      persistAuth(response);
      setAccountExists(true);
    },
    [persistAuth]
  );

  const logout = useCallback(async () => {
    const activeToken = token;

    localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    setToken(null);
    setUser(null);

    if (activeToken) {
      try {
        await logoutUser(activeToken);
      } catch {
        // Local logout still succeeds even if the server call fails.
      }
    }
  }, [token]);

  const clearAuthError = useCallback(() => {
    setAuthError(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      token,
      accountExists,
      setupComplete,
      defaultCurrency,
      timezone,
      isBooting,
      authError,
      setup,
      completeSetup,
      login,
      logout,
      clearAuthError
    }),
    [
      accountExists,
      authError,
      clearAuthError,
      completeSetup,
      defaultCurrency,
      isBooting,
      login,
      logout,
      setup,
      setupComplete,
      timezone,
      token,
      user
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }

  return context;
}
