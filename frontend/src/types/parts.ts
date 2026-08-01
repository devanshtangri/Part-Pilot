export interface PartFieldValueCreatePayload {
  field_id: number;
  value_text?: string | null;
  value_number?: string | null;
  value_bool?: boolean | null;
  unit?: string | null;
}

// PATCH 160: reusable part location assignment types
export interface CreatePartPayload {
  part_type_id: number;
  manufacturer_id: number | null;
  location_id: number | null;
  part_number: string | null;
  name: string | null;
  description: string | null;
  package: string | null;
  notes: string | null;
  total_quantity: number;
  unit_price: string | null;
  purchase_link: string | null;
  low_stock_enabled: boolean;
  low_stock_threshold: number | null;
  field_values: PartFieldValueCreatePayload[];
}

export interface PartFieldValue {
  id: number;
  field_id: number;
  field_key: string;
  label: string;
  field_type: string;
  is_required: boolean;
  value_text: string | null;
  value_number: string | null;
  value_bool: boolean | null;
  unit: string | null;
}

export interface Part {
  id: number;
  part_type_id: number;
  part_type_name: string;
  manufacturer_id: number | null;
  manufacturer_name: string | null;
  location_id: number | null;
  location_name: string | null;
  part_number: string | null;
  name: string | null;
  description: string | null;
  package: string | null;
  notes: string | null;
  total_quantity: number;
  reserved_quantity: number;
  available_quantity: number;
  unit_price: string | null;
  purchase_link: string | null;
  low_stock_enabled: boolean;
  low_stock_threshold: number | null;
  is_low_stock: boolean;
  created_at: string;
  updated_at: string;
  field_values: PartFieldValue[];
}

// PATCH 232: PARTPILOT_STORED_PARTS_SERVER_SEARCH_V233
export type PartStockStatus =
  | "all"
  | "in"
  | "low"
  | "out";

// PATCH 269: PARTPILOT_STORED_PARTS_SORT_TYPES_V270
export type PartSortBy =
  | "default"
  | "part"
  | "type"
  | "manufacturer"
  | "location"
  | "available"
  | "total"
  | "status";

export type PartSortDirection = "asc" | "desc";

export interface PartCollection {
  total: number;
  limit: number;
  offset: number;
  parts: Part[];
}


// PATCH 186: dashboard low-stock summary contract
export interface LowStockSummary {
  total: number;
  low_stock_count: number;
  out_of_stock_count: number;
  limit: number;
  parts: Part[];
}

// PATCH 153: recoverable part deletion and restoration types
export interface DeletedPart extends Part {
  is_deleted: true;
  deleted_at: string;
}

export interface DeletedPartCollection {
  total: number;
  limit: number;
  offset: number;
  parts: DeletedPart[];
}

// PATCH 137: stock quantity adjustment and movement history types
export type QuantityAdjustmentOperation =
  | "add"
  | "remove"
  | "consume"
  | "correction";

export interface QuantityAdjustmentPayload {
  operation: QuantityAdjustmentOperation;
  quantity: number;
  reason: string | null;
  note: string | null;
}

export interface StockMovement {
  id: number;
  part_id: number | null;
  movement_type: string;
  quantity_delta: number;
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
  source: string;
  actor_user_id: number | null;
  created_at: string;
}

export interface QuantityAdjustmentResponse {
  operation: QuantityAdjustmentOperation;
  part: Part;
  movement: StockMovement;
}

export interface PartMovementCollection {
  part_id: number;
  movements: StockMovement[];
}

// PATCH 143: existing-part metadata update payload
export interface UpdatePartPayload {
  part_type_id: number;
  manufacturer_id: number | null;
  location_id: number | null;
  part_number: string | null;
  name: string | null;
  description: string | null;
  package: string | null;
  notes: string | null;
  unit_price: string | null;
  purchase_link: string | null;
  low_stock_enabled: boolean;
  low_stock_threshold: number | null;
  field_values: PartFieldValueCreatePayload[];
}
