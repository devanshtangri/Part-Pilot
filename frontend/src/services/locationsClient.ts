import type {
  LocationCollection,
  LocationCreatePayload,
  LocationOption
} from "../types/locations";


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


// PATCH 160: reusable location catalogue frontend client
export function getLocations(
  token: string
): Promise<LocationCollection> {
  return requestJson<LocationCollection>("/locations", token);
}


export function createLocation(
  token: string,
  payload: LocationCreatePayload
): Promise<LocationOption> {
  return requestJson<LocationOption>("/locations", token, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
