// PARTPILOT:SYSTEM_HISTORY_TYPES:V408

export type HistoryKind = "audit" | "stock_movement";
export type HistoryJson = Record<string, unknown> | unknown[] | null;

export interface HistoryEntry {
  key: string;
  kind: HistoryKind;
  event_type: string;
  occurred_at: string;
  summary: string | null;

  entity_type: string | null;
  entity_id: number | null;
  entity_label: string | null;

  actor_type: string | null;
  actor_user_id: number | null;
  actor_display_name: string | null;

  part_id: number | null;
  part_number: string | null;
  part_name: string | null;

  reservation_id: number | null;
  reservation_label: string | null;
  project_id: number | null;
  project_label: string | null;

  movement_type: string | null;
  quantity: number | null;
  quantity_delta: number | null;
  quantity_before: number | null;
  quantity_after: number | null;
  reserved_quantity_before: number | null;
  reserved_quantity_after: number | null;
  available_quantity_before: number | null;
  available_quantity_after: number | null;
  unit_price_snapshot: string | null;
  currency_snapshot: string | null;
  reason: string | null;
  note: string | null;
  source: string | null;

  before_json: HistoryJson;
  after_json: HistoryJson;
  metadata_json: HistoryJson;
}

export interface HistoryCollection {
  total: number;
  limit: number;
  offset: number;
  entries: HistoryEntry[];
}

export interface HistoryFacetValue {
  value: string;
  count: number;
}

export interface HistoryActorOption {
  user_id: number;
  display_name: string;
  count: number;
}

export interface HistoryFilterOptions {
  kinds: HistoryFacetValue[];
  entity_types: HistoryFacetValue[];
  event_types: HistoryFacetValue[];
  actor_types: HistoryFacetValue[];
  movement_types: HistoryFacetValue[];
  sources: HistoryFacetValue[];
  actors: HistoryActorOption[];
  earliest_at: string | null;
  latest_at: string | null;
}

export interface HistoryQueryOptions {
  kind?: HistoryKind;
  entityType?: string;
  eventType?: string;
  actorType?: string;
  actorUserId?: number;
  movementType?: string;
  from?: string;
  to?: string;
  query?: string;
  limit?: number;
  offset?: number;
  signal?: AbortSignal;
}
