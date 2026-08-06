import type {
  AppearanceSettings,
  AppearanceSettingsUpdatePayload,
  McpDirectAuthCustomHeaderPayload,
  McpDirectAuthKeyResponse,
  McpDirectAuthStatus,
  McpDirectAuthTrustedNetworkPayload,
  McpOAuthClientsResponse,
  McpSettings,
  McpSettingsUpdatePayload,
  ReservationSettings,
  ReservationSettingsUpdatePayload,
  SearchSettings,
  SearchSettingsUpdatePayload
} from "../types/settings";


const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";


interface ValidationDetail {
  msg?: string;
}


async function parseApiError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as {
      detail?: string | ValidationDetail[];
    };

    if (typeof body.detail === "string") {
      return body.detail;
    }

    if (Array.isArray(body.detail)) {
      const messages = body.detail
        .map((item) => item.msg)
        .filter(
          (message): message is string => Boolean(message)
        );

      if (messages.length > 0) {
        return messages.join("; ");
      }
    }
  } catch {
    // Fall through to the generic response message.
  }

  return `Request failed with status ${response.status}`;
}


async function requestJson<T>(
  path: string,
  token: string,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...init?.headers
    }
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return response.json() as Promise<T>;
}


// PATCH 194: protected search-settings frontend client
export function getSearchSettings(
  token: string
): Promise<SearchSettings> {
  return requestJson<SearchSettings>("/settings/search", token);
}


export function updateSearchSettings(
  token: string,
  payload: SearchSettingsUpdatePayload
): Promise<SearchSettings> {
  return requestJson<SearchSettings>("/settings/search", token, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}


// PARTPILOT:RESERVATION_EXPIRY_SETTINGS_CLIENT:V362
export function getReservationSettings(
  token: string
): Promise<ReservationSettings> {
  return requestJson<ReservationSettings>("/settings/reservations", token);
}

export function updateReservationSettings(
  token: string,
  payload: ReservationSettingsUpdatePayload
): Promise<ReservationSettings> {
  return requestJson<ReservationSettings>("/settings/reservations", token, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}


// PARTPILOT:APPEARANCE_SETTINGS_CLIENT:V412
export function getAppearanceSettings(
  token: string
): Promise<AppearanceSettings> {
  return requestJson<AppearanceSettings>("/settings/appearance", token);
}

export function updateAppearanceSettings(
  token: string,
  payload: AppearanceSettingsUpdatePayload
): Promise<AppearanceSettings> {
  return requestJson<AppearanceSettings>("/settings/appearance", token, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}


// PARTPILOT:MCP_SETTINGS_CLIENT:V473
export function getMcpSettings(
  token: string
): Promise<McpSettings> {
  return requestJson<McpSettings>("/settings/mcp", token);
}

export function updateMcpSettings(
  token: string,
  payload: McpSettingsUpdatePayload
): Promise<McpSettings> {
  return requestJson<McpSettings>("/settings/mcp", token, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}


// PARTPILOT:MCP_OAUTH_CLIENT_ADMIN_CLIENT:V540
export function getMcpOAuthClients(
  token: string
): Promise<McpOAuthClientsResponse> {
  return requestJson<McpOAuthClientsResponse>(
    "/settings/mcp/oauth-clients",
    token
  );
}

// PARTPILOT:MCP_OAUTH_CLIENT_REVOCATION_CLIENT:V541
export function revokeMcpOAuthClient(
  token: string,
  clientDatabaseId: number
): Promise<McpOAuthClientsResponse> {
  return requestJson<McpOAuthClientsResponse>(
    `/settings/mcp/oauth-clients/${clientDatabaseId}`,
    token,
    { method: "DELETE" }
  );
}


// PARTPILOT:MCP_TRUSTED_NETWORK_CLIENT:V510
export function getMcpDirectAuth(
  token: string
): Promise<McpDirectAuthStatus> {
  return requestJson<McpDirectAuthStatus>(
    "/settings/mcp/direct-auth",
    token
  );
}

export function rotateMcpDirectBearerKey(
  token: string
): Promise<McpDirectAuthKeyResponse> {
  return requestJson<McpDirectAuthKeyResponse>(
    "/settings/mcp/direct-auth/bearer-key",
    token,
    { method: "POST" }
  );
}

export function rotateMcpDirectCustomHeaderKey(
  token: string,
  payload: McpDirectAuthCustomHeaderPayload
): Promise<McpDirectAuthKeyResponse> {
  return requestJson<McpDirectAuthKeyResponse>(
    "/settings/mcp/direct-auth/custom-header",
    token,
    {
      method: "POST",
      body: JSON.stringify(payload)
    }
  );
}

export function configureMcpDirectTrustedNetworks(
  token: string,
  payload: McpDirectAuthTrustedNetworkPayload
): Promise<McpDirectAuthStatus> {
  return requestJson<McpDirectAuthStatus>(
    "/settings/mcp/direct-auth/trusted-network",
    token,
    {
      method: "POST",
      body: JSON.stringify(payload)
    }
  );
}

export function revealMcpDirectKey(
  token: string
): Promise<McpDirectAuthKeyResponse> {
  return requestJson<McpDirectAuthKeyResponse>(
    "/settings/mcp/direct-auth/reveal",
    token,
    { method: "POST" }
  );
}

export function disableMcpDirectAuth(
  token: string
): Promise<McpDirectAuthStatus> {
  return requestJson<McpDirectAuthStatus>(
    "/settings/mcp/direct-auth",
    token,
    { method: "DELETE" }
  );
}
