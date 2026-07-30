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
