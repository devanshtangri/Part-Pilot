export interface SetupStatusResponse {
  setup_complete: boolean;
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

export interface SetupRequest {
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
