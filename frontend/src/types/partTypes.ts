export interface PartTypeField {
  id: number;
  field_key: string;
  label: string;
  field_type: string;
  is_required: boolean;
  sort_order: number;
  options: unknown[] | Record<string, unknown> | null;
  default_unit: string | null;
  help_text: string | null;
}

export interface PartType {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  is_builtin: boolean;
  is_active: boolean;
  template_version: number;
  field_count: number;
  fields: PartTypeField[];
}

export interface PartTypeCollection {
  total: number;
  builtin_count: number;
  custom_count: number;
  total_fields: number;
  part_types: PartType[];
}
