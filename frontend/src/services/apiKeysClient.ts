import type {
  ApiKeyListResponse,
  ApiKeyMutationPayload,
  ApiKeySecretResponse,
  ApiKeySummary
} from "../types/apiKeys";

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
        .filter((message): message is string => Boolean(message));
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

// PARTPILOT:REST_API_KEY_SETTINGS_CLIENT:V618
export function getApiKeys(token: string): Promise<ApiKeyListResponse> {
  return requestJson<ApiKeyListResponse>("/settings/api-keys", token);
}

export function createApiKey(
  token: string,
  payload: ApiKeyMutationPayload
): Promise<ApiKeySecretResponse> {
  return requestJson<ApiKeySecretResponse>("/settings/api-keys", token, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateApiKey(
  token: string,
  keyId: number,
  payload: ApiKeyMutationPayload
): Promise<ApiKeySummary> {
  return requestJson<ApiKeySummary>(`/settings/api-keys/${keyId}`, token, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function rotateApiKey(
  token: string,
  keyId: number
): Promise<ApiKeySecretResponse> {
  return requestJson<ApiKeySecretResponse>(
    `/settings/api-keys/${keyId}/rotate`,
    token,
    { method: "POST" }
  );
}

export function revokeApiKey(
  token: string,
  keyId: number
): Promise<ApiKeySummary> {
  return requestJson<ApiKeySummary>(`/settings/api-keys/${keyId}`, token, {
    method: "DELETE"
  });
}
