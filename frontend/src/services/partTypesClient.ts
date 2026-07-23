import type { PartTypeCollection } from "../types/partTypes";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

async function parseApiError(response: Response): Promise<string> {
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

export async function getPartTypes(
  token: string
): Promise<PartTypeCollection> {
  const response = await fetch(`${API_BASE_URL}/part-types`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return response.json();
}
