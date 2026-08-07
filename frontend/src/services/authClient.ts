import type {
  ApiAuthTokenResponse,
  AuthTokenResponse,
  AuthUser,
  DebugResetResponse,
  LoginRequest,
  OtherSessionsRevokeResponse,
  PasswordChangeRequest,
  PasswordChangeResponse,
  ProfileResponse,
  ProfileUpdateRequest,
  SessionListResponse,
  SessionRevokeResponse,
  SetupPreferencesRequest,
  SetupRequest,
  SetupStatusResponse
} from "../types/auth";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export const AUTH_TOKEN_STORAGE_KEY = "partpilot.auth.token";

async function parseAuthError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // Fall through to the generic message.
  }

  return `Request failed with status ${response.status}`;
}

function mapTokenResponse(response: ApiAuthTokenResponse): AuthTokenResponse {
  return {
    token: response.token,
    username: response.username,
    display_name: response.display_name
  };
}

function setupPreferencesBody(payload: SetupPreferencesRequest) {
  return {
    default_currency: payload.defaultCurrency.trim().toUpperCase(),
    timezone: payload.timezone.trim()
  };
}

export async function getSetupStatus(): Promise<SetupStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/setup-status`);

  if (!response.ok) {
    throw new Error(await parseAuthError(response));
  }

  return response.json();
}

export async function setupFirstUser(
  payload: SetupRequest
): Promise<AuthTokenResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/setup`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      display_name: payload.displayName,
      username: payload.username,
      password: payload.password,
      ...setupPreferencesBody(payload)
    })
  });

  if (!response.ok) {
    throw new Error(await parseAuthError(response));
  }

  return mapTokenResponse(await response.json());
}

export async function completeApplicationSetup(
  token: string,
  payload: SetupPreferencesRequest
): Promise<SetupStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/complete-setup`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(setupPreferencesBody(payload))
  });

  if (!response.ok) {
    throw new Error(await parseAuthError(response));
  }

  return response.json();
}

export async function loginUser(
  payload: LoginRequest
): Promise<AuthTokenResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(await parseAuthError(response));
  }

  return mapTokenResponse(await response.json());
}

export async function getCurrentUser(token: string): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });

  if (!response.ok) {
    throw new Error(await parseAuthError(response));
  }

  return response.json();
}

export async function logoutUser(token: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/auth/logout`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    }
  });

  if (!response.ok) {
    throw new Error(await parseAuthError(response));
  }
}

export async function resetApplicationDatabase(
  token: string,
  confirmation: string
): Promise<DebugResetResponse> {
  const response = await fetch(
    `${API_BASE_URL}/auth/debug/reset-database`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ confirmation })
    }
  );

  if (!response.ok) {
    throw new Error(await parseAuthError(response));
  }

  return response.json();
}

// PARTPILOT:AUTH_ACCOUNT_SECURITY_CLIENT:V591
function bearerHeaders(token: string) {
  return {
    Authorization: `Bearer ${token}`
  };
}

export async function getProfile(token: string): Promise<ProfileResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/profile`, {
    headers: bearerHeaders(token)
  });

  if (!response.ok) {
    throw new Error(await parseAuthError(response));
  }

  return response.json();
}

export async function updateProfile(
  token: string,
  payload: ProfileUpdateRequest
): Promise<ProfileResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/profile`, {
    method: "PUT",
    headers: {
      ...bearerHeaders(token),
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      username: payload.username.trim().toLowerCase(),
      display_name: payload.displayName.trim(),
      avatar_id: payload.avatarId
    })
  });

  if (!response.ok) {
    throw new Error(await parseAuthError(response));
  }

  return response.json();
}

export async function changePassword(
  token: string,
  payload: PasswordChangeRequest
): Promise<PasswordChangeResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/change-password`, {
    method: "POST",
    headers: {
      ...bearerHeaders(token),
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      current_password: payload.currentPassword,
      new_password: payload.newPassword
    })
  });

  if (!response.ok) {
    throw new Error(await parseAuthError(response));
  }

  return response.json();
}

export async function getSessions(
  token: string
): Promise<SessionListResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/sessions`, {
    headers: bearerHeaders(token)
  });

  if (!response.ok) {
    throw new Error(await parseAuthError(response));
  }

  return response.json();
}

export async function revokeSession(
  token: string,
  sessionId: number
): Promise<SessionRevokeResponse> {
  const response = await fetch(
    `${API_BASE_URL}/auth/sessions/${sessionId}`,
    {
      method: "DELETE",
      headers: bearerHeaders(token)
    }
  );

  if (!response.ok) {
    throw new Error(await parseAuthError(response));
  }

  return response.json();
}

export async function revokeAllOtherSessions(
  token: string
): Promise<OtherSessionsRevokeResponse> {
  const response = await fetch(
    `${API_BASE_URL}/auth/sessions/revoke-all-other`,
    {
      method: "POST",
      headers: bearerHeaders(token)
    }
  );

  if (!response.ok) {
    throw new Error(await parseAuthError(response));
  }

  return response.json();
}
