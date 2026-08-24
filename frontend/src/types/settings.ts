// PATCH 194: typed search settings contracts
export interface SearchSettings {
  show_out_of_stock_section: boolean;
}

export interface SearchSettingsUpdatePayload {
  show_out_of_stock_section: boolean;
}


// PARTPILOT:CURRENCY_PREFERENCE_TYPES:V675
export interface CurrencySettings {
  currency: string;
}

export interface CurrencySettingsUpdatePayload {
  currency: string;
}


// PARTPILOT:TIMEZONE_PREFERENCE_TYPES:V676
export interface TimezoneSettings {
  timezone: string;
}

export interface TimezoneSettingsUpdatePayload {
  timezone: string;
}


// PARTPILOT:RESERVATION_EXPIRY_SETTINGS_TYPES:V362
export type ReservationExpiryMode = "none" | "default";

export interface ReservationSettings {
  expiry_mode: ReservationExpiryMode;
  default_days: number | null;
}

export interface ReservationSettingsUpdatePayload {
  expiry_mode: ReservationExpiryMode;
  default_days: number | null;
}


// PARTPILOT:APPEARANCE_SETTINGS_TYPES:V412
export type AppearanceTheme = "dark" | "light" | "system";
export type ResolvedAppearanceTheme = "dark" | "light";

export interface AppearanceSettings {
  theme: AppearanceTheme;
  light_theme_available: boolean;
}

export interface AppearanceSettingsUpdatePayload {
  theme: AppearanceTheme;
}


// PARTPILOT:TARGETED_PREFERENCE_RESET_TYPES:V673
export type ReversiblePreferenceResetTarget =
  | "appearance"
  | "inventory"
  | "reservations";

export interface ReversiblePreferenceResetPayload {
  target: ReversiblePreferenceResetTarget;
}

export interface ReversiblePreferenceResetResponse {
  target: ReversiblePreferenceResetTarget;
  appearance: AppearanceSettings | null;
  inventory: SearchSettings | null;
  reservations: ReservationSettings | null;
}


// PARTPILOT:MCP_SETTINGS_TYPES:V627
export interface McpSettings {
  enabled: boolean;
  read_tools_enabled: boolean;
  write_tools_enabled: boolean;
  direct_clients_enabled: boolean;
  direct_no_auth_enabled: boolean;
  direct_no_auth_last_client_ip: string | null;
}

export interface McpSettingsUpdatePayload {
  enabled: boolean;
  read_tools_enabled: boolean;
  write_tools_enabled: boolean;
  direct_clients_enabled: boolean;
  direct_no_auth_enabled: boolean;
  direct_no_auth_confirmation?: string | null;
}


// PARTPILOT:MCP_TOOL_PERMISSIONS_TYPES:V654
export type McpToolCapability = "read" | "write";

export interface McpToolPermission {
  name: string;
  label: string;
  capability: McpToolCapability;
  enabled: boolean;
}

export interface McpToolPermissionsResponse {
  tools: McpToolPermission[];
}

export interface McpToolPermissionsUpdatePayload {
  permissions: Record<string, boolean>;
}

export interface McpClientToolPermission {
  name: string;
  label: string;
  capability: McpToolCapability;
  global_enabled: boolean;
  denied: boolean;
  effective_enabled: boolean;
}

export interface McpClientToolPermissionsResponse {
  denied_tools: string[];
  tools: McpClientToolPermission[];
}

export interface McpClientToolPermissionsUpdatePayload {
  denied_tools: string[];
}


// PARTPILOT:MCP_OAUTH_CLIENT_ADMIN_TYPES:V540
export type McpOAuthClientConnectionStatus = "connected";
export type McpOAuthClientType = "public" | "confidential";
export type McpOAuthTokenEndpointAuthMethod =
  | "none"
  | "client_secret_post"
  | "client_secret_basic";

export interface McpOAuthClientSummary {
  database_id: number;
  client_id: string;
  client_name: string;
  status: McpOAuthClientConnectionStatus;
  client_type: McpOAuthClientType;
  token_endpoint_auth_method: McpOAuthTokenEndpointAuthMethod;
  redirect_origins: string[];
  scopes: string[];
  created_at: string;
  connected_at: string;
  last_used_at: string | null;
  active_token_count: number;
  token_family_count: number;
  total_token_count: number;
  authorization_code_count: number;
  active_consent_count: number;
  denied_tools: string[];
  tool_permissions: McpClientToolPermission[];
}

