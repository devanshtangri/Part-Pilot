export interface PartFieldValueCreatePayload {
  field_id: number;
  value_text?: string | null;
  value_number?: string | null;
  value_bool?: boolean | null;
  unit?: string | null;
}

export interface CreatePartPayload {
  part_type_id: number;
  manufacturer_id: number | null;
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

export interface PartCollection {
  total: number;
  limit: number;
  offset: number;
  parts: Part[];
}
