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


// PARTPILOT:MCP_SETTINGS_TYPES:V473
export interface McpSettings {
  enabled: boolean;
  read_tools_enabled: boolean;
  write_tools_enabled: boolean;
}

export type McpSettingsUpdatePayload = McpSettings;
