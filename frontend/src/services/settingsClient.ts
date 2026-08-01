import type {
  AppearanceSettings,
  AppearanceSettingsUpdatePayload,
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
