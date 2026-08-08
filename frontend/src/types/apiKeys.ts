// PARTPILOT:REST_API_KEY_SETTINGS_TYPES:V618
export type ApiKeyScope =
  | "inventory:read"
  | "inventory:write"
  | "catalogues:read"
  | "catalogues:write"
  | "projects:read"
  | "projects:write"
  | "reservations:read"
  | "reservations:write"
  | "history:read";

export type ApiKeyStatus = "active" | "expired" | "revoked";

export interface ApiKeySummary {
  id: number;
  name: string;
  masked_key: string;
  scopes: ApiKeyScope[];
  status: ApiKeyStatus;
  created_at: string;
  updated_at: string;
  expires_at: string | null;
  rotated_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface ApiKeyListResponse {
  keys: ApiKeySummary[];
  total: number;
  available_scopes: ApiKeyScope[];
}

export interface ApiKeySecretResponse extends ApiKeySummary {
  key: string;
}

export interface ApiKeyMutationPayload {
  name: string;
  scopes: ApiKeyScope[];
  expires_at: string | null;
}
