import type {
  CreatePartTypePayload,
  PartType,
  PartTypeCollection,
  UpdatePartTypePayload,
} from "../types/partTypes";

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
    // Fall through to the generic message.
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

export function getPartTypes(token: string): Promise<PartTypeCollection> {
  return requestJson<PartTypeCollection>("/part-types", token);
}

export function createPartType(
  token: string,
  payload: CreatePartTypePayload
): Promise<PartType> {
  return requestJson<PartType>("/part-types", token, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

// PATCH 085: custom part type update client
export function updatePartType(
  token: string,
  partTypeId: number,
  payload: UpdatePartTypePayload
): Promise<PartType> {
  return requestJson<PartType>(`/part-types/${partTypeId}`, token, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}
