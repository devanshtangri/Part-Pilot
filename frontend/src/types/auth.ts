export interface SetupStatusResponse {
  setup_complete: boolean;
  account_exists: boolean;
  default_currency: string | null;
  timezone: string | null;
}

export interface AuthUser {
  id: number;
  username: string;
  display_name: string;
  is_active: boolean;
}

export interface AuthTokenResponse {
  token: string;
  username: string;
  display_name: string;
}

export interface SetupPreferencesRequest {
  defaultCurrency: string;
  timezone: string;
}

export interface SetupRequest extends SetupPreferencesRequest {
  displayName: string;
  username: string;
  password: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface ApiAuthTokenResponse {
  token: string;
  username: string;
  display_name: string;
}

export interface DebugResetResponse {
  ok: boolean;
  recreated_part_types: number;
  recreated_template_fields: number;
  recreated_settings: number;
}

