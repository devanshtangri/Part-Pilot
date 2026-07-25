import type {
  PackageCollection,
  PackageOption
} from "../types/packages";


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


export function getPackages(
  token: string
): Promise<PackageCollection> {
  return requestJson<PackageCollection>(
    "/packages",
    token
  );
}


export function createPackage(
  token: string,
  name: string
): Promise<PackageOption> {
  return requestJson<PackageOption>(
    "/packages",
    token,
    {
      method: "POST",
      body: JSON.stringify({ name })
    }
  );
}
