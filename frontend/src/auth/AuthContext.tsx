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

import {
  AUTH_TOKEN_STORAGE_KEY,
  completeApplicationSetup,
  getCurrentUser,
  getProfileAvatarImage,
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
  avatarImageUrl: string | null;
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
  refreshUser: () => Promise<AuthUser>;
  syncDefaultCurrency: (currency: string) => void;
  syncTimezone: (timezone: string) => void;
  clearAuthError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function authUserFromTokenResponse(response: AuthTokenResponse): AuthUser {
  return {
    id: 0,
    username: response.username,
    display_name: response.display_name,
    avatar_id: "initials",
    has_custom_avatar: false,
    avatar_image_sha256: null,
    role: response.role,
    is_active: true
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const avatarImageUrlRef = useRef<string | null>(null);
  const [avatarImageUrl, setAvatarImageUrl] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
  );
  const [accountExists, setAccountExists] = useState<boolean | null>(null);
  const [setupComplete, setSetupComplete] = useState<boolean | null>(null);
  const [defaultCurrency, setDefaultCurrency] = useState<string | null>(null);
  const [timezone, setTimezone] = useState<string | null>(null);
  const [isBooting, setIsBooting] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);

  // PARTPILOT:AUTH_CUSTOM_AVATAR_CONTEXT:V602
  const replaceAvatarImageUrl = useCallback((blob: Blob | null) => {
    const previous = avatarImageUrlRef.current;
    const next = blob ? URL.createObjectURL(blob) : null;
    avatarImageUrlRef.current = next;
    setAvatarImageUrl(next);
    if (previous) {
      URL.revokeObjectURL(previous);
    }
  }, []);

  const loadAvatarImage = useCallback(
    async (activeToken: string, currentUser: AuthUser): Promise<Blob | null> => {
      if (!currentUser.has_custom_avatar) {
        return null;
      }
      try {
        return await getProfileAvatarImage(activeToken);
      } catch {
        return null;
      }
    },
    []
  );

  useEffect(() => {
    return () => {
      if (avatarImageUrlRef.current) {
        URL.revokeObjectURL(avatarImageUrlRef.current);
        avatarImageUrlRef.current = null;
      }
    };
  }, []);

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
            const avatarBlob = await loadAvatarImage(
              storedToken,
              currentUser
            );

            if (!cancelled) {
              setToken(storedToken);
              setUser(currentUser);
              replaceAvatarImageUrl(avatarBlob);
            }
          } catch {
            localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);

            if (!cancelled) {
              setToken(null);
              setUser(null);
              replaceAvatarImageUrl(null);
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
  }, [applySetupStatus, loadAvatarImage, replaceAvatarImageUrl]);

  const persistAuth = useCallback((response: AuthTokenResponse) => {
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, response.token);
    setToken(response.token);
    setUser(authUserFromTokenResponse(response));
    replaceAvatarImageUrl(null);
  }, [replaceAvatarImageUrl]);

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
      try {
        const currentUser = await getCurrentUser(response.token);
        const avatarBlob = await loadAvatarImage(
          response.token,
          currentUser
        );
        setUser(currentUser);
        replaceAvatarImageUrl(avatarBlob);
      } catch {
        // Token-response identity remains usable if hydration is unavailable.
      }
    },
    [loadAvatarImage, persistAuth, replaceAvatarImageUrl]
  );

  const logout = useCallback(async () => {
    const activeToken = token;

    localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    setToken(null);
    setUser(null);
    replaceAvatarImageUrl(null);

    if (activeToken) {
      try {
        await logoutUser(activeToken);
      } catch {
        // Local logout still succeeds even if the server call fails.
      }
    }
  }, [replaceAvatarImageUrl, token]);

  // PARTPILOT:AUTH_REFRESH_CONTEXT:V591
  const refreshUser = useCallback(async () => {
    if (!token) {
      throw new Error("Sign in before refreshing account details");
    }

    const currentUser = await getCurrentUser(token);
    const avatarBlob = await loadAvatarImage(token, currentUser);
    setUser(currentUser);
    replaceAvatarImageUrl(avatarBlob);
    return currentUser;
  }, [loadAvatarImage, replaceAvatarImageUrl, token]);

  // PARTPILOT:CURRENCY_PREFERENCE_AUTH_SYNC:V675
  const syncDefaultCurrency = useCallback((currency: string) => {
    setDefaultCurrency(currency.trim().toUpperCase());
  }, []);

  // PARTPILOT:TIMEZONE_PREFERENCE_AUTH_SYNC:V676
  const syncTimezone = useCallback((nextTimezone: string) => {
    setTimezone(nextTimezone.trim());
  }, []);

  const clearAuthError = useCallback(() => {
    setAuthError(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      avatarImageUrl,
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
      refreshUser,
      syncDefaultCurrency,
      syncTimezone,
      clearAuthError
    }),
    [
      accountExists,
      authError,
      avatarImageUrl,
      clearAuthError,
      completeSetup,
      defaultCurrency,
      isBooting,
      login,
      logout,
      refreshUser,
      setup,
      setupComplete,
      syncDefaultCurrency,
      syncTimezone,
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
