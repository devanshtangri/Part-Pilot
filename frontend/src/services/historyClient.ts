// PARTPILOT:SYSTEM_HISTORY_CLIENT:V408

import type {
  HistoryCollection,
  HistoryFilterOptions,
  HistoryQueryOptions
} from "../types/history";

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
  signal?: AbortSignal
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    signal
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return response.json() as Promise<T>;
}

export function getHistory(
  token: string,
  options: HistoryQueryOptions = {}
): Promise<HistoryCollection> {
  const parameters = new URLSearchParams();

  if (options.kind) {
    parameters.set("kind", options.kind);
  }
  if (options.entityType) {
    parameters.set("entity_type", options.entityType);
  }
  if (options.eventType) {
    parameters.set("event_type", options.eventType);
  }
  if (options.actorType) {
    parameters.set("actor_type", options.actorType);
  }
  if (options.actorUserId !== undefined) {
    parameters.set("actor_user_id", String(options.actorUserId));
  }
  if (options.movementType) {
    parameters.set("movement_type", options.movementType);
  }
  if (options.from) {
    parameters.set("from", options.from);
  }
  if (options.to) {
    parameters.set("to", options.to);
  }
  if (options.query) {
    parameters.set("q", options.query);
  }
  if (options.limit !== undefined) {
    parameters.set("limit", String(options.limit));
  }
  if (options.offset !== undefined) {
    parameters.set("offset", String(options.offset));
  }

  const query = parameters.toString();
  return requestJson<HistoryCollection>(
    `/history${query ? `?${query}` : ""}`,
    token,
    options.signal
  );
}

export function getHistoryFilterOptions(
  token: string,
  signal?: AbortSignal
): Promise<HistoryFilterOptions> {
  return requestJson<HistoryFilterOptions>(
    "/history/filter-options",
    token,
    signal
  );
}
