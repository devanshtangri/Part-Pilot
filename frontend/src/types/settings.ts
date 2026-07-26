// PATCH 194: typed search settings contracts
export interface SearchSettings {
  show_out_of_stock_section: boolean;
}

export interface SearchSettingsUpdatePayload {
  show_out_of_stock_section: boolean;
}
