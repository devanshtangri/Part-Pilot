// PATCH 194: typed search settings contracts
export interface SearchSettings {
  show_out_of_stock_section: boolean;
}

export interface SearchSettingsUpdatePayload {
  show_out_of_stock_section: boolean;
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


// PARTPILOT:MCP_SETTINGS_TYPES:V491
export interface McpSettings {
  enabled: boolean;
  read_tools_enabled: boolean;
  write_tools_enabled: boolean;
}

export type McpSettingsUpdatePayload = McpSettings;


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
