// PARTPILOT:RESERVATIONS_CLIENT:V340

import type {
  ReservablePart,
  Reservation,
  ReservationActivityCollection,
  ReservationCollection,
  ReservationCreatePayload,
  ReservationStatus
} from "../types/reservations";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

interface ValidationDetail {
  msg?: string;
}

interface PartSearchResponse {
  parts?: Array<{
    id: number;
    part_number: string;
    name: string;
    total_quantity: number;
    reserved_quantity?: number;
    available_quantity?: number;
    manufacturer_name?: string | null;
    location_name?: string | null;
  }>;
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

export function getReservations(
  token: string,
  options?: {
    status?: ReservationStatus;
    limit?: number;
    offset?: number;
    signal?: AbortSignal;
  }
): Promise<ReservationCollection> {
  const parameters = new URLSearchParams();
  if (options?.status) {
    parameters.set("status", options.status);
  }
  if (options?.limit !== undefined) {
    parameters.set("limit", String(options.limit));
  }
  if (options?.offset !== undefined) {
    parameters.set("offset", String(options.offset));
  }

  const query = parameters.toString();
  return requestJson<ReservationCollection>(
    `/reservations${query ? `?${query}` : ""}`,
    token,
    { signal: options?.signal }
  );
}

export function getReservation(
  token: string,
  reservationId: number,
  signal?: AbortSignal
): Promise<Reservation> {
  return requestJson<Reservation>(
    `/reservations/${reservationId}`,
    token,
    { signal }
  );
}

// PARTPILOT:RESERVATION_ACTIVITY_CLIENT:V340
export function getReservationActivity(
  token: string,
  reservationId: number,
  signal?: AbortSignal
): Promise<ReservationActivityCollection> {
  return requestJson<ReservationActivityCollection>(
    `/reservations/${reservationId}/activity`,
    token,
    { signal }
  );
}

export function createReservation(
  token: string,
  payload: ReservationCreatePayload
): Promise<Reservation> {
  return requestJson<Reservation>("/reservations", token, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

function runLifecycleAction(
  token: string,
  reservationId: number,
  action: "cancel" | "consume" | "expire"
): Promise<Reservation> {
  return requestJson<Reservation>(
    `/reservations/${reservationId}/${action}`,
    token,
    { method: "POST" }
  );
}

export function cancelReservation(
  token: string,
  reservationId: number
): Promise<Reservation> {
  return runLifecycleAction(token, reservationId, "cancel");
}

export function consumeReservation(
  token: string,
  reservationId: number
): Promise<Reservation> {
  return runLifecycleAction(token, reservationId, "consume");
}

export function expireReservation(
  token: string,
  reservationId: number
): Promise<Reservation> {
  return runLifecycleAction(token, reservationId, "expire");
}

export async function searchReservableParts(
  token: string,
  query: string,
  signal?: AbortSignal
): Promise<ReservablePart[]> {
  const parameters = new URLSearchParams({
    search: query,
    limit: "20",
    offset: "0"
  });
  const response = await requestJson<PartSearchResponse>(
    `/parts?${parameters.toString()}`,
    token,
    { signal }
  );

  return (response.parts ?? [])
    .map((part) => {
      const reservedQuantity = Number(part.reserved_quantity ?? 0);
      const totalQuantity = Number(part.total_quantity ?? 0);
      const availableQuantity = Number(
        part.available_quantity ?? totalQuantity - reservedQuantity
      );
      return {
        id: part.id,
        part_number: part.part_number,
        name: part.name,
        total_quantity: totalQuantity,
        reserved_quantity: reservedQuantity,
        available_quantity: availableQuantity,
        manufacturer_name: part.manufacturer_name ?? null,
        location_name: part.location_name ?? null
      };
    })
    .filter((part) => part.available_quantity > 0);
}
