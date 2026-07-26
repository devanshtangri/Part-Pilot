// PATCH 160: reusable location catalogue frontend types
export interface LocationOption {
  id: number;
  name: string;
  note: string | null;
  part_count: number;
  active_part_count: number;
  deleted_part_count: number;
  created_at: string;
  updated_at: string;
}

export interface LocationCollection {
  total: number;
  locations: LocationOption[];
}

export interface LocationCreatePayload {
  name: string;
  note: string | null;
}
