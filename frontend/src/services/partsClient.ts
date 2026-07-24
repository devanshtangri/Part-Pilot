import type {
  CreatePartPayload,
  Part,
  PartCollection
} from "../types/parts";


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


export function createPart(
  token: string,
  payload: CreatePartPayload
): Promise<Part> {
  return requestJson<Part>("/parts", token, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}


export function getParts(
  token: string,
  options?: {
    partTypeId?: number;
    limit?: number;
    offset?: number;
  }
): Promise<PartCollection> {
  const parameters = new URLSearchParams();

  if (options?.partTypeId) {
    parameters.set(
      "part_type_id",
      String(options.partTypeId)
    );
  }

  if (options?.limit !== undefined) {
    parameters.set("limit", String(options.limit));
  }

  if (options?.offset !== undefined) {
    parameters.set("offset", String(options.offset));
  }

  const query = parameters.toString();

  return requestJson<PartCollection>(
    `/parts${query ? `?${query}` : ""}`,
    token
  );
}


export function getPart(
  token: string,
  partId: number
): Promise<Part> {
  return requestJson<Part>(`/parts/${partId}`, token);
}
