// PARTPILOT:RESERVATIONS_TYPES:V322

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
