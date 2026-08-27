export interface SetupStatusResponse {
  setup_complete: boolean;
  account_exists: boolean;
  default_currency: string | null;
  timezone: string | null;
}

// PARTPILOT:AUTH_ACCOUNT_SECURITY_TYPES:V591
export type BuiltInAvatarId =
  | "initials"
  | "chip"
  | "circuit"
  | "terminal"
  | "storage"
  | "rocket";

export type UserRole =
  | "owner"
  | "administrator"
  | "operator"
  | "viewer";

export interface AuthUser {
  id: number;
  username: string;
  display_name: string;
  avatar_id: BuiltInAvatarId;
  has_custom_avatar: boolean;
  avatar_image_sha256: string | null;
  role: UserRole;
  is_active: boolean;
}

export interface AuthTokenResponse {
  token: string;
  username: string;
  display_name: string;
  role: UserRole;
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
  role: UserRole;
}

export interface DebugResetResponse {
  ok: boolean;
  recreated_part_types: number;
  recreated_template_fields: number;
  recreated_settings: number;
}

export interface ProfileUpdateRequest {
  username: string;
  displayName: string;
  avatarId: BuiltInAvatarId;
}

export interface ProfileResponse extends AuthUser {
  available_avatar_ids: BuiltInAvatarId[];
}

export interface PasswordChangeRequest {
  currentPassword: string;
  newPassword: string;
}

export interface PasswordChangeResponse {
  ok: boolean;
  revoked_other_sessions: number;
}

export interface AuthSession {
  id: number;
  is_current: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  expires_at: string;
  revoked_at: string | null;
  user_agent: string | null;
  ip_address: string | null;
}

export interface SessionListResponse {
  sessions: AuthSession[];
}

export interface SessionRevokeResponse {
  ok: boolean;
  revoked: boolean;
}

export interface OtherSessionsRevokeResponse {
  ok: boolean;
  revoked_sessions: number;
}

// PARTPILOT:USER_MANAGEMENT_FRONTEND_TYPES:V774
export type AssignableUserRole = Exclude<UserRole, "owner">;

export interface ManagedUser {
  id: number;
  username: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ManagedUserListResponse {
  users: ManagedUser[];
  total: number;
}

export interface ManagedUserCreateRequest {
  username: string;
  displayName: string;
  password: string;
  role: AssignableUserRole;
}

export interface ManagedUserAccessUpdateRequest {
  role?: AssignableUserRole;
  isActive?: boolean;
}

export interface ManagedUserActionResponse {
  ok: boolean;
  revoked_sessions: number;
}
