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
  getCurrentUser,
  getSetupStatus,
  loginUser,
  logoutUser,
  setupFirstUser
} from "../services/authClient";
import type { AuthTokenResponse, AuthUser, LoginRequest, SetupRequest } from "../types/auth";

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  setupComplete: boolean | null;
  isBooting: boolean;
  authError: string | null;
  setup: (payload: SetupRequest) => Promise<void>;
  login: (payload: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  clearAuthError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function authUserFromTokenResponse(response: AuthTokenResponse): AuthUser {
  const displayName = response.display_name;

  return {
    id: 0,
    username: response.username,
    display_name: displayName,
    is_active: true
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(AUTH_TOKEN_STORAGE_KEY));
  const [setupComplete, setSetupComplete] = useState<boolean | null>(null);
  const [isBooting, setIsBooting] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function bootAuth() {
      try {
        const status = await getSetupStatus();

        if (cancelled) {
          return;
        }

        setSetupComplete(status.setup_complete);

        const storedToken = localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
        if (status.setup_complete && storedToken) {
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
          setAuthError(error instanceof Error ? error.message : "Unable to reach the auth service");
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
  }, []);

  const persistAuth = useCallback((response: AuthTokenResponse) => {
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, response.token);
    setToken(response.token);
    setUser(authUserFromTokenResponse(response));
    setSetupComplete(true);
  }, []);

  const setup = useCallback(
    async (payload: SetupRequest) => {
      setAuthError(null);
      const response = await setupFirstUser(payload);
      persistAuth(response);
    },
    [persistAuth]
  );

  const login = useCallback(
    async (payload: LoginRequest) => {
      setAuthError(null);
      const response = await loginUser(payload);
      persistAuth(response);
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
      setupComplete,
      isBooting,
      authError,
      setup,
      login,
      logout,
      clearAuthError
    }),
    [authError, clearAuthError, isBooting, login, logout, setup, setupComplete, token, user]
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
