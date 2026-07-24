export interface Manufacturer {
  id: number;
  name: string;
  is_builtin: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ManufacturerCollection {
  total: number;
  builtin_count: number;
  custom_count: number;
  manufacturers: Manufacturer[];
}
