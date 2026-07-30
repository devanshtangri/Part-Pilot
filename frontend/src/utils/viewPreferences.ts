// PARTPILOT:DURABLE_VIEW_PREFERENCES:V355

export const VIEW_PREFERENCE_KEYS = {
  inventoryPageSize: "partpilot.inventory.page-size",
  inventoryStockFilter: "partpilot.inventory.stock-filter",
  inventoryPartTypeFilter: "partpilot.inventory.part-type-filter",
  inventoryLocationFilter: "partpilot.inventory.location-filter",
  inventoryAvailableSortBy: "partpilot.inventory.available-sort-by",
  inventoryAvailableSortDirection:
    "partpilot.inventory.available-sort-direction",
  inventoryOutOfStockSortBy: "partpilot.inventory.out-of-stock-sort-by",
  inventoryOutOfStockSortDirection:
    "partpilot.inventory.out-of-stock-sort-direction",
  partManagerTypeFilter: "partpilot.part-manager.type-filter"
} as const;

function browserStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function removeViewPreference(key: string): void {
  try {
    browserStorage()?.removeItem(key);
  } catch {
    // A blocked or full storage area must never break the workspace.
  }
}

export function writeViewPreference(
  key: string,
  value: string | number
): void {
  try {
    browserStorage()?.setItem(key, String(value));
  } catch {
    // Preferences remain usable for the current session when storage is blocked.
  }
}

export function readEnumViewPreference<T extends string>(
  key: string,
  allowed: readonly T[],
  fallback: T
): T {
  try {
    const stored = browserStorage()?.getItem(key) ?? null;
    if (stored === null) {
      return fallback;
    }
    if (allowed.includes(stored as T)) {
      return stored as T;
    }
    removeViewPreference(key);
  } catch {
    return fallback;
  }

  return fallback;
}

export function readNumberViewPreference<T extends number>(
  key: string,
  allowed: readonly T[],
  fallback: T
): T {
  try {
    const stored = browserStorage()?.getItem(key) ?? null;
    if (stored === null) {
      return fallback;
    }
    const value = Number(stored);
    if (allowed.includes(value as T)) {
      return value as T;
    }
    removeViewPreference(key);
  } catch {
    return fallback;
  }

  return fallback;
}

export function readPositiveIntegerViewPreference(
  key: string
): number | null {
  try {
    const stored = browserStorage()?.getItem(key) ?? null;
    if (stored === null) {
      return null;
    }
    const value = Number(stored);
    if (Number.isInteger(value) && value > 0) {
      return value;
    }
    removeViewPreference(key);
  } catch {
    return null;
  }

  return null;
}

export function writeNullablePositiveIntegerViewPreference(
  key: string,
  value: number | null
): void {
  if (value === null) {
    removeViewPreference(key);
    return;
  }

  if (Number.isInteger(value) && value > 0) {
    writeViewPreference(key, value);
    return;
  }

  removeViewPreference(key);
}
