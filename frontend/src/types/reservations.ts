// PARTPILOT:RESERVATIONS_TYPES:V340

export type ReservationStatus =
  | "active"
  | "consumed"
  | "cancelled"
  | "expired";

export interface ReservationItem {
  id: number;
  reservation_id: number;
  part_id: number | null;
  part_number: string | null;
  part_name: string | null;
  quantity: number;
  unit_price_snapshot: number | string | null;
  currency_snapshot: string | null;
  note: string | null;
  total_quantity: number | null;
  reserved_quantity: number | null;
  available_quantity: number | null;
}

export interface Reservation {
  id: number;
  project_id: number | null;
  label: string;
  status: ReservationStatus;
  notes: string | null;
  created_by: string;
  expiry_at: string | null;
  estimated_reserved_value: number | string | null;
  currency_snapshot: string | null;
  created_at: string;
  updated_at: string;
  items: ReservationItem[];
}

export interface ReservationCollection {
  total: number;
  limit: number;
  offset: number;
  reservations: Reservation[];
}

// PARTPILOT:RESERVATION_ACTIVITY_TYPES:V340
export type ReservationActivityKind = "audit" | "stock_movement";

export interface ReservationActivityEntry {
  key: string;
  kind: ReservationActivityKind;
  event_type: string;
  occurred_at: string;
  summary: string | null;
  actor_type: string | null;
  actor_user_id: number | null;
  actor_display_name: string | null;
  part_id: number | null;
  part_number: string | null;
  part_name: string | null;
  movement_type: string | null;
  quantity: number | null;
  quantity_delta: number | null;
  quantity_before: number | null;
  quantity_after: number | null;
  reserved_quantity_before: number | null;
  reserved_quantity_after: number | null;
  available_quantity_before: number | null;
  available_quantity_after: number | null;
  reason: string | null;
  note: string | null;
  source: string | null;
  before_json: Record<string, unknown> | unknown[] | null;
  after_json: Record<string, unknown> | unknown[] | null;
  metadata_json: Record<string, unknown> | unknown[] | null;
}

export interface ReservationActivityCollection {
  reservation_id: number;
  total: number;
  limit: number;
  offset: number;
  activities: ReservationActivityEntry[];
}

export interface ReservationCreateItem {
  part_id: number;
  quantity: number;
  note?: string | null;
}

export interface ReservationCreatePayload {
  label: string;
  notes?: string | null;
  expiry_at?: string | null;
  items: ReservationCreateItem[];
}

// PARTPILOT:RESERVATION_EDIT_TYPES:V347
export type ReservationUpdatePayload = ReservationCreatePayload;

// PARTPILOT:RESERVATION_DELETE_TYPES:V352
export interface ReservationDeletePayload {
  confirmation_label: string;
}

export interface ReservationDeleteResult {
  id: number;
  label: string;
  previous_status: ReservationStatus;
  deleted: boolean;
  removed_item_count: number;
  detached_movement_count: number;
  deleted_at: string;
}

export interface ReservablePart {
  id: number;
  part_number: string;
  name: string;
  total_quantity: number;
  reserved_quantity: number;
  available_quantity: number;
  manufacturer_name?: string | null;
  location_name?: string | null;
}
