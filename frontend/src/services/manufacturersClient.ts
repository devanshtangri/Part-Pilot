import type {
  Manufacturer,
  ManufacturerCollection
} from "../types/manufacturers";


const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";


async function parseApiError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as {
      detail?: string;
    };

    if (typeof body.detail === "string") {
      return body.detail;
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


export function getManufacturers(
  token: string
): Promise<ManufacturerCollection> {
  return requestJson<ManufacturerCollection>(
    "/manufacturers",
    token
  );
}


export function createManufacturer(
  token: string,
  name: string
): Promise<Manufacturer> {
  return requestJson<Manufacturer>(
    "/manufacturers",
    token,
    {
      method: "POST",
      body: JSON.stringify({ name })
    }
  );
}
