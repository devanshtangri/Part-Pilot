import type {
  CreatePartPayload,
  DeletedPart,
  DeletedPartCollection,
  Part,
  PartCollection,
  LowStockSummary,
  PartMovementCollection,
  QuantityAdjustmentPayload,
  QuantityAdjustmentResponse,
  UpdatePartPayload
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


// PATCH 169: Stored Parts location filter client
export function getParts(
  token: string,
  options?: {
    partTypeId?: number;
    locationId?: number;
    search?: string;
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

  if (options?.locationId) {
    parameters.set(
      "location_id",
      String(options.locationId)
    );
  }

  // PATCH 217: typed backend universal-search option
  const search = options?.search?.trim();
  if (search) {
    parameters.set("search", search);
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


// PATCH 186: dashboard low-stock summary client
export function getLowStockParts(
  token: string,
  options?: {
    partTypeId?: number;
    locationId?: number;
    limit?: number;
  }
): Promise<LowStockSummary> {
  const parameters = new URLSearchParams();

  if (options?.partTypeId) {
    parameters.set("part_type_id", String(options.partTypeId));
  }

  if (options?.locationId) {
    parameters.set("location_id", String(options.locationId));
  }

  if (options?.limit !== undefined) {
    parameters.set("limit", String(options.limit));
  }

  const query = parameters.toString();

  return requestJson<LowStockSummary>(
    `/parts/low-stock${query ? `?${query}` : ""}`,
    token
  );
}


export function getPart(
  token: string,
  partId: number
): Promise<Part> {
  return requestJson<Part>(`/parts/${partId}`, token);
}

// PATCH 137: stock quantity adjustment and movement history client
export function adjustPartQuantity(
  token: string,
  partId: number,
  payload: QuantityAdjustmentPayload
): Promise<QuantityAdjustmentResponse> {
  return requestJson<QuantityAdjustmentResponse>(
    `/parts/${partId}/quantity-adjustments`,
    token,
    {
      method: "POST",
      body: JSON.stringify(payload)
    }
  );
}

export function getPartMovements(
  token: string,
  partId: number,
  options?: { limit?: number }
): Promise<PartMovementCollection> {
  const parameters = new URLSearchParams();
  if (options?.limit !== undefined) {
    parameters.set("limit", String(options.limit));
  }
  const query = parameters.toString();
  return requestJson<PartMovementCollection>(
    `/parts/${partId}/movements${query ? `?${query}` : ""}`,
    token
  );
}

// PATCH 143: existing-part metadata update client
export function updatePart(
  token: string,
  partId: number,
  payload: UpdatePartPayload
): Promise<Part> {
  return requestJson<Part>(`/parts/${partId}`, token, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

// PATCH 153: recoverable part deletion and restoration client
export function getDeletedParts(
  token: string,
  options?: {
    limit?: number;
    offset?: number;
  }
): Promise<DeletedPartCollection> {
  const parameters = new URLSearchParams();

  if (options?.limit !== undefined) {
    parameters.set("limit", String(options.limit));
  }

  if (options?.offset !== undefined) {
    parameters.set("offset", String(options.offset));
  }

  const query = parameters.toString();
  return requestJson<DeletedPartCollection>(
    `/parts/deleted${query ? `?${query}` : ""}`,
    token
  );
}

export function deletePart(
  token: string,
  partId: number
): Promise<DeletedPart> {
  return requestJson<DeletedPart>(`/parts/${partId}`, token, {
    method: "DELETE"
  });
}

export function restorePart(
  token: string,
  partId: number
): Promise<Part> {
  return requestJson<Part>(`/parts/${partId}/restore`, token, {
    method: "POST"
  });
}
