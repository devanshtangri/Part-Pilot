// PARTPILOT:PROJECTS_TYPES:V379

export type ProjectStatus =
  | "draft"
  | "reserved"
  | "consumed"
  | "cancelled";

export interface ProjectItem {
  id: number;
  project_id: number;
  part_id: number | null;
  part_number: string | null;
  part_name: string | null;
  part_is_deleted: boolean | null;
  quantity: number;
  unit_price_snapshot: number | string | null;
  currency_snapshot: string | null;
  note: string | null;
  total_quantity: number | null;
  reserved_quantity: number | null;
  available_quantity: number | null;
}

export interface Project {
  id: number;
  name: string;
  description: string | null;
  status: ProjectStatus;
  notes: string | null;
  created_by: string;
  estimated_total_value: number | string | null;
  currency_snapshot: string | null;
  created_at: string;
  updated_at: string;
  item_count: number;
  total_units: number;
  items: ProjectItem[];
}

export interface ProjectCollection {
  total: number;
  limit: number;
  offset: number;
  projects: Project[];
}

export interface ProjectCreateItem {
  part_id: number;
  quantity: number;
  note?: string | null;
}

export interface ProjectCreatePayload {
  name: string;
  description?: string | null;
  notes?: string | null;
  items: ProjectCreateItem[];
}

export type ProjectUpdatePayload = ProjectCreatePayload;