export interface McpOAuthClientsResponse {
  clients: McpOAuthClientSummary[];
  total: number;
}


// PARTPILOT:MCP_OAUTH_MANUAL_REGISTRATION_TYPES:V561
export type McpOAuthManageableClientStatus =
  | "registered"
  | "connected"
  | "revoked";

export interface McpOAuthManageableClientSummary {
  database_id: number;
  client_id: string;
  client_name: string;
  status: McpOAuthManageableClientStatus;
  client_type: McpOAuthClientType;
  token_endpoint_auth_method: McpOAuthTokenEndpointAuthMethod;
  redirect_origins: string[];
  scopes: string[];
  created_at: string;
  connected_at: string | null;
  last_used_at: string | null;
  active_token_count: number;
  token_family_count: number;
  total_token_count: number;
  authorization_code_count: number;
  active_consent_count: number;
  registered_by_current_user: boolean;
  denied_tools: string[];
  tool_permissions: McpClientToolPermission[];
}

export interface McpOAuthManageableClientsResponse {
  clients: McpOAuthManageableClientSummary[];
  total: number;
}

export interface McpOAuthClientRegistrationPayload {
  client_name: string;
  redirect_uris: string[];
  client_type: McpOAuthClientType;
  token_endpoint_auth_method: McpOAuthTokenEndpointAuthMethod;
}

export interface McpOAuthClientRegistrationResponse {
  database_id: number;
  client_id: string;
  client_name: string;
  redirect_uris: string[];
  client_type: McpOAuthClientType;
  token_endpoint_auth_method: McpOAuthTokenEndpointAuthMethod;
  created_at: string;
  client_secret: string | null;
}


// PARTPILOT:MCP_TRUSTED_NETWORK_TYPES:V510
export type McpDirectAuthMode =
  | "disabled"
  | "bearer_key"
  | "custom_header"
  | "trusted_network";

export type McpDirectSelectionMode = Exclude<
  McpDirectAuthMode,
  "disabled"
>;
export type McpDirectCredentialMode = Exclude<
  McpDirectSelectionMode,
  "trusted_network"
>;

export interface McpDirectAuthStatus {
  mode: McpDirectAuthMode;
  configured: boolean;
  masked_key: string | null;
  custom_header_name: string | null;
  trusted_networks: string[];
  rotated_at: string | null;
  last_used_at: string | null;
}

export interface McpDirectAuthKeyResponse
  extends McpDirectAuthStatus {
  key: string;
}

export interface McpDirectAuthCustomHeaderPayload {
  header_name: string;
}

export interface McpDirectAuthTrustedNetworkPayload {
  networks: string[];
}


// PARTPILOT:MCP_NAMED_DIRECT_CLIENTS_TYPES:V627
export type McpNamedDirectClientMode =
  | "bearer_key"
  | "custom_header"
  | "trusted_network";

export interface McpNamedDirectClient {
  id: number;
  name: string;
  enabled: boolean;
  mode: McpNamedDirectClientMode;
  masked_key: string | null;
  custom_header_name: string | null;
  trusted_networks: string[];
  rotated_at: string | null;
  last_used_at: string | null;
  last_resolved_client_ip: string | null;
  created_at: string;
  updated_at: string;
  denied_tools: string[];
  tool_permissions: McpClientToolPermission[];
}

export interface McpNamedDirectClientsResponse {
  clients: McpNamedDirectClient[];
  total: number;
}

export interface McpNamedDirectClientCreatePayload {
  name: string;
  mode: McpNamedDirectClientMode;
  header_name?: string | null;
  networks?: string[];
}

export interface McpNamedDirectClientCreateResponse extends McpNamedDirectClient {
  key: string | null;
}

export interface McpNamedDirectClientUpdatePayload {
  name?: string;
  enabled?: boolean;
}

export interface McpNamedDirectClientRotatePayload {
  header_name?: string | null;
}

export interface McpNamedDirectClientKeyResponse extends McpNamedDirectClient {
  key: string;
}
