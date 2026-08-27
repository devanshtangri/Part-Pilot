import {
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import { useLocation } from "react-router-dom";

import {
  APPEARANCE_STORAGE_KEY,
  useAppearance
} from "../appearance/AppearanceContext";
import { useAuth } from "../auth/AuthContext";
import { useLiveSyncRevision } from "../live/LiveSyncContext";
import { ApiKeySettingsSection } from "../components/ApiKeySettingsSection";
import { McpClientPermissionsDialog } from "../components/McpClientPermissionsDialog";
import { McpDirectClientsSection } from "../components/McpDirectClientsSection";
import { SettingsStageIcon } from "../components/SettingsStageIcon";
import { UserManagementSection } from "../components/UserManagementSection";
import { UserAvatar } from "../components/UserAvatar";
import {
  AUTH_TOKEN_STORAGE_KEY,
  changePassword,
  deleteProfileAvatarImage,
  getProfile,
  getSessions,
  resetApplicationDatabase,
  revokeAllOtherSessions,
  revokeSession,
  updateProfile,
  uploadProfileAvatarImage
} from "../services/authClient";
import {
  commitRestoreBackup,
  downloadBackup,
  getManualBackupStatus,
  validateRestoreBackup,
  waitForPartPilotReady
} from "../services/backupsClient";
import {
  getCurrencySettings,
  getMcpOAuthManageableClients,
  getMcpSettings,
  getMcpToolPermissions,
  registerMcpOAuthClient,
  getReservationSettings,
  getSearchSettings,
  getTimezoneSettings,
  resetReversiblePreference,
  revokeMcpOAuthClient,
  updateCurrencySettings,
  updateMcpOAuthClientPermissions,
  updateMcpSettings,
  updateMcpToolPermissions,
  updateReservationSettings,
  updateSearchSettings,
  updateTimezoneSettings
} from "../services/settingsClient";
import type {
  AuthSession,
  BuiltInAvatarId,
  ProfileResponse
} from "../types/auth";
import type {
  ManualBackupStatusResponse,
  RestoreValidationResponse
} from "../types/backups";
import type {
  AppearanceTheme,
  CurrencySettings,
  McpOAuthClientRegistrationResponse,
  McpOAuthClientType,
  McpToolPermissionsResponse,
  McpOAuthManageableClientSummary,
  McpOAuthTokenEndpointAuthMethod,
  McpSettings,
  ReservationExpiryMode,
  ReversiblePreferenceResetTarget,
  ReservationSettings,
  SearchSettings,
  TimezoneSettings
} from "../types/settings";
import { formatWorkspaceDateTime } from "../utils/dateTime";
import { getCurrencyOptions, getTimezoneOptions } from "../utils/setupDefaults";
import "./Settings.css";

const RESET_CONFIRMATION = "RESET PART PILOT";
const RESTORE_CONFIRMATION = "RESTORE";
const MAX_RESTORE_FILE_BYTES = 256 * 1024 * 1024;
const RESERVATION_AUTOSAVE_DELAY_MS = 550;
const SETTINGS_AUTOSAVE_SAVED_VISIBLE_MS = 3500;
const RESERVATION_AUTOSAVE_STARTER_DAYS = 30;
const SETTINGS_SECTION_IDS = [
  "account",
  "users",
  "preferences",
  "api",
  "mcp",
  "data"
] as const;
type SettingsSection = (typeof SETTINGS_SECTION_IDS)[number];
const LEGACY_PREFERENCE_SECTION_IDS = new Set([
  "appearance",
  "inventory",
  "reservations"
]);

function settingsSectionFromHash(): SettingsSection {
  const candidate = window.location.hash.replace("#settings-", "");
  if (LEGACY_PREFERENCE_SECTION_IDS.has(candidate)) {
    return "preferences";
  }
  return SETTINGS_SECTION_IDS.includes(candidate as SettingsSection)
    ? (candidate as SettingsSection)
    : "preferences";
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KiB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
}

function formatUtc(value: string, timezone: string | null): string {
  return formatWorkspaceDateTime(value, timezone);
}

interface AccountProfileDraft {
  username: string;
  displayName: string;
  avatarId: BuiltInAvatarId;
}

const ACCOUNT_AVATAR_OPTIONS: Array<{
  value: BuiltInAvatarId;
  label: string;
}> = [
  { value: "initials", label: "Initials" },
  { value: "chip", label: "Chip" },
  { value: "circuit", label: "Circuit" },
  { value: "terminal", label: "Terminal" },
  { value: "storage", label: "Storage" },
  { value: "rocket", label: "Rocket" }
];

const ACCOUNT_AVATAR_MAX_SOURCE_BYTES = 5 * 1024 * 1024;
const ACCOUNT_AVATAR_MAX_SOURCE_PIXELS = 20_000_000;
const ACCOUNT_AVATAR_PREVIEW_EDGE = 512;
const ACCOUNT_AVATAR_TYPES = new Set([
  "image/png",
  "image/jpeg",
  "image/webp"
]);

async function prepareAccountAvatarImage(file: File): Promise<File> {
  if (!ACCOUNT_AVATAR_TYPES.has(file.type)) {
    throw new Error("Choose a PNG, JPEG, or WebP image.");
  }
  if (file.size > ACCOUNT_AVATAR_MAX_SOURCE_BYTES) {
    throw new Error("Profile image must be 5 MiB or smaller.");
  }

  const sourceUrl = URL.createObjectURL(file);
  try {
    const image = document.createElement("img");
    image.decoding = "async";
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error("Unable to read that image."));
      image.src = sourceUrl;
    });

    if (
      image.naturalWidth < 1 ||
      image.naturalHeight < 1 ||
      image.naturalWidth * image.naturalHeight > ACCOUNT_AVATAR_MAX_SOURCE_PIXELS
    ) {
      throw new Error("Profile image dimensions are unsupported.");
    }

    const crop = Math.min(image.naturalWidth, image.naturalHeight);
    const sourceX = (image.naturalWidth - crop) / 2;
    const sourceY = (image.naturalHeight - crop) / 2;
    const canvas = document.createElement("canvas");
    canvas.width = ACCOUNT_AVATAR_PREVIEW_EDGE;
    canvas.height = ACCOUNT_AVATAR_PREVIEW_EDGE;
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("Unable to prepare the profile image.");
    }
    context.drawImage(
      image,
      sourceX,
      sourceY,
      crop,
      crop,
      0,
      0,
      ACCOUNT_AVATAR_PREVIEW_EDGE,
      ACCOUNT_AVATAR_PREVIEW_EDGE
    );
    const blob = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (value) =>
          value
            ? resolve(value)
            : reject(new Error("Unable to prepare the profile image.")),
        "image/webp",
        0.9
      );
    });
    return new File([blob], "partpilot-avatar.webp", {
      type: "image/webp"
    });
  } finally {
    URL.revokeObjectURL(sourceUrl);
  }
}

function sessionClientLabel(userAgent: string | null): string {
  if (!userAgent) return "Unknown client";
  const browser = /Edg\//.test(userAgent)
    ? "Edge"
    : /Firefox\//.test(userAgent)
      ? "Firefox"
      : /Chrome\//.test(userAgent)
        ? "Chrome"
        : /Safari\//.test(userAgent)
          ? "Safari"
          : "Browser";
  const platform = /Android/.test(userAgent)
    ? "Android"
    : /iPhone|iPad/.test(userAgent)
      ? "iOS"
      : /Windows/.test(userAgent)
        ? "Windows"
        : /Mac OS X/.test(userAgent)
          ? "macOS"
          : /Linux/.test(userAgent)
            ? "Linux"
            : "device";
  return `${browser} on ${platform}`;
}

const APPEARANCE_OPTIONS: Array<{
  value: AppearanceTheme;
  title: string;
  description: string;
}> = [
  {
    value: "dark",
    title: "Dark",
    description: "Low-glare surfaces for workshops and dim rooms."
  },
  {
    value: "light",
    title: "Light",
    description: "Bright neutral surfaces with strong daylight contrast."
  },
  {
    value: "system",
    title: "System",
    description: "Follow the operating system and update automatically."
  }
];

export function Settings() {
  const { token, user, avatarImageUrl, refreshUser, timezone, syncDefaultCurrency, syncTimezone } = useAuth();
  const preferencesLiveRevision = useLiveSyncRevision("preferences");
  const accountLiveRevision = useLiveSyncRevision("account");
  const backupsLiveRevision = useLiveSyncRevision("backups");
  const apiKeysLiveRevision = useLiveSyncRevision("integrations.api_keys");
  const mcpIntegrationLiveRevision = useLiveSyncRevision("integrations.mcp");
  const lastPreferencesLiveRevision = useRef(preferencesLiveRevision);
  const lastAccountLiveRevision = useRef(accountLiveRevision);
  const lastBackupsLiveRevision = useRef(backupsLiveRevision);
  const lastApiKeysLiveRevision = useRef(apiKeysLiveRevision);
  const lastMcpIntegrationLiveRevision = useRef(mcpIntegrationLiveRevision);
  const pendingPreferencesLiveReloadRef = useRef(false);
  const pendingAccountLiveReloadRef = useRef(false);
  const pendingBackupsLiveReloadRef = useRef(false);
  const pendingMcpIntegrationReloadRef = useRef(false);
  const preserveAccountDraftOnLiveReloadRef = useRef(false);
  const preserveReservationDraftOnLiveReloadRef = useRef(false);
  const preserveMcpDraftOnLiveReloadRef = useRef(false);
  const preserveMcpToolPermissionsDraftOnLiveReloadRef = useRef(false);
  const location = useLocation();
  const restoreFileInputRef = useRef<HTMLInputElement | null>(null);
  const currencyOptions = useMemo(() => getCurrencyOptions(), []);
  const timezoneOptions = useMemo(() => getTimezoneOptions(), []);
  const accountAvatarInputRef = useRef<HTMLInputElement | null>(null);
  const [activeSettingsSection, setActiveSettingsSection] =
    useState<SettingsSection>(settingsSectionFromHash);
  const canAdministerWorkspace =
    user?.role === "owner" || user?.role === "administrator";
  const canAdministerUsers = canAdministerWorkspace;
  const isPrimaryOwner = user?.role === "owner";
  const visibleSettingsSections = useMemo<SettingsSection[]>(
    () => canAdministerWorkspace
      ? ["account", "users", "preferences", "api", "mcp", "data"]
      : ["account", "api"],
    [canAdministerWorkspace]
  );

  useEffect(() => {
    if (user && !visibleSettingsSections.includes(activeSettingsSection)) {
      setActiveSettingsSection("account");
      window.history.replaceState(null, "", "#settings-account");
    }
  }, [activeSettingsSection, user, visibleSettingsSections]);

  const {
    theme,
    lightThemeAvailable,
    isLoading: appearanceLoading,
    isSaving: appearanceSaving,
    saved: appearanceSaved,
    error: appearanceError,
    selectTheme,
    reload: reloadAppearance
  } = useAppearance();

  // PARTPILOT:SETTINGS_ACCOUNT_SECURITY_UI:V592
  const [accountProfile, setAccountProfile] =
    useState<ProfileResponse | null>(null);
  const [accountDraft, setAccountDraft] =
    useState<AccountProfileDraft | null>(null);
  const [accountLoading, setAccountLoading] = useState(true);
  const [accountSaving, setAccountSaving] = useState(false);
  const [accountAvatarUploading, setAccountAvatarUploading] = useState(false);
  const [accountAvatarRemoving, setAccountAvatarRemoving] = useState(false);
  const [accountAvatarPreviewUrl, setAccountAvatarPreviewUrl] =
    useState<string | null>(null);
  const [accountError, setAccountError] = useState<string | null>(null);
  const [accountMessage, setAccountMessage] = useState<string | null>(null);
  const [accountReloadVersion, setAccountReloadVersion] = useState(0);
  const [preferenceReloadVersion, setPreferenceReloadVersion] = useState(0);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordMessage, setPasswordMessage] = useState<string | null>(null);
  const [accountSessions, setAccountSessions] = useState<AuthSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [sessionsMessage, setSessionsMessage] = useState<string | null>(null);
  const [sessionRevokingId, setSessionRevokingId] =
    useState<number | null>(null);
  const [sessionsRevokingAll, setSessionsRevokingAll] = useState(false);

  const [searchSettings, setSearchSettings] =
    useState<SearchSettings | null>(null);
  const [searchSettingsLoading, setSearchSettingsLoading] =
    useState(true);
  const [searchSettingsSaving, setSearchSettingsSaving] =
    useState(false);
  const [searchSettingsError, setSearchSettingsError] =
    useState<string | null>(null);
  const [searchSettingsSaved, setSearchSettingsSaved] =
    useState(false);

  // PARTPILOT:CURRENCY_PREFERENCE_UI:V675
  const [currencySettings, setCurrencySettings] =
    useState<CurrencySettings | null>(null);
  const [currencySettingsLoading, setCurrencySettingsLoading] = useState(true);
  const [currencySettingsSaving, setCurrencySettingsSaving] = useState(false);
  const [currencySettingsError, setCurrencySettingsError] =
    useState<string | null>(null);
  const [currencySettingsSaved, setCurrencySettingsSaved] = useState(false);

  // PARTPILOT:TIMEZONE_PREFERENCE_UI:V676
  const [timezoneSettings, setTimezoneSettings] =
    useState<TimezoneSettings | null>(null);
  const [timezoneSettingsLoading, setTimezoneSettingsLoading] = useState(true);
  const [timezoneSettingsSaving, setTimezoneSettingsSaving] = useState(false);
  const [timezoneSettingsError, setTimezoneSettingsError] =
    useState<string | null>(null);
  const [timezoneSettingsSaved, setTimezoneSettingsSaved] = useState(false);

  const [reservationSettings, setReservationSettings] =
    useState<ReservationSettings | null>(null);
  const [reservationDraft, setReservationDraft] =
    useState<ReservationSettings | null>(null);
  const [reservationSettingsLoading, setReservationSettingsLoading] =
    useState(true);
  const [reservationSettingsSaving, setReservationSettingsSaving] =
    useState(false);
  const [reservationSettingsError, setReservationSettingsError] =
    useState<string | null>(null);
  const [reservationSettingsSaved, setReservationSettingsSaved] =
    useState(false);
  const [reservationReloadVersion, setReservationReloadVersion] =
    useState(0);
  const reservationAutosaveTimerRef = useRef<number | null>(null);
  const reservationSaveRequestRef = useRef(0);
  const reservationEditVersionRef = useRef(0);
  const accountLoadedTokenRef = useRef<string | null>(null);
  const searchSettingsLoadedTokenRef = useRef<string | null>(null);
  const currencySettingsLoadedTokenRef = useRef<string | null>(null);
  const timezoneSettingsLoadedTokenRef = useRef<string | null>(null);
  const reservationSettingsLoadedTokenRef = useRef<string | null>(null);
  const backupStatusLoadedTokenRef = useRef<string | null>(null);

  const [mcpSettings, setMcpSettings] =
    useState<McpSettings | null>(null);
  const [mcpDraft, setMcpDraft] =
    useState<McpSettings | null>(null);
  const [mcpSettingsLoading, setMcpSettingsLoading] =
    useState(true);
  const [mcpSettingsSaving, setMcpSettingsSaving] =
    useState(false);
  const [mcpSettingsError, setMcpSettingsError] =
    useState<string | null>(null);
  const [mcpSettingsSaved, setMcpSettingsSaved] =
    useState(false);
  const mcpSettingsSaveRequestRef = useRef(0);
  const mcpSettingsEditVersionRef = useRef(0);
  const mcpSettingsLoadedTokenRef = useRef<string | null>(null);
  const [mcpReloadVersion, setMcpReloadVersion] = useState(0);
  const [apiKeyLiveReloadVersion, setApiKeyLiveReloadVersion] = useState(0);
  const [mcpUrlCopied, setMcpUrlCopied] = useState(false);
  const [mcpCopyError, setMcpCopyError] =
    useState<string | null>(null);
  // PARTPILOT:MCP_TOOL_PERMISSIONS_UI:V654
  const [mcpToolPermissions, setMcpToolPermissions] =
    useState<McpToolPermissionsResponse | null>(null);
  const [mcpToolPermissionsDraft, setMcpToolPermissionsDraft] =
    useState<McpToolPermissionsResponse | null>(null);
  const [mcpToolPermissionsLoading, setMcpToolPermissionsLoading] = useState(true);
  const [mcpToolPermissionsSaving, setMcpToolPermissionsSaving] = useState(false);
  const [mcpToolPermissionsError, setMcpToolPermissionsError] = useState<string | null>(null);
  const [mcpToolPermissionsSaved, setMcpToolPermissionsSaved] = useState(false);
  const mcpToolPermissionSaveRequestRef = useRef(0);
  const mcpToolPermissionEditVersionRef = useRef(0);
  const mcpToolPermissionsLoadedTokenRef = useRef<string | null>(null);
  const [mcpToolPermissionsReloadVersion, setMcpToolPermissionsReloadVersion] = useState(0);
  const [mcpPermissionRefreshVersion, setMcpPermissionRefreshVersion] = useState(0);
  // PARTPILOT:MCP_OAUTH_MANUAL_REGISTRATION_UI:V569
  const [mcpOAuthClients, setMcpOAuthClients] = useState<
    McpOAuthManageableClientSummary[] | null
  >(null);
  const [mcpOAuthClientsLoading, setMcpOAuthClientsLoading] = useState(true);
  const [mcpOAuthClientsError, setMcpOAuthClientsError] = useState<string | null>(null);
  const [mcpOAuthClientsMessage, setMcpOAuthClientsMessage] = useState<string | null>(null);
  const mcpOAuthClientsLoadedTokenRef = useRef<string | null>(null);
  const [mcpOAuthReloadVersion, setMcpOAuthReloadVersion] = useState(0);
  const [mcpOAuthRevokeTarget, setMcpOAuthRevokeTarget] = useState<McpOAuthManageableClientSummary | null>(null);
  const [mcpOAuthRevokingId, setMcpOAuthRevokingId] = useState<number | null>(null);
  const [mcpOAuthRevokeError, setMcpOAuthRevokeError] = useState<string | null>(null);
  const [mcpOAuthRegisterOpen, setMcpOAuthRegisterOpen] = useState(false);
  const [mcpOAuthRegisterAttempted, setMcpOAuthRegisterAttempted] = useState(false);
  const [mcpOAuthClientNameDraft, setMcpOAuthClientNameDraft] = useState("");
  const [mcpOAuthRedirectUrisDraft, setMcpOAuthRedirectUrisDraft] = useState("");
  const [mcpOAuthClientTypeDraft, setMcpOAuthClientTypeDraft] = useState<McpOAuthClientType>("public");
  const [mcpOAuthAuthMethodDraft, setMcpOAuthAuthMethodDraft] = useState<McpOAuthTokenEndpointAuthMethod>("none");
  const [mcpOAuthRegistering, setMcpOAuthRegistering] = useState(false);
  const [mcpOAuthRegisterError, setMcpOAuthRegisterError] = useState<string | null>(null);
  const [mcpOAuthCredential, setMcpOAuthCredential] = useState<McpOAuthClientRegistrationResponse | null>(null);
  const [mcpOAuthSecretVisible, setMcpOAuthSecretVisible] = useState(false);
  const [mcpOAuthCredentialCopied, setMcpOAuthCredentialCopied] = useState<"client_id" | "client_secret" | null>(null);
  const [mcpOAuthPermissionTarget, setMcpOAuthPermissionTarget] = useState<McpOAuthManageableClientSummary | null>(null);
  const [mcpOAuthPermissionSaving, setMcpOAuthPermissionSaving] = useState(false);
  const [mcpOAuthPermissionError, setMcpOAuthPermissionError] = useState<string | null>(null);
  const [mcpNoAuthDialogOpen, setMcpNoAuthDialogOpen] = useState(false);
  const [mcpNoAuthConfirmation, setMcpNoAuthConfirmation] = useState("");

  // PARTPILOT:TARGETED_PREFERENCE_RESET_UI:V673
  const [preferenceResetTarget, setPreferenceResetTarget] =
    useState<ReversiblePreferenceResetTarget | null>(null);
  const [preferenceResetting, setPreferenceResetting] = useState(false);
  const [preferenceResetError, setPreferenceResetError] = useState<string | null>(null);
  const [preferenceResetMessage, setPreferenceResetMessage] = useState<{
    target: ReversiblePreferenceResetTarget;
    text: string;
  } | null>(null);

  const [confirmation, setConfirmation] = useState("");
  const [isResetting, setIsResetting] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);
  const [resetDialogOpen, setResetDialogOpen] = useState(false);

  const [backupDownloading, setBackupDownloading] = useState(false);
  const [backupMessage, setBackupMessage] = useState<string | null>(null);
  const [backupError, setBackupError] = useState<string | null>(null);
  const [backupStatus, setBackupStatus] =
    useState<ManualBackupStatusResponse | null>(null);
  const [backupStatusLoading, setBackupStatusLoading] = useState(true);
  const [backupStatusError, setBackupStatusError] =
    useState<string | null>(null);
  const [backupStatusReloadVersion, setBackupStatusReloadVersion] =
    useState(0);
  const [restoreFile, setRestoreFile] = useState<File | null>(null);
  const [restoreValidation, setRestoreValidation] =
    useState<RestoreValidationResponse | null>(null);
  const [restoreDialogOpen, setRestoreDialogOpen] = useState(false);
  const [restoreConfirmation, setRestoreConfirmation] = useState("");
  const [restoreValidating, setRestoreValidating] = useState(false);
  const [restoreCommitting, setRestoreCommitting] = useState(false);
  const [restoreRestarting, setRestoreRestarting] = useState(false);
  const [restoreError, setRestoreError] = useState<string | null>(null);

  const accountProfileChanged = Boolean(
    accountProfile
      && accountDraft
      && (
        accountDraft.username !== accountProfile.username
        || accountDraft.displayName !== accountProfile.display_name
        || accountDraft.avatarId !== accountProfile.avatar_id
      )
  );
  const reservationDraftChanged = Boolean(
    reservationSettings
      && reservationDraft
      && (
        reservationDraft.expiry_mode !== reservationSettings.expiry_mode
        || !Object.is(
          reservationDraft.default_days,
          reservationSettings.default_days
        )
      )
  );
  const accountMutationInProgress =
    accountSaving
    || accountAvatarUploading
    || accountAvatarRemoving
    || passwordSaving
    || sessionRevokingId !== null
    || sessionsRevokingAll;
  const preferenceMutationInProgress =
    appearanceSaving || currencySettingsSaving || timezoneSettingsSaving || searchSettingsSaving || reservationSettingsSaving;
  const canConfirmPreferenceReset =
    preferenceResetTarget !== null &&
    !preferenceResetting &&
    !preferenceMutationInProgress;

  const canReset =
    confirmation === RESET_CONFIRMATION && !isResetting;
  const canCommitRestore =
    restoreConfirmation === RESTORE_CONFIRMATION &&
    Boolean(restoreValidation) &&
    !restoreCommitting &&
    !restoreRestarting;

  const reservationDaysError =
    reservationDraft?.expiry_mode === "default" &&
    (!Number.isInteger(reservationDraft.default_days) ||
      Number(reservationDraft.default_days) < 1 ||
      Number(reservationDraft.default_days) > 3650)
      ? "Enter a whole number from 1 to 3650 days."
      : null;

  const mcpSettingsChanged = Boolean(
    mcpSettings &&
      mcpDraft &&
      (mcpSettings.enabled !== mcpDraft.enabled ||
        mcpSettings.read_tools_enabled !== mcpDraft.read_tools_enabled ||
        mcpSettings.write_tools_enabled !== mcpDraft.write_tools_enabled ||
        mcpSettings.direct_clients_enabled !== mcpDraft.direct_clients_enabled ||
        mcpSettings.direct_no_auth_enabled !== mcpDraft.direct_no_auth_enabled)
  );
  const mcpToolPermissionsChanged = Boolean(
    mcpToolPermissions &&
      mcpToolPermissionsDraft &&
      mcpToolPermissions.tools.some((tool) =>
        mcpToolPermissionsDraft.tools.find((draft) => draft.name === tool.name)?.enabled !== tool.enabled
      )
  );
  const mcpMutationInProgress =
    mcpSettingsSaving
    || mcpToolPermissionsSaving
    || mcpOAuthRegistering
    || mcpOAuthRevokingId !== null
    || mcpOAuthPermissionSaving;
  const mcpNoAuthConfirmationReady =
    mcpNoAuthConfirmation === "ALLOW NO AUTH";
  const mcpServerUrl = `${window.location.origin}/mcp`;
  const mcpUsesPublicHttps = window.location.protocol === "https:";
  const mcpOAuthRedirectUris = mcpOAuthRedirectUrisDraft.split(/\r?\n/).map((value) => value.trim()).filter(Boolean);
  const mcpOAuthClientNameError = mcpOAuthClientNameDraft.trim().length === 0 ? "Enter a client name." : null;
  const mcpOAuthRedirectUrisError = mcpOAuthRedirectUris.length === 0 ? "Enter at least one redirect URI." : mcpOAuthRedirectUris.length > 20 ? "Use no more than 20 redirect URIs." : null;
  const mcpOAuthRegistrationError = mcpOAuthClientNameError ?? mcpOAuthRedirectUrisError;
  const mcpOAuthDisplayedRegistrationError = mcpOAuthRegisterError ?? (mcpOAuthRegisterAttempted ? mcpOAuthRegistrationError : null);
  const mcpOAuthVisibleClients = mcpOAuthClients?.filter(
    (client) => client.status !== "revoked"
  ) ?? null;
  const activeAccountSessions = accountSessions.filter(
    (session) => session.is_active
  );
  const otherActiveSessionCount = activeAccountSessions.filter(
    (session) => !session.is_current
  ).length;
  const availableAccountAvatars = ACCOUNT_AVATAR_OPTIONS.filter(
    (option) =>
      accountProfile?.available_avatar_ids.includes(option.value) ?? true
  );

  useEffect(() => {
    setActiveSettingsSection(settingsSectionFromHash());
  }, [location.hash]);

  // PARTPILOT:SETTINGS_ACCOUNT_PREFERENCES_LIVE_SYNC:V705
  useEffect(() => {
    if (
      preferencesLiveRevision
      === lastPreferencesLiveRevision.current
    ) {
      return;
    }
    lastPreferencesLiveRevision.current = preferencesLiveRevision;
    pendingPreferencesLiveReloadRef.current = true;
  }, [preferencesLiveRevision]);

  useEffect(() => {
    if (
      !pendingPreferencesLiveReloadRef.current
      || preferenceMutationInProgress
      || preferenceResetting
      || reservationAutosaveTimerRef.current !== null
    ) {
      return;
    }
    preserveReservationDraftOnLiveReloadRef.current =
      reservationDraftChanged;
    pendingPreferencesLiveReloadRef.current = false;
    setPreferenceReloadVersion((value) => value + 1);
    setReservationReloadVersion((value) => value + 1);
  }, [
    preferenceMutationInProgress,
    preferenceResetting,
    preferencesLiveRevision,
    reservationDraftChanged
  ]);

  useEffect(() => {
    if (accountLiveRevision === lastAccountLiveRevision.current) {
      return;
    }
    lastAccountLiveRevision.current = accountLiveRevision;
    pendingAccountLiveReloadRef.current = true;
  }, [accountLiveRevision]);

  useEffect(() => {
    if (
      !pendingAccountLiveReloadRef.current
      || accountMutationInProgress
    ) {
      return;
    }
    preserveAccountDraftOnLiveReloadRef.current =
      accountProfileChanged;
    pendingAccountLiveReloadRef.current = false;
    setAccountReloadVersion((value) => value + 1);
  }, [
    accountLiveRevision,
    accountMutationInProgress,
    accountProfileChanged
  ]);

  useEffect(() => {
    if (backupsLiveRevision === lastBackupsLiveRevision.current) {
      return;
    }
    lastBackupsLiveRevision.current = backupsLiveRevision;
    pendingBackupsLiveReloadRef.current = true;
  }, [backupsLiveRevision]);

  useEffect(() => {
    if (
      !pendingBackupsLiveReloadRef.current
      || backupDownloading
      || restoreCommitting
      || restoreRestarting
    ) {
      return;
    }
    pendingBackupsLiveReloadRef.current = false;
    setBackupStatusReloadVersion((value) => value + 1);
  }, [
    backupDownloading,
    backupsLiveRevision,
    restoreCommitting,
    restoreRestarting
  ]);

  // PARTPILOT:API_KEY_MCP_INTEGRATION_LIVE_SYNC:V708
  useEffect(() => {
    if (apiKeysLiveRevision === lastApiKeysLiveRevision.current) return;
    lastApiKeysLiveRevision.current = apiKeysLiveRevision;
    setApiKeyLiveReloadVersion((value) => value + 1);
  }, [apiKeysLiveRevision]);

  useEffect(() => {
    if (mcpIntegrationLiveRevision === lastMcpIntegrationLiveRevision.current) return;
    lastMcpIntegrationLiveRevision.current = mcpIntegrationLiveRevision;
    pendingMcpIntegrationReloadRef.current = true;
  }, [mcpIntegrationLiveRevision]);

  useEffect(() => {
    if (!pendingMcpIntegrationReloadRef.current || mcpMutationInProgress) return;
    preserveMcpDraftOnLiveReloadRef.current = mcpSettingsChanged;
    preserveMcpToolPermissionsDraftOnLiveReloadRef.current =
      mcpToolPermissionsChanged;
    pendingMcpIntegrationReloadRef.current = false;
    setMcpReloadVersion((value) => value + 1);
    setMcpToolPermissionsReloadVersion((value) => value + 1);
    setMcpOAuthReloadVersion((value) => value + 1);
    setMcpPermissionRefreshVersion((value) => value + 1);
  }, [
    mcpIntegrationLiveRevision,
    mcpMutationInProgress,
    mcpSettingsChanged,
    mcpToolPermissionsChanged
  ]);

  useEffect(() => {
    return () => {
      if (reservationAutosaveTimerRef.current !== null) {
        window.clearTimeout(reservationAutosaveTimerRef.current);
      }
    };
  }, []);

  // PARTPILOT:CONSISTENT_AUTOSAVE_FEEDBACK_DURATION:V751
  useEffect(() => {
    if (!searchSettingsSaved) return;
    const timeoutId = window.setTimeout(
      () => setSearchSettingsSaved(false),
      SETTINGS_AUTOSAVE_SAVED_VISIBLE_MS
    );
    return () => window.clearTimeout(timeoutId);
  }, [searchSettingsSaved]);

  useEffect(() => {
    if (!currencySettingsSaved) return;
    const timeoutId = window.setTimeout(
      () => setCurrencySettingsSaved(false),
      SETTINGS_AUTOSAVE_SAVED_VISIBLE_MS
    );
    return () => window.clearTimeout(timeoutId);
  }, [currencySettingsSaved]);

  useEffect(() => {
    if (!timezoneSettingsSaved) return;
    const timeoutId = window.setTimeout(
      () => setTimezoneSettingsSaved(false),
      SETTINGS_AUTOSAVE_SAVED_VISIBLE_MS
    );
    return () => window.clearTimeout(timeoutId);
  }, [timezoneSettingsSaved]);

  useEffect(() => {
    if (!reservationSettingsSaved) return;
    const timeoutId = window.setTimeout(
      () => setReservationSettingsSaved(false),
      SETTINGS_AUTOSAVE_SAVED_VISIBLE_MS
    );
    return () => window.clearTimeout(timeoutId);
  }, [reservationSettingsSaved]);

  useEffect(() => {
    if (!mcpSettingsSaved) return;
    const timeoutId = window.setTimeout(
      () => setMcpSettingsSaved(false),
      SETTINGS_AUTOSAVE_SAVED_VISIBLE_MS
    );
    return () => window.clearTimeout(timeoutId);
  }, [mcpSettingsSaved]);

  useEffect(() => {
    if (!mcpToolPermissionsSaved) return;
    const timeoutId = window.setTimeout(
      () => setMcpToolPermissionsSaved(false),
      SETTINGS_AUTOSAVE_SAVED_VISIBLE_MS
    );
    return () => window.clearTimeout(timeoutId);
  }, [mcpToolPermissionsSaved]);

  useEffect(() => {
    return () => {
      if (accountAvatarPreviewUrl) {
        URL.revokeObjectURL(accountAvatarPreviewUrl);
      }
    };
  }, [accountAvatarPreviewUrl]);

  useEffect(() => {
    if (!token) {
      accountLoadedTokenRef.current = null;
      setAccountProfile(null);
      setAccountDraft(null);
      setAccountSessions([]);
      setAccountLoading(false);
      setSessionsLoading(false);
      setAccountError("Your session is unavailable. Sign in again.");
      setSessionsError("Your session is unavailable. Sign in again.");
      return;
    }

    let cancelled = false;
    const hasCachedAccount = accountLoadedTokenRef.current === token;
    if (!hasCachedAccount) {
      setAccountProfile(null);
      setAccountDraft(null);
      setAccountSessions([]);
    }
    setAccountLoading(!hasCachedAccount);
    setSessionsLoading(!hasCachedAccount);
    setAccountError(null);
    setSessionsError(null);

    Promise.all([getProfile(token), getSessions(token)])
      .then(([profile, sessions]) => {
        if (cancelled) return;
        accountLoadedTokenRef.current = token;
        setAccountProfile(profile);
        if (!preserveAccountDraftOnLiveReloadRef.current) {
          setAccountDraft({
            username: profile.username,
            displayName: profile.display_name,
            avatarId: profile.avatar_id
          });
        }
        preserveAccountDraftOnLiveReloadRef.current = false;
        setAccountSessions(sessions.sessions);
      })
      .catch((caught) => {
        if (cancelled) return;
        preserveAccountDraftOnLiveReloadRef.current = false;
        const message =
          caught instanceof Error
            ? caught.message
            : "Unable to load account security settings";
        setAccountError(message);
        setSessionsError(message);
      })
      .finally(() => {
        if (!cancelled) {
          setAccountLoading(false);
          setSessionsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [accountReloadVersion, token]);

  useEffect(() => {
    if (!token || !canAdministerWorkspace) {
      searchSettingsLoadedTokenRef.current = null;
      setSearchSettings(null);
      setSearchSettingsLoading(false);
      setSearchSettingsError(
        "Your session is unavailable. Sign in again."
      );
      return;
    }

    let cancelled = false;
    const hasCachedSearchSettings = searchSettingsLoadedTokenRef.current === token;
    setSearchSettingsLoading(!hasCachedSearchSettings);
    setSearchSettingsError(null);

    getSearchSettings(token)
      .then((result) => {
        if (!cancelled) {
          searchSettingsLoadedTokenRef.current = token;
          setSearchSettings(result);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          if (!hasCachedSearchSettings) setSearchSettings(null);
          setSearchSettingsError(
            caught instanceof Error
              ? caught.message
              : "Unable to load search settings"
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setSearchSettingsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [canAdministerWorkspace, preferenceReloadVersion, token]);

  // PARTPILOT:CURRENCY_PREFERENCE_UI:V675
  useEffect(() => {
    if (!token || !canAdministerWorkspace) {
      currencySettingsLoadedTokenRef.current = null;
      setCurrencySettings(null);
      setCurrencySettingsLoading(false);
      setCurrencySettingsError("Your session is unavailable. Sign in again.");
      return;
    }

    let cancelled = false;
    const hasCachedCurrency = currencySettingsLoadedTokenRef.current === token;
    setCurrencySettingsLoading(!hasCachedCurrency);
    setCurrencySettingsError(null);

    getCurrencySettings(token)
      .then((result) => {
        if (!cancelled) {
          currencySettingsLoadedTokenRef.current = token;
          setCurrencySettings(result);
          syncDefaultCurrency(result.currency);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          if (!hasCachedCurrency) setCurrencySettings(null);
          setCurrencySettingsError(
            caught instanceof Error ? caught.message : "Unable to load currency preference"
          );
        }
      })
      .finally(() => {
        if (!cancelled) setCurrencySettingsLoading(false);
      });

    return () => { cancelled = true; };
  }, [canAdministerWorkspace, preferenceReloadVersion, syncDefaultCurrency, token]);

  // PARTPILOT:TIMEZONE_PREFERENCE_UI:V676
  useEffect(() => {
    if (!token || !canAdministerWorkspace) {
      timezoneSettingsLoadedTokenRef.current = null;
      setTimezoneSettings(null);
      setTimezoneSettingsLoading(false);
      setTimezoneSettingsError("Your session is unavailable. Sign in again.");
      return;
    }

    let cancelled = false;
    const hasCachedTimezone = timezoneSettingsLoadedTokenRef.current === token;
    setTimezoneSettingsLoading(!hasCachedTimezone);
    setTimezoneSettingsError(null);

    getTimezoneSettings(token)
      .then((result) => {
        if (!cancelled) {
          timezoneSettingsLoadedTokenRef.current = token;
          setTimezoneSettings(result);
          syncTimezone(result.timezone);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          if (!hasCachedTimezone) setTimezoneSettings(null);
          setTimezoneSettingsError(
            caught instanceof Error ? caught.message : "Unable to load timezone preference"
          );
        }
      })
      .finally(() => {
        if (!cancelled) setTimezoneSettingsLoading(false);
      });

    return () => { cancelled = true; };
  }, [canAdministerWorkspace, preferenceReloadVersion, syncTimezone, token]);

  useEffect(() => {
    if (!token || !canAdministerWorkspace) {
      reservationSettingsLoadedTokenRef.current = null;
      setReservationSettings(null);
      setReservationDraft(null);
      setReservationSettingsLoading(false);
      setReservationSettingsError(
        "Your session is unavailable. Sign in again."
      );
      return;
    }

    let cancelled = false;
    const hasCachedReservationSettings =
      reservationSettingsLoadedTokenRef.current === token;
    setReservationSettingsLoading(!hasCachedReservationSettings);
    setReservationSettingsError(null);

    getReservationSettings(token)
      .then((result) => {
        if (!cancelled) {
          reservationSettingsLoadedTokenRef.current = token;
          setReservationSettings(result);
          if (!preserveReservationDraftOnLiveReloadRef.current) {
            setReservationDraft(result);
          }
          preserveReservationDraftOnLiveReloadRef.current = false;
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          preserveReservationDraftOnLiveReloadRef.current = false;
          if (!hasCachedReservationSettings) {
            setReservationSettings(null);
            setReservationDraft(null);
          }
          setReservationSettingsError(
            caught instanceof Error
              ? caught.message
              : "Unable to load reservation defaults"
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setReservationSettingsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [canAdministerWorkspace, reservationReloadVersion, token]);

  // PARTPILOT:MCP_SETTINGS_UI:V473
  useEffect(() => {
    if (!token || !canAdministerWorkspace) {
      mcpSettingsLoadedTokenRef.current = null;
      setMcpSettings(null);
      setMcpDraft(null);
      setMcpSettingsLoading(false);
      setMcpSettingsError(
        "Your session is unavailable. Sign in again."
      );
      return;
    }

    let cancelled = false;
    const hasCachedMcpSettings =
      mcpSettingsLoadedTokenRef.current === token && mcpDraft !== null;
    setMcpSettingsLoading(!hasCachedMcpSettings);
    setMcpSettingsError(null);

    getMcpSettings(token)
      .then((result) => {
        if (!cancelled) {
          setMcpSettings(result);
          mcpSettingsLoadedTokenRef.current = token;
          if (!preserveMcpDraftOnLiveReloadRef.current) setMcpDraft(result);
          preserveMcpDraftOnLiveReloadRef.current = false;
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          if (!hasCachedMcpSettings) {
            setMcpSettings(null);
            if (!preserveMcpDraftOnLiveReloadRef.current) setMcpDraft(null);
          }
          preserveMcpDraftOnLiveReloadRef.current = false;
          setMcpSettingsError(
            caught instanceof Error
              ? caught.message
              : "Unable to load MCP settings"
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setMcpSettingsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [canAdministerWorkspace, mcpReloadVersion, token]);

  // PARTPILOT:MCP_TOOL_PERMISSIONS_UI:V654
  useEffect(() => {
    if (!token || !canAdministerWorkspace) {
      mcpToolPermissionsLoadedTokenRef.current = null;
      setMcpToolPermissions(null);
      setMcpToolPermissionsDraft(null);
      setMcpToolPermissionsLoading(false);
      setMcpToolPermissionsError("Your session is unavailable. Sign in again.");
      return;
    }
    let cancelled = false;
    const hasCachedMcpToolPermissions =
      mcpToolPermissionsLoadedTokenRef.current === token && mcpToolPermissionsDraft !== null;
    setMcpToolPermissionsLoading(!hasCachedMcpToolPermissions);
    setMcpToolPermissionsError(null);
    getMcpToolPermissions(token)
      .then((result) => {
        if (!cancelled) {
          setMcpToolPermissions(result);
          mcpToolPermissionsLoadedTokenRef.current = token;
          if (!preserveMcpToolPermissionsDraftOnLiveReloadRef.current) {
            setMcpToolPermissionsDraft(result);
          }
          preserveMcpToolPermissionsDraftOnLiveReloadRef.current = false;
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          if (!hasCachedMcpToolPermissions) {
            setMcpToolPermissions(null);
            if (!preserveMcpToolPermissionsDraftOnLiveReloadRef.current) {
              setMcpToolPermissionsDraft(null);
            }
          }
          preserveMcpToolPermissionsDraftOnLiveReloadRef.current = false;
          setMcpToolPermissionsError(
            caught instanceof Error ? caught.message : "Unable to load MCP tool permissions"
          );
        }
      })
      .finally(() => {
        if (!cancelled) setMcpToolPermissionsLoading(false);
      });
    return () => { cancelled = true; };
  }, [canAdministerWorkspace, mcpToolPermissionsReloadVersion, token]);

  // PARTPILOT:MCP_OAUTH_MANUAL_REGISTRATION_UI:V569
  useEffect(() => {
    if (!token || !canAdministerWorkspace) {
      mcpOAuthClientsLoadedTokenRef.current = null;
      setMcpOAuthClients(null);
      setMcpOAuthClientsLoading(false);
      setMcpOAuthClientsError("Your session is unavailable. Sign in again.");
      setMcpOAuthCredential(null);
      return;
    }
    let cancelled = false;
    const hasCachedMcpOAuthClients =
      mcpOAuthClientsLoadedTokenRef.current === token && mcpOAuthClients !== null;
    setMcpOAuthClientsLoading(!hasCachedMcpOAuthClients);
    setMcpOAuthClientsError(null);
    getMcpOAuthManageableClients(token)
      .then((result) => {
        if (!cancelled) {
          setMcpOAuthClients(result.clients);
          mcpOAuthClientsLoadedTokenRef.current = token;
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          if (!hasCachedMcpOAuthClients) setMcpOAuthClients(null);
          setMcpOAuthClientsError(caught instanceof Error ? caught.message : "Unable to load OAuth clients");
        }
      })
      .finally(() => { if (!cancelled) setMcpOAuthClientsLoading(false); });
    return () => { cancelled = true; };
  }, [canAdministerWorkspace, mcpOAuthReloadVersion, token]);

  // PARTPILOT:MCP_TRUSTED_NETWORK_UI:V510

  // PARTPILOT:SETTINGS_MANUAL_BACKUP_STATUS_UI:V454
  useEffect(() => {
    if (!token || !canAdministerWorkspace) {
      backupStatusLoadedTokenRef.current = null;
      setBackupStatus(null);
      setBackupStatusLoading(false);
      setBackupStatusError(
        "Your session is unavailable. Sign in again."
      );
      return;
    }

    let cancelled = false;
    const hasCachedBackupStatus = backupStatusLoadedTokenRef.current === token;
    setBackupStatusLoading(!hasCachedBackupStatus);
    setBackupStatusError(null);

    getManualBackupStatus(token)
      .then((result) => {
        if (!cancelled) {
          backupStatusLoadedTokenRef.current = token;
          setBackupStatus(result);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          if (!hasCachedBackupStatus) setBackupStatus(null);
          setBackupStatusError(
            caught instanceof Error
              ? caught.message
              : "Unable to load backup history"
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setBackupStatusLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [canAdministerWorkspace, backupStatusReloadVersion, token]);

  useEffect(() => {
    if (!preferenceResetTarget) return;
    const previousOverflow = document.body.style.overflow;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !preferenceResetting) {
        setPreferenceResetTarget(null);
        setPreferenceResetError(null);
      }
    }
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [preferenceResetTarget, preferenceResetting]);

  useEffect(() => {
    if (!resetDialogOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !isResetting) {
        closeDatabaseResetDialog();
      }
    }

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isResetting, resetDialogOpen]);

  useEffect(() => {
    if (!restoreDialogOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;

    function handleKeyDown(event: KeyboardEvent) {
      if (
        event.key === "Escape" &&
        !restoreCommitting &&
        !restoreRestarting
      ) {
        closeRestoreDialog();
      }
    }

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [restoreCommitting, restoreDialogOpen, restoreRestarting]);

  useEffect(() => {
    if (!mcpOAuthRevokeTarget) {
      return;
    }

    const previousOverflow = document.body.style.overflow;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && mcpOAuthRevokingId === null) {
        closeMcpOAuthRevokeDialog();
      }
    }

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [mcpOAuthRevokeTarget, mcpOAuthRevokingId]);

  useEffect(() => {
    if (!mcpOAuthCredential) return;
    const previousOverflow = document.body.style.overflow;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") closeMcpOAuthCredentialDialog();
    }
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [mcpOAuthCredential]);

  function clearReservationAutosaveTimer(): void {
    if (reservationAutosaveTimerRef.current !== null) {
      window.clearTimeout(reservationAutosaveTimerRef.current);
      reservationAutosaveTimerRef.current = null;
    }
  }

  async function persistReservationDefaults(
    next: ReservationSettings,
    editVersion: number
  ): Promise<void> {
    if (!token || !reservationSettings || reservationSettingsSaving) {
      return;
    }

    const previousConfirmed = reservationSettings;
    const requestId = reservationSaveRequestRef.current + 1;
    reservationSaveRequestRef.current = requestId;
    setReservationSettingsSaving(true);
    setReservationSettingsError(null);
    setReservationSettingsSaved(false);

    try {
      const saved = await updateReservationSettings(token, next);
      if (reservationSaveRequestRef.current !== requestId) {
        return;
      }
      setReservationSettings(saved);
      if (reservationEditVersionRef.current === editVersion) {
        setReservationDraft(saved);
      }
      setReservationSettingsSaved(true);
    } catch (caught) {
      if (reservationSaveRequestRef.current !== requestId) {
        return;
      }
      reservationEditVersionRef.current += 1;
      clearReservationAutosaveTimer();
      setReservationDraft(previousConfirmed);
      setReservationSettingsError(
        caught instanceof Error
          ? caught.message
          : "Unable to save reservation defaults"
      );
    } finally {
      if (reservationSaveRequestRef.current === requestId) {
        setReservationSettingsSaving(false);
      }
    }
  }

  function chooseReservationExpiryMode(
    expiryMode: ReservationExpiryMode
  ): void {
    if (!reservationDraft || !reservationSettings || reservationSettingsSaving) {
      return;
    }
    if (reservationDraft.expiry_mode === expiryMode) {
      return;
    }

    clearReservationAutosaveTimer();
    const next: ReservationSettings = {
      expiry_mode: expiryMode,
      default_days:
        expiryMode === "none"
          ? null
          : reservationDraft.default_days ??
            reservationSettings.default_days ??
            RESERVATION_AUTOSAVE_STARTER_DAYS
    };
    const editVersion = reservationEditVersionRef.current + 1;
    reservationEditVersionRef.current = editVersion;
    setReservationDraft(next);
    setReservationSettingsError(null);
    setReservationSettingsSaved(false);
    void persistReservationDefaults(next, editVersion);
  }

  function updateReservationDefaultDays(rawValue: string): void {
    if (!reservationDraft || reservationSettingsSaving) {
      return;
    }

    clearReservationAutosaveTimer();
    const parsedValue = rawValue === "" ? null : Number(rawValue);
    const next: ReservationSettings = {
      expiry_mode: "default",
      default_days: parsedValue
    };
    const editVersion = reservationEditVersionRef.current + 1;
    reservationEditVersionRef.current = editVersion;
    setReservationDraft(next);
    setReservationSettingsError(null);
    setReservationSettingsSaved(false);

    if (
      !Number.isInteger(parsedValue) ||
      Number(parsedValue) < 1 ||
      Number(parsedValue) > 3650
    ) {
      return;
    }

    reservationAutosaveTimerRef.current = window.setTimeout(() => {
      reservationAutosaveTimerRef.current = null;
      void persistReservationDefaults(next, editVersion);
    }, RESERVATION_AUTOSAVE_DELAY_MS);
  }

  // PARTPILOT:MCP_AUTOSAVE:V715
  async function persistMcpAccess(
    next: McpSettings,
    editVersion: number,
    noAuthConfirmation: string | null = null
  ): Promise<void> {
    if (!token || !mcpSettings || mcpSettingsSaving) return;
    const previousConfirmed = mcpSettings;
    const requestId = mcpSettingsSaveRequestRef.current + 1;
    mcpSettingsSaveRequestRef.current = requestId;
    setMcpSettingsSaving(true);
    setMcpSettingsError(null);
    setMcpSettingsSaved(false);
    try {
      const saved = await updateMcpSettings(token, {
        enabled: next.enabled,
        read_tools_enabled: next.read_tools_enabled,
        write_tools_enabled: next.write_tools_enabled,
        direct_clients_enabled: next.direct_clients_enabled,
        direct_no_auth_enabled: next.direct_no_auth_enabled,
        direct_no_auth_confirmation: noAuthConfirmation
      });
      if (mcpSettingsSaveRequestRef.current !== requestId) return;
      setMcpSettings(saved);
      if (mcpSettingsEditVersionRef.current === editVersion) setMcpDraft(saved);
      setMcpSettingsSaved(true);
    } catch (caught) {
      if (mcpSettingsSaveRequestRef.current !== requestId) return;
      mcpSettingsEditVersionRef.current += 1;
      setMcpDraft(previousConfirmed);
      setMcpSettingsError(
        caught instanceof Error ? caught.message : "Unable to save MCP settings"
      );
    } finally {
      if (mcpSettingsSaveRequestRef.current === requestId) setMcpSettingsSaving(false);
    }
  }

  function updateMcpDraft(
    field:
      | "enabled"
      | "read_tools_enabled"
      | "write_tools_enabled"
      | "direct_clients_enabled",
    value: boolean
  ): void {
    if (!mcpDraft || !mcpSettings || mcpSettingsSaving) return;
    const next = { ...mcpDraft, [field]: value };
    if (field === "enabled" && !value) next.direct_no_auth_enabled = false;
    if (field === "direct_clients_enabled" && !value) {
      next.direct_no_auth_enabled = false;
      setMcpNoAuthConfirmation("");
      setMcpNoAuthDialogOpen(false);
    }
    const editVersion = mcpSettingsEditVersionRef.current + 1;
    mcpSettingsEditVersionRef.current = editVersion;
    setMcpDraft(next);
    setMcpSettingsError(null);
    setMcpSettingsSaved(false);
    void persistMcpAccess(next, editVersion);
  }

  function requestMcpNoAuth(nextValue: boolean): void {
    if (!mcpDraft || !mcpSettings || mcpSettingsSaving) return;
    setMcpSettingsError(null);
    setMcpSettingsSaved(false);
    if (!nextValue) {
      const next = { ...mcpDraft, direct_no_auth_enabled: false };
      const editVersion = mcpSettingsEditVersionRef.current + 1;
      mcpSettingsEditVersionRef.current = editVersion;
      setMcpDraft(next);
      setMcpNoAuthConfirmation("");
      setMcpNoAuthDialogOpen(false);
      void persistMcpAccess(next, editVersion);
      return;
    }
    if (!mcpDraft.enabled || !mcpDraft.direct_clients_enabled) return;
    setMcpNoAuthConfirmation("");
    setMcpNoAuthDialogOpen(true);
  }

  function confirmMcpNoAuth(): void {
    if (
      !mcpDraft ||
      !mcpSettings ||
      !mcpNoAuthConfirmationReady ||
      mcpSettingsSaving
    ) return;
    const next = { ...mcpDraft, direct_no_auth_enabled: true };
    const confirmation = mcpNoAuthConfirmation;
    const editVersion = mcpSettingsEditVersionRef.current + 1;
    mcpSettingsEditVersionRef.current = editVersion;
    setMcpDraft(next);
    setMcpNoAuthDialogOpen(false);
    setMcpNoAuthConfirmation("");
    setMcpSettingsError(null);
    setMcpSettingsSaved(false);
    void persistMcpAccess(next, editVersion, confirmation);
  }

  async function persistMcpToolPermission(
    name: string,
    enabled: boolean,
    nextDraft: McpToolPermissionsResponse,
    editVersion: number
  ): Promise<void> {
    if (!token || !mcpToolPermissions || mcpToolPermissionsSaving) return;
    const previousConfirmed = mcpToolPermissions;
    const requestId = mcpToolPermissionSaveRequestRef.current + 1;
    mcpToolPermissionSaveRequestRef.current = requestId;
    setMcpToolPermissionsSaving(true);
    setMcpToolPermissionsError(null);
    setMcpToolPermissionsSaved(false);
    try {
      const saved = await updateMcpToolPermissions(token, {
        permissions: { [name]: enabled }
      });
      if (mcpToolPermissionSaveRequestRef.current !== requestId) return;
      setMcpToolPermissions(saved);
      if (mcpToolPermissionEditVersionRef.current === editVersion) {
        setMcpToolPermissionsDraft(saved);
      } else {
        setMcpToolPermissionsDraft(nextDraft);
      }
      setMcpToolPermissionsSaved(true);
      setMcpPermissionRefreshVersion((value) => value + 1);
      setMcpOAuthReloadVersion((value) => value + 1);
    } catch (caught) {
      if (mcpToolPermissionSaveRequestRef.current !== requestId) return;
      mcpToolPermissionEditVersionRef.current += 1;
      setMcpToolPermissionsDraft(previousConfirmed);
      setMcpToolPermissionsError(
        caught instanceof Error ? caught.message : "Unable to save MCP tool permissions"
      );
    } finally {
      if (mcpToolPermissionSaveRequestRef.current === requestId) {
        setMcpToolPermissionsSaving(false);
      }
    }
  }

  function updateMcpToolPermissionDraft(name: string, enabled: boolean): void {
    if (!mcpToolPermissions || !mcpToolPermissionsDraft || mcpToolPermissionsSaving) return;
    const nextDraft = {
      tools: mcpToolPermissionsDraft.tools.map((tool) =>
        tool.name === name ? { ...tool, enabled } : tool
      )
    };
    const editVersion = mcpToolPermissionEditVersionRef.current + 1;
    mcpToolPermissionEditVersionRef.current = editVersion;
    setMcpToolPermissionsDraft(nextDraft);
    setMcpToolPermissionsError(null);
    setMcpToolPermissionsSaved(false);
    void persistMcpToolPermission(name, enabled, nextDraft, editVersion);
  }

  async function copyMcpServerUrl(): Promise<void> {
    setMcpCopyError(null);
    setMcpUrlCopied(false);
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(mcpServerUrl);
      } else {
        const field = document.createElement("textarea");
        field.value = mcpServerUrl;
        field.style.position = "fixed";
        field.style.opacity = "0";
        document.body.appendChild(field);
        field.select();
        const copied = document.execCommand("copy");
        field.remove();
        if (!copied) {
          throw new Error("Clipboard copy was rejected.");
        }
      }
      setMcpUrlCopied(true);
    } catch (caught) {
      setMcpCopyError(
        caught instanceof Error
          ? caught.message
          : "Unable to copy the MCP server URL"
      );
    }
  }

  function openMcpOAuthPermissions(client: McpOAuthManageableClientSummary): void {
    if (mcpOAuthRevokingId !== null || mcpOAuthPermissionSaving || client.status === "revoked") return;
    setMcpOAuthPermissionError(null);
    setMcpOAuthClientsMessage(null);
    setMcpOAuthPermissionTarget(client);
  }

  async function saveMcpOAuthPermissions(deniedTools: string[]): Promise<void> {
    if (!token || !mcpOAuthPermissionTarget || mcpOAuthPermissionSaving) return;
    const target = mcpOAuthPermissionTarget;
    setMcpOAuthPermissionSaving(true);
    setMcpOAuthPermissionError(null);
    try {
      const result = await updateMcpOAuthClientPermissions(
        token,
        target.database_id,
        { denied_tools: deniedTools }
      );
      setMcpOAuthClients((current) =>
        current?.map((client) =>
          client.database_id === target.database_id
            ? {
                ...client,
                denied_tools: result.denied_tools,
                tool_permissions: result.tools
              }
            : client
        ) ?? null
      );
      setMcpOAuthPermissionTarget(null);
      setMcpOAuthClientsMessage(`${target.client_name} permissions saved.`);
    } catch (caught) {
      setMcpOAuthPermissionError(
        caught instanceof Error ? caught.message : "Unable to save OAuth client permissions"
      );
    } finally {
      setMcpOAuthPermissionSaving(false);
    }
  }

  function openMcpOAuthRevokeDialog(client: McpOAuthManageableClientSummary): void {
    if (mcpOAuthRevokingId !== null || client.status === "revoked") return;
    setMcpOAuthRevokeError(null);
    setMcpOAuthClientsMessage(null);
    setMcpOAuthRevokeTarget(client);
  }

  function closeMcpOAuthRevokeDialog(): void {
    if (mcpOAuthRevokingId !== null) return;
    setMcpOAuthRevokeTarget(null);
    setMcpOAuthRevokeError(null);
  }

  function openMcpOAuthRegistration(): void {
    if (mcpOAuthRegistering) return;
    setMcpOAuthRegisterOpen(true);
    setMcpOAuthRegisterAttempted(false);
    setMcpOAuthRegisterError(null);
    setMcpOAuthClientsMessage(null);
  }

  function closeMcpOAuthRegistration(): void {
    if (mcpOAuthRegistering) return;
    setMcpOAuthRegisterOpen(false);
    setMcpOAuthRegisterAttempted(false);
    setMcpOAuthRegisterError(null);
  }

  function chooseMcpOAuthClientType(clientType: McpOAuthClientType): void {
    if (mcpOAuthRegistering) return;
    setMcpOAuthClientTypeDraft(clientType);
    setMcpOAuthAuthMethodDraft(clientType === "public" ? "none" : "client_secret_post");
    setMcpOAuthRegisterError(null);
  }

  async function submitMcpOAuthRegistration(): Promise<void> {
    if (!token || mcpOAuthRegistering) return;
    setMcpOAuthRegisterAttempted(true);
    if (mcpOAuthRegistrationError) return;
    setMcpOAuthRegistering(true);
    setMcpOAuthRegisterError(null);
    setMcpOAuthClientsError(null);
    setMcpOAuthClientsMessage(null);
    try {
      const result = await registerMcpOAuthClient(token, {
        client_name: mcpOAuthClientNameDraft.trim(),
        redirect_uris: mcpOAuthRedirectUris,
        client_type: mcpOAuthClientTypeDraft,
        token_endpoint_auth_method: mcpOAuthAuthMethodDraft
      });
      const refreshed = await getMcpOAuthManageableClients(token);
      setMcpOAuthClients(refreshed.clients);
      setMcpOAuthCredential(result);
      setMcpOAuthSecretVisible(false);
      setMcpOAuthCredentialCopied(null);
      setMcpOAuthRegisterOpen(false);
      setMcpOAuthRegisterAttempted(false);
      setMcpOAuthClientNameDraft("");
      setMcpOAuthRedirectUrisDraft("");
      setMcpOAuthClientTypeDraft("public");
      setMcpOAuthAuthMethodDraft("none");
      setMcpOAuthClientsMessage(`${result.client_name} registered. Save the credentials before closing the result.`);
    } catch (caught) {
      setMcpOAuthRegisterError(caught instanceof Error ? caught.message : "Unable to register the OAuth client");
    } finally {
      setMcpOAuthRegistering(false);
    }
  }

  function closeMcpOAuthCredentialDialog(): void {
    setMcpOAuthCredential(null);
    setMcpOAuthSecretVisible(false);
    setMcpOAuthCredentialCopied(null);
  }

  async function copyMcpOAuthCredential(value: string, field: "client_id" | "client_secret"): Promise<void> {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
      } else {
        const temporary = document.createElement("textarea");
        temporary.value = value;
        temporary.setAttribute("readonly", "");
        temporary.style.position = "fixed";
        temporary.style.opacity = "0";
        document.body.appendChild(temporary);
        temporary.select();
        const copied = document.execCommand("copy");
        temporary.remove();
        if (!copied) throw new Error("Clipboard copy was rejected.");
      }
      setMcpOAuthCredentialCopied(field);
    } catch {
      setMcpOAuthCredentialCopied(null);
    }
  }

  async function confirmMcpOAuthRevocation(): Promise<void> {
    if (!token || !mcpOAuthRevokeTarget || mcpOAuthRevokingId !== null) return;
    const target = mcpOAuthRevokeTarget;
    setMcpOAuthRevokingId(target.database_id);
    setMcpOAuthRevokeError(null);
    setMcpOAuthClientsError(null);
    setMcpOAuthClientsMessage(null);
    try {
      await revokeMcpOAuthClient(token, target.database_id);
      const refreshed = await getMcpOAuthManageableClients(token);
      setMcpOAuthClients(refreshed.clients);
      setMcpOAuthRevokeTarget(null);
      setMcpOAuthClientsMessage(
        target.status === "connected"
          ? `${target.client_name} access revoked. The revoked record is retained for audit but hidden from this list.`
          : `${target.client_name} registration revoked. The revoked record is retained for audit but hidden from this list.`
      );
    } catch (caught) {
      setMcpOAuthRevokeError(caught instanceof Error ? caught.message : "Unable to revoke the OAuth client");
    } finally {
      setMcpOAuthRevokingId(null);
    }
  }

  async function handleCurrencyPreference(nextCurrency: string): Promise<void> {
    if (!token || !currencySettings || currencySettingsSaving) return;
    const normalized = nextCurrency.trim().toUpperCase();
    if (normalized === currencySettings.currency) return;

    const previous = currencySettings;
    setCurrencySettings({ currency: normalized });
    setCurrencySettingsSaving(true);
    setCurrencySettingsError(null);
    setCurrencySettingsSaved(false);

    try {
      const saved = await updateCurrencySettings(token, { currency: normalized });
      setCurrencySettings(saved);
      syncDefaultCurrency(saved.currency);
      setCurrencySettingsSaved(true);
    } catch (caught) {
      setCurrencySettings(previous);
      syncDefaultCurrency(previous.currency);
      setCurrencySettingsError(
        caught instanceof Error ? caught.message : "Unable to save currency preference"
      );
    } finally {
      setCurrencySettingsSaving(false);
    }
  }

  async function handleTimezonePreference(nextTimezone: string): Promise<void> {
    if (!token || !timezoneSettings || timezoneSettingsSaving) return;
    const normalized = nextTimezone.trim();
    if (normalized === timezoneSettings.timezone) return;

    const previous = timezoneSettings;
    setTimezoneSettings({ timezone: normalized });
    setTimezoneSettingsSaving(true);
    setTimezoneSettingsError(null);
    setTimezoneSettingsSaved(false);

    try {
      const saved = await updateTimezoneSettings(token, { timezone: normalized });
      setTimezoneSettings(saved);
      syncTimezone(saved.timezone);
      setTimezoneSettingsSaved(true);
    } catch (caught) {
      setTimezoneSettings(previous);
      syncTimezone(previous.timezone);
      setTimezoneSettingsError(
        caught instanceof Error ? caught.message : "Unable to save timezone preference"
      );
    } finally {
      setTimezoneSettingsSaving(false);
    }
  }

  async function handleOutOfStockPreference(
    nextValue: boolean
  ): Promise<void> {
    if (!token || !searchSettings || searchSettingsSaving) {
      return;
    }

    const previous = searchSettings;
    setSearchSettings({
      show_out_of_stock_section: nextValue
    });
    setSearchSettingsSaving(true);
    setSearchSettingsError(null);
    setSearchSettingsSaved(false);

    try {
      const saved = await updateSearchSettings(token, {
        show_out_of_stock_section: nextValue
      });
      setSearchSettings(saved);
      setSearchSettingsSaved(true);
    } catch (caught) {
      setSearchSettings(previous);
      setSearchSettingsError(
        caught instanceof Error
          ? caught.message
          : "Unable to save search settings"
      );
    } finally {
      setSearchSettingsSaving(false);
    }
  }

  async function saveAccountProfile(): Promise<void> {
    if (!token || !accountDraft || accountSaving) return;
    setAccountSaving(true);
    setAccountError(null);
    setAccountMessage(null);
    try {
      const saved = await updateProfile(token, accountDraft);
      setAccountProfile(saved);
      setAccountDraft({
        username: saved.username,
        displayName: saved.display_name,
        avatarId: saved.avatar_id
      });
      await refreshUser();
      setAccountMessage("Profile saved across Part Pilot.");
    } catch (caught) {
      setAccountError(
        caught instanceof Error ? caught.message : "Unable to save profile"
      );
    } finally {
      setAccountSaving(false);
    }
  }


  async function uploadAccountAvatar(file: File): Promise<void> {
    if (!token || accountAvatarUploading || accountAvatarRemoving) return;
    setAccountAvatarUploading(true);
    setAccountError(null);
    setAccountMessage(null);
    try {
      const prepared = await prepareAccountAvatarImage(file);
      setAccountAvatarPreviewUrl(URL.createObjectURL(prepared));
      const saved = await uploadProfileAvatarImage(token, prepared);
      setAccountProfile(saved);
      await refreshUser();
      setAccountMessage("Custom profile image updated.");
    } catch (caught) {
      setAccountError(
        caught instanceof Error
          ? caught.message
          : "Unable to update the profile image"
      );
    } finally {
      setAccountAvatarPreviewUrl(null);
      setAccountAvatarUploading(false);
    }
  }

  async function removeAccountAvatar(): Promise<void> {
    if (!token || accountAvatarUploading || accountAvatarRemoving) return;
    setAccountAvatarRemoving(true);
    setAccountError(null);
    setAccountMessage(null);
    try {
      const saved = await deleteProfileAvatarImage(token);
      setAccountProfile(saved);
      await refreshUser();
      setAccountMessage("Custom profile image removed.");
    } catch (caught) {
      setAccountError(
        caught instanceof Error
          ? caught.message
          : "Unable to remove the profile image"
      );
    } finally {
      setAccountAvatarRemoving(false);
    }
  }

  async function saveAccountPassword(): Promise<void> {
    if (!token || passwordSaving) return;
    setPasswordError(null);
    setPasswordMessage(null);
    if (!currentPassword) {
      setPasswordError("Enter your current password.");
      return;
    }
    if (newPassword.length < 8 || newPassword.length > 256) {
      setPasswordError("New password must be 8-256 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("New password confirmation does not match.");
      return;
    }

    setPasswordSaving(true);
    try {
      const result = await changePassword(token, {
        currentPassword,
        newPassword
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordMessage(
        result.revoked_other_sessions === 1
          ? "Password changed. 1 other session was revoked."
          : `Password changed. ${result.revoked_other_sessions} other sessions were revoked.`
      );
      setAccountReloadVersion((value) => value + 1);
    } catch (caught) {
      setPasswordError(
        caught instanceof Error ? caught.message : "Unable to change password"
      );
    } finally {
      setPasswordSaving(false);
    }
  }

  async function revokeAccountSession(sessionId: number): Promise<void> {
    if (!token || sessionRevokingId !== null || sessionsRevokingAll) return;
    setSessionRevokingId(sessionId);
    setSessionsError(null);
    setSessionsMessage(null);
    try {
      const result = await revokeSession(token, sessionId);
      setSessionsMessage(
        result.revoked ? "Session revoked." : "Session was already inactive."
      );
      setAccountReloadVersion((value) => value + 1);
    } catch (caught) {
      setSessionsError(
        caught instanceof Error ? caught.message : "Unable to revoke session"
      );
    } finally {
      setSessionRevokingId(null);
    }
  }

  async function revokeOtherAccountSessions(): Promise<void> {
    if (!token || sessionsRevokingAll || sessionRevokingId !== null) return;
    setSessionsRevokingAll(true);
    setSessionsError(null);
    setSessionsMessage(null);
    try {
      const result = await revokeAllOtherSessions(token);
      setSessionsMessage(
        result.revoked_sessions === 1
          ? "1 other session revoked."
          : `${result.revoked_sessions} other sessions revoked.`
      );
      setAccountReloadVersion((value) => value + 1);
    } catch (caught) {
      setSessionsError(
        caught instanceof Error
          ? caught.message
          : "Unable to revoke other sessions"
      );
    } finally {
      setSessionsRevokingAll(false);
    }
  }

  function chooseSettingsSection(
    section: SettingsSection
  ): void {
    setActiveSettingsSection(section);
    window.history.replaceState(
      null,
      "",
      `#settings-${section}`
    );
  }

  async function handleBackupDownload(): Promise<void> {
    if (!token || backupDownloading) {
      return;
    }

    setBackupDownloading(true);
    setBackupError(null);
    setBackupMessage(null);
    try {
      const result = await downloadBackup(token);
      const url = URL.createObjectURL(result.blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = result.filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setBackupMessage(`Downloaded ${result.filename}`);

      try {
        const refreshedStatus = await getManualBackupStatus(token);
        setBackupStatus(refreshedStatus);
        setBackupStatusError(null);
      } catch (statusCaught) {
        setBackupStatusError(
          statusCaught instanceof Error
            ? statusCaught.message
            : "Backup downloaded, but history could not be refreshed"
        );
      }
    } catch (caught) {
      setBackupError(
        caught instanceof Error
          ? caught.message
          : "Unable to download a backup"
      );
    } finally {
      setBackupDownloading(false);
    }
  }

  function chooseRestoreFile(file: File | null): void {
    setRestoreValidation(null);
    setRestoreConfirmation("");
    setRestoreError(null);

    if (!file) {
      setRestoreFile(null);
      return;
    }
    if (!file.name.toLowerCase().endsWith(".ppbackup")) {
      setRestoreFile(null);
      setRestoreError("Choose a Part Pilot .ppbackup file.");
      return;
    }
    if (file.size < 1 || file.size > MAX_RESTORE_FILE_BYTES) {
      setRestoreFile(null);
      setRestoreError(
        "The restore file must be between 1 byte and 256 MiB."
      );
      return;
    }
    setRestoreFile(file);
  }

  async function reviewRestoreBackup(): Promise<void> {
    if (!token || !restoreFile || restoreValidating) {
      return;
    }

    setRestoreValidating(true);
    setRestoreError(null);
    try {
      const validation = await validateRestoreBackup(token, restoreFile);
      setRestoreValidation(validation);
      setRestoreConfirmation("");
      setRestoreDialogOpen(true);
    } catch (caught) {
      setRestoreValidation(null);
      setRestoreError(
        caught instanceof Error
          ? caught.message
          : "Unable to validate the selected backup"
      );
    } finally {
      setRestoreValidating(false);
    }
  }

  function closeRestoreDialog(): void {
    if (restoreCommitting || restoreRestarting) {
      return;
    }
    setRestoreDialogOpen(false);
    setRestoreConfirmation("");
    setRestoreError(null);
  }

  function clearRestoreSelection(): void {
    if (restoreValidating || restoreCommitting || restoreRestarting) {
      return;
    }
    setRestoreFile(null);
    setRestoreValidation(null);
    setRestoreConfirmation("");
    setRestoreError(null);
    if (restoreFileInputRef.current) {
      restoreFileInputRef.current.value = "";
    }
  }

  async function confirmRestoreBackup(): Promise<void> {
    if (!token || !restoreValidation || !canCommitRestore) {
      return;
    }

    setRestoreCommitting(true);
    setRestoreError(null);
    try {
      await commitRestoreBackup(
        token,
        restoreValidation.validation_token
      );
      setRestoreRestarting(true);
      localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
      localStorage.removeItem(APPEARANCE_STORAGE_KEY);
      await waitForPartPilotReady();
      window.location.replace("/");
    } catch (caught) {
      setRestoreError(
        caught instanceof Error
          ? caught.message
          : "Unable to schedule the restore"
      );
      setRestoreCommitting(false);
      setRestoreRestarting(false);
    }
  }

  function openPreferenceResetDialog(
    target: ReversiblePreferenceResetTarget
  ): void {
    if (preferenceMutationInProgress || preferenceResetting) return;
    setPreferenceResetError(null);
    setPreferenceResetTarget(target);
  }

  function closePreferenceResetDialog(): void {
    if (preferenceResetting) return;
    setPreferenceResetTarget(null);
    setPreferenceResetError(null);
  }

  async function confirmPreferenceReset(): Promise<void> {
    const target = preferenceResetTarget;
    if (!token) {
      setPreferenceResetError("Your session is unavailable. Sign in again.");
      return;
    }
    if (!target || preferenceMutationInProgress || preferenceResetting) return;
    if (target === "reservations") {
      clearReservationAutosaveTimer();
      reservationSaveRequestRef.current += 1;
      reservationEditVersionRef.current += 1;
    }
    setPreferenceResetting(true);
    setPreferenceResetError(null);
    setPreferenceResetMessage(null);
    try {
      const reset = await resetReversiblePreference(token, { target });
      if (reset.target !== target) throw new Error("Preference reset returned an unexpected target");
      if (target === "appearance") {
        if (!reset.appearance) throw new Error("Appearance reset response is incomplete");
        reloadAppearance();
        setPreferenceResetMessage({ target, text: "Theme reset to Dark." });
      } else if (target === "inventory") {
        if (!reset.inventory) throw new Error("Inventory reset response is incomplete");
        setSearchSettings(reset.inventory);
        setSearchSettingsLoading(false);
        setSearchSettingsError(null);
        setSearchSettingsSaved(false);
        setPreferenceResetMessage({ target, text: "Inventory display reset to separate out-of-stock results." });
      } else {
        if (!reset.reservations) throw new Error("Reservation reset response is incomplete");
        setReservationSettings(reset.reservations);
        setReservationDraft(reset.reservations);
        setReservationSettingsLoading(false);
        setReservationSettingsError(null);
        setReservationSettingsSaved(false);
        setPreferenceResetMessage({ target, text: "Reservation defaults reset to no automatic expiry." });
      }
      setPreferenceResetTarget(null);
    } catch (caught) {
      setPreferenceResetError(caught instanceof Error ? caught.message : "Unable to reset this preference");
    } finally {
      setPreferenceResetting(false);
    }
  }

  function openDatabaseResetDialog(): void {
    setConfirmation("");
    setResetError(null);
    setResetDialogOpen(true);
  }

  function closeDatabaseResetDialog(): void {
    if (isResetting) {
      return;
    }
    setResetDialogOpen(false);
    setConfirmation("");
    setResetError(null);
  }

  async function confirmDatabaseReset(): Promise<void> {
    const activeToken =
      token ?? localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);

    if (!activeToken) {
      setResetError(
        "Your session is missing. Sign in again before resetting."
      );
      return;
    }

    setIsResetting(true);
    setResetError(null);

    try {
      await resetApplicationDatabase(
        activeToken,
        confirmation
      );
      localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
      localStorage.removeItem(APPEARANCE_STORAGE_KEY);
      document.documentElement.dataset.theme = "dark";
      document.documentElement.dataset.themePreference = "dark";
      document.documentElement.style.colorScheme = "dark";
      window.location.replace("/");
    } catch (caught) {
      setResetError(
        caught instanceof Error
          ? caught.message
          : "Unable to reset the database"
      );
      setIsResetting(false);
    }
  }

  return (
    <div
      className="page-stack settings-page"
      data-search-settings-version="search-settings-toggle-v194"
      data-reservation-settings-version="reservation-expiry-settings-v362"
      data-partpilot-appearance="PARTPILOT:SETTINGS_APPEARANCE_WORKSPACE:V412"
      data-partpilot-runtime-badge="PARTPILOT:SETTINGS_RUNTIME_BADGE_REMOVED:V428"
      data-partpilot-backup-restore="PARTPILOT:SETTINGS_BACKUP_RESTORE_UI:V442"
      data-partpilot-backup-status="PARTPILOT:SETTINGS_MANUAL_BACKUP_STATUS_UI:V454"
      data-partpilot-settings-tabs="PARTPILOT:SETTINGS_SECTION_TABS:V444"
      data-partpilot-mcp-settings="PARTPILOT:MCP_SETTINGS_UI:V473"
      data-partpilot-mcp-oauth-clients="PARTPILOT:MCP_OAUTH_MANUAL_REGISTRATION_UI:V569"
      data-partpilot-account-security="PARTPILOT:SETTINGS_ACCOUNT_SECURITY_UI:V592"
      data-partpilot-account-avatar-refinement="PARTPILOT:SETTINGS_ACCOUNT_AVATAR_REFINEMENT:V594"
      data-partpilot-account-custom-avatar="PARTPILOT:SETTINGS_CUSTOM_AVATAR_UI:V602"
      data-partpilot-rest-api-keys="PARTPILOT:REST_API_KEY_SETTINGS_UI:V618"
      data-partpilot-preferences-workspace="PARTPILOT:SETTINGS_PREFERENCES_WORKSPACE:V673"
      data-partpilot-live-sync="PARTPILOT:SETTINGS_ACCOUNT_PREFERENCES_LIVE_SYNC:V705"
      data-partpilot-integrations-live-sync="PARTPILOT:API_KEY_MCP_INTEGRATION_LIVE_SYNC:V708"
      data-partpilot-user-management="PARTPILOT:SETTINGS_USER_MANAGEMENT_UI:V774"
      data-partpilot-active-settings-section={activeSettingsSection}
      data-partpilot-unified-settings-hierarchy="PARTPILOT:UNIFIED_SETTINGS_HIERARCHY:V781"
      data-partpilot-settings-numberless-hierarchy="PARTPILOT:SETTINGS_NUMBERLESS_HIERARCHY:V783"
      data-partpilot-settings-stage-icons="PARTPILOT:SETTINGS_SEMANTIC_STAGE_ICONS:V784"
    >
      <header className="page-header settings-page-header">
        <div>
          <p className="eyebrow">Application configuration</p>
          <h1>Settings</h1>
          <p>
            {canAdministerWorkspace
              ? "Manage your account, users and roles, workspace preferences, REST API access, MCP access, and local data controls."
              : "Manage your account and role-capped REST API access."}
          </p>
        </div>
      </header>

      <nav
        className="settings-section-nav"
        aria-label="Settings sections"
      >
        <button
          className={
            activeSettingsSection === "account" ? "is-active" : ""
          }
          type="button"
          aria-current={
            activeSettingsSection === "account" ? "page" : undefined
          }
          aria-controls="settings-account"
          onClick={() => chooseSettingsSection("account")}
        >
          Account
        </button>
        {canAdministerUsers ? (
          <button
            className={activeSettingsSection === "users" ? "is-active" : ""}
            type="button"
            aria-current={activeSettingsSection === "users" ? "page" : undefined}
            aria-controls="settings-users"
            onClick={() => chooseSettingsSection("users")}
          >
            Users
          </button>
        ) : null}
        {canAdministerWorkspace ? (
        <button
          className={activeSettingsSection === "preferences" ? "is-active" : ""}
          type="button"
          aria-current={activeSettingsSection === "preferences" ? "page" : undefined}
          aria-controls="settings-preferences"
          onClick={() => chooseSettingsSection("preferences")}
        >
          Preferences
        </button>
        ) : null}
        <button
          className={
            activeSettingsSection === "api"
              ? "is-active"
              : ""
          }
          type="button"
          aria-current={
            activeSettingsSection === "api"
              ? "page"
              : undefined
          }
          aria-controls="settings-api"
          onClick={() => chooseSettingsSection("api")}
        >
          API Access
        </button>
        {canAdministerWorkspace ? (
        <button
          className={
            activeSettingsSection === "mcp"
              ? "is-active"
              : ""
          }
          type="button"
          aria-current={
            activeSettingsSection === "mcp"
              ? "page"
              : undefined
          }
          aria-controls="settings-mcp"
          onClick={() => chooseSettingsSection("mcp")}
        >
          MCP
        </button>
        ) : null}
        {canAdministerWorkspace ? (
        <button
          className={
            activeSettingsSection === "data"
              ? "is-active"
              : ""
          }
          type="button"
          aria-current={
            activeSettingsSection === "data"
              ? "page"
              : undefined
          }
          aria-controls="settings-data"
          onClick={() => chooseSettingsSection("data")}
        >
          Data
        </button>
        ) : null}
      </nav>

      <section
        id="settings-account"
        data-partpilot-background-refresh="PARTPILOT:STABLE_BACKGROUND_REFRESH:V718"
        className="card settings-section settings-account-section"
        aria-labelledby="settings-account-title"
        hidden={activeSettingsSection !== "account"}
        data-partpilot-account-security="PARTPILOT:SETTINGS_ACCOUNT_SECURITY_UI:V592"
      >
        <div className="settings-section-heading">
          <div>
            <span className="card-label">
              {user?.role
                ? `${user.role.charAt(0).toUpperCase()}${user.role.slice(1)} account`
                : "Signed-in account"}
            </span>
            <h2 id="settings-account-title">Account &amp; Security</h2>
            <p>
              Update your Part Pilot identity, change your password, and
              control active signed-in sessions.
            </p>
          </div>
          <span className="settings-account-user-badge">
            {user?.username ?? "Signed in"}
          </span>
        </div>

        <div className="settings-account-grid">
          <div className="settings-account-panel settings-account-primary-panel settings-unified-stage">
            <div className="settings-account-panel-heading settings-unified-stage-heading">
              <SettingsStageIcon name="profile" />
              <div>
                <span className="card-label">Profile</span>
                <h3>Identity &amp; avatar</h3>
              </div>
              {accountDraft ? (
                <UserAvatar
                  avatarId={accountDraft.avatarId}
                  displayName={accountDraft.displayName}
                  imageUrl={accountAvatarPreviewUrl ?? avatarImageUrl}
                  className="settings-account-preview"
                />
              ) : null}
            </div>

            {accountLoading || !accountDraft ? (
              <p className="settings-account-state" role="status">
                Loading profile...
              </p>
            ) : (
              <form
                className="settings-account-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  void saveAccountProfile();
                }}
              >
                <div className="settings-account-fields">
                  <label>
                    <span>Display name</span>
                    <input
                      type="text"
                      maxLength={160}
                      value={accountDraft.displayName}
                      disabled={accountSaving}
                      onChange={(event) => {
                        setAccountDraft({
                          ...accountDraft,
                          displayName: event.target.value
                        });
                        setAccountError(null);
                        setAccountMessage(null);
                      }}
                    />
                  </label>
                  <label>
                    <span>Username</span>
                    <input
                      type="text"
                      maxLength={80}
                      autoCapitalize="none"
                      autoCorrect="off"
                      spellCheck={false}
                      value={accountDraft.username}
                      disabled={accountSaving}
                      onChange={(event) => {
                        setAccountDraft({
                          ...accountDraft,
                          username: event.target.value.toLowerCase()
                        });
                        setAccountError(null);
                        setAccountMessage(null);
                      }}
                    />
                  </label>
                </div>

                <fieldset
                  className="settings-account-avatar-fieldset"
                  disabled={
                    accountSaving ||
                    accountAvatarUploading ||
                    accountAvatarRemoving
                  }
                >
                  <legend>Built-in avatar</legend>
                  <div
                    className="settings-account-avatar-grid"
                    role="radiogroup"
                    aria-label="Built-in avatar"
                  >
                    {availableAccountAvatars.map((option) => {
                      const selected =
                        accountDraft.avatarId === option.value;
                      return (
                        <button
                          key={option.value}
                          className={
                            selected
                              ? "settings-account-avatar is-selected"
                              : "settings-account-avatar"
                          }
                          type="button"
                          role="radio"
                          aria-checked={selected}
                          aria-label={option.label}
                          title={option.label}
                          onClick={() => {
                            setAccountDraft({
                              ...accountDraft,
                              avatarId: option.value
                            });
                            setAccountError(null);
                            setAccountMessage(null);
                          }}
                        >
                          <UserAvatar
                            avatarId={option.value}
                            displayName={accountDraft.displayName}
                            className="settings-account-avatar-visual"
                          />
                        </button>
                      );
                    })}
                  </div>
                </fieldset>


                <div
                  className="settings-account-custom-avatar"
                  data-partpilot-custom-avatar="PARTPILOT:SETTINGS_CUSTOM_AVATAR_UI:V602"
                >
                  <div className="settings-account-custom-avatar-copy">
                    <strong>Custom image</strong>
                    <span>
                      PNG, JPEG or WebP up to 5 MiB. Images are center-cropped
                      and normalized before storage.
                    </span>
                    {accountProfile?.has_custom_avatar ? (
                      <span className="settings-account-custom-avatar-active">
                        Custom image active. Built-in selection remains the fallback.
                      </span>
                    ) : null}
                  </div>
                  <div className="settings-account-avatar-actions">
                    <input
                      ref={accountAvatarInputRef}
                      className="settings-account-avatar-input"
                      type="file"
                      accept="image/png,image/jpeg,image/webp"
                      tabIndex={-1}
                      aria-hidden="true"
                      onChange={(event) => {
                        const file = event.currentTarget.files?.[0];
                        event.currentTarget.value = "";
                        if (file) {
                          void uploadAccountAvatar(file);
                        }
                      }}
                    />
                    <button
                      className="settings-action settings-action-secondary"
                      type="button"
                      disabled={
                        accountAvatarUploading || accountAvatarRemoving
                      }
                      onClick={() => accountAvatarInputRef.current?.click()}
                    >
                      {accountAvatarUploading
                        ? "Uploading..."
                        : accountProfile?.has_custom_avatar
                          ? "Replace image"
                          : "Upload image"}
                    </button>
                    {accountProfile?.has_custom_avatar ? (
                      <button
                        className="settings-action settings-action-danger"
                        type="button"
                        disabled={
                          accountAvatarUploading || accountAvatarRemoving
                        }
                        onClick={() => void removeAccountAvatar()}
                      >
                        {accountAvatarRemoving ? "Removing..." : "Remove image"}
                      </button>
                    ) : null}
                  </div>
                </div>

                {accountError ? (
                  <p
                    className="settings-account-state is-error"
                    role="alert"
                  >
                    {accountError}
                  </p>
                ) : null}
                {accountMessage ? (
                  <p
                    className="settings-account-state is-success"
                    role="status"
                  >
                    {accountMessage}
                  </p>
                ) : null}

                <div className="settings-action-row">
                  <button
                    className="settings-action settings-action-primary"
                    type="submit"
                    disabled={
                      accountSaving ||
                      accountAvatarUploading ||
                      accountAvatarRemoving ||
                      !accountDraft.displayName.trim() ||
                      !accountDraft.username.trim()
                    }
                  >
                    {accountSaving ? "Saving profile..." : "Save profile"}
                  </button>
                </div>
              </form>
            )}
          </div>

          <div className="settings-account-panel settings-account-primary-panel settings-unified-stage">
            <div className="settings-account-panel-heading settings-unified-stage-heading">
              <SettingsStageIcon name="password" />
              <div>
                <span className="card-label">Password</span>
                <h3>Change password</h3>
              </div>
            </div>
            <p className="settings-account-helper">
              Changing your password keeps this session signed in and
              revokes every other active session.
            </p>

            <form
              className="settings-account-form"
              onSubmit={(event) => {
                event.preventDefault();
                void saveAccountPassword();
              }}
            >
              <div className="settings-account-password-fields">
                <label>
                  <span>Current password</span>
                  <input
                    type="password"
                    autoComplete="current-password"
                    value={currentPassword}
                    disabled={passwordSaving}
                    onChange={(event) => {
                      setCurrentPassword(event.target.value);
                      setPasswordError(null);
                      setPasswordMessage(null);
                    }}
                  />
                </label>
                <label>
                  <span>New password</span>
                  <input
                    type="password"
                    autoComplete="new-password"
                    minLength={8}
                    maxLength={256}
                    value={newPassword}
                    disabled={passwordSaving}
                    onChange={(event) => {
                      setNewPassword(event.target.value);
                      setPasswordError(null);
                      setPasswordMessage(null);
                    }}
                  />
                </label>
                <label>
                  <span>Confirm new password</span>
                  <input
                    type="password"
                    autoComplete="new-password"
                    minLength={8}
                    maxLength={256}
                    value={confirmPassword}
                    disabled={passwordSaving}
                    onChange={(event) => {
                      setConfirmPassword(event.target.value);
                      setPasswordError(null);
                      setPasswordMessage(null);
                    }}
                  />
                </label>
              </div>

              {passwordError ? (
                <p
                  className="settings-account-state is-error"
                  role="alert"
                >
                  {passwordError}
                </p>
              ) : null}
              {passwordMessage ? (
                <p
                  className="settings-account-state is-success"
                  role="status"
                >
                  {passwordMessage}
                </p>
              ) : null}

              <div className="settings-action-row">
                <button
                  className="settings-action settings-action-primary"
                  type="submit"
                  disabled={
                    passwordSaving ||
                    !currentPassword ||
                    !newPassword ||
                    !confirmPassword
                  }
                >
                  {passwordSaving
                    ? "Changing password..."
                    : "Change password"}
                </button>
              </div>
            </form>
          </div>

          <div
            className="settings-account-panel settings-account-sessions-panel settings-unified-stage"
          >
            <div className="settings-account-sessions-heading settings-unified-stage-heading">
              <SettingsStageIcon name="sessions" />
              <div>
                <span className="card-label">Security</span>
                <h3>Active sessions</h3>
                <p>
                  {activeAccountSessions.length} active ·{" "}
                  {otherActiveSessionCount} other
                </p>
              </div>
              <button
                className="settings-action settings-action-danger"
                type="button"
                disabled={
                  sessionsLoading ||
                  sessionsRevokingAll ||
                  sessionRevokingId !== null ||
                  otherActiveSessionCount === 0
                }
                onClick={() => void revokeOtherAccountSessions()}
              >
                {sessionsRevokingAll
                  ? "Revoking..."
                  : "Revoke all other sessions"}
              </button>
            </div>

            {sessionsLoading ? (
              <p className="settings-account-state" role="status">
                Loading active sessions...
              </p>
            ) : activeAccountSessions.length === 0 ? (
              <p className="settings-account-state">
                No active sessions were returned.
              </p>
            ) : (
              <div className="settings-account-session-list">
                {activeAccountSessions.map((session) => (
                  <div
                    className={
                      session.is_current
                        ? "settings-account-session is-current"
                        : "settings-account-session"
                    }
                    key={session.id}
                  >
                    <div className="settings-account-session-copy">
                      <div className="settings-account-session-title">
                        <strong>
                          {sessionClientLabel(session.user_agent)}
                        </strong>
                        <span
                          className={
                            session.is_current ? "is-current" : ""
                          }
                        >
                          {session.is_current ? "Current" : "Active"}
                        </span>
                      </div>
                      <div className="settings-account-session-meta">
                        <span>
                          Signed in {formatUtc(session.created_at, timezone)}
                        </span>
                        <span>
                          Expires {formatUtc(session.expires_at, timezone)}
                        </span>
                        {session.ip_address ? (
                          <span>IP {session.ip_address}</span>
                        ) : null}
                      </div>
                    </div>
                    {session.is_current ? (
                      <span className="settings-account-current-note">
                        This device
                      </span>
                    ) : (
                      <button
                        className="settings-action settings-action-danger"
                        type="button"
                        disabled={
                          sessionRevokingId !== null ||
                          sessionsRevokingAll
                        }
                        onClick={() =>
                          void revokeAccountSession(session.id)
                        }
                      >
                        {sessionRevokingId === session.id
                          ? "Revoking..."
                          : "Revoke"}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}

            {sessionsError ? (
              <p
                className="settings-account-state is-error"
                role="alert"
              >
                {sessionsError}
              </p>
            ) : null}
            {sessionsMessage ? (
              <p
                className="settings-account-state is-success"
                role="status"
              >
                {sessionsMessage}
              </p>
            ) : null}
          </div>
        </div>
      </section>

      {canAdministerUsers && token && user ? (
        <UserManagementSection
          token={token}
          currentUser={user}
          timezone={timezone}
          liveRevision={accountLiveRevision}
          hidden={activeSettingsSection !== "users"}
        />
      ) : null}

      {canAdministerWorkspace ? (
      <section
        id="settings-preferences"
        data-partpilot-background-refresh="PARTPILOT:STABLE_BACKGROUND_REFRESH:V718"
        className="card settings-section settings-preferences-section"
        aria-labelledby="settings-preferences-title"
        hidden={activeSettingsSection !== "preferences"}
        data-partpilot-preferences-workspace="PARTPILOT:SETTINGS_PREFERENCES_WORKSPACE:V673"
      >
        <div className="settings-section-heading">
          <div>
            <span className="card-label">Workspace preferences</span>
            <h2 id="settings-preferences-title">Preferences</h2>
            <p>
              Control interface and workflow defaults in one place. Changes
              save automatically; fixed defaults can be reset independently.
            </p>
          </div>
        </div>

        <div className="settings-preferences-grid">
          <section className="settings-preference-card settings-unified-stage" aria-labelledby="settings-theme-title">
            <div className="settings-preference-card-heading settings-unified-stage-heading">
              <SettingsStageIcon name="theme" />
              <div>
                <span className="card-label">Interface</span>
                <h3 id="settings-theme-title">Theme</h3>
                <p>Choose how Part Pilot is rendered across the complete workspace.</p>
              </div>
              <button className="settings-action settings-action-secondary" type="button" disabled={appearanceLoading || appearanceSaving || preferenceResetting} onClick={() => openPreferenceResetDialog("appearance")}>Reset to default</button>
            </div>
            {appearanceLoading ? <p className="settings-preference-state" role="status">Loading appearance preference...</p> : (
              <div className="settings-theme-options" role="radiogroup" aria-label="Application appearance">
                {APPEARANCE_OPTIONS.map((option) => {
                  const disabled = appearanceSaving || (option.value !== "dark" && !lightThemeAvailable);
                  return (
                    <button key={option.value} className={theme === option.value ? "settings-theme-option is-selected" : "settings-theme-option"} type="button" role="radio" aria-checked={theme === option.value} disabled={disabled} onClick={() => void selectTheme(option.value)}>
                      <span className={`settings-theme-preview is-${option.value}`} aria-hidden="true"><span className="settings-preview-sidebar" /><span className="settings-preview-main"><i /><i /><i /></span></span>
                      <span className="settings-theme-copy"><strong>{option.title}</strong><span>{option.description}</span></span>
                      <span className="settings-theme-check" aria-hidden="true">{theme === option.value ? "Selected" : ""}</span>
                    </button>
                  );
                })}
              </div>
            )}
            {!lightThemeAvailable ? <p className="settings-preference-state">Light and System modes are unavailable for this installation. Dark remains active.</p> : null}
            {appearanceError ? <div className="settings-preference-state is-error" role="alert"><span>{appearanceError}</span><button type="button" onClick={reloadAppearance}>Retry</button></div> : null}
            {appearanceSaved && !appearanceError ? <p className="settings-preference-state is-success" role="status">Appearance saved automatically and applied across Part Pilot.</p> : null}
            {preferenceResetMessage?.target === "appearance" ? <p className="settings-preference-state is-success" role="status">{preferenceResetMessage.text}</p> : null}
            <p className="settings-preference-default-note">Default: Dark</p>
          </section>

          <section className="settings-preference-card settings-regional-card settings-unified-stage" aria-labelledby="settings-regional-title" data-partpilot-regional-display="PARTPILOT:REGIONAL_DISPLAY_PREFERENCES:V676">
            <div className="settings-preference-card-heading settings-unified-stage-heading">
              <SettingsStageIcon name="regional" />
              <div>
                <span className="card-label">Regional display</span>
                <h3 id="settings-regional-title">Currency &amp; timezone</h3>
                <p>Set how Part Pilot displays money and stored timestamps across the workspace. These choices do not convert stored prices, rewrite historical currency snapshots, or alter stored UTC timestamps.</p>
              </div>
            </div>
            <div className="settings-regional-grid">
              <label className="settings-field">
                <span>Currency</span>
                {currencySettingsLoading ? <small role="status">Loading currency...</small> : null}
                {!currencySettingsLoading && currencySettings ? (
                  <span className="settings-select-shell">
                    <select value={currencySettings.currency} disabled={currencySettingsSaving} onChange={(event) => void handleCurrencyPreference(event.currentTarget.value)} aria-describedby="settings-currency-help">
                      {currencyOptions.map((option) => <option key={option.code} value={option.code}>{option.label}</option>)}
                    </select>
                  </span>
                ) : null}
                <small id="settings-currency-help">Used for inventory price formatting and future Project/Reservation price snapshots. No FX conversion is performed.</small>
                {currencySettingsSaving ? <small className="settings-preference-state" role="status">Saving currency...</small> : null}
                {currencySettingsError ? <small className="settings-preference-state is-error" role="alert">{currencySettingsError}</small> : null}
                {currencySettingsSaved && !currencySettingsError ? <small className="settings-preference-state is-success" role="status">Currency saved.</small> : null}
              </label>
              <label className="settings-field">
                <span>Display timezone</span>
                {timezoneSettingsLoading ? <small role="status">Loading timezone...</small> : null}
                {!timezoneSettingsLoading && timezoneSettings ? (
                  <span className="settings-select-shell">
                    <select value={timezoneSettings.timezone} disabled={timezoneSettingsSaving} onChange={(event) => void handleTimezonePreference(event.currentTarget.value)} aria-describedby="settings-timezone-help">
                      {!timezoneOptions.some((option) => option.value === timezoneSettings.timezone) ? <option value={timezoneSettings.timezone}>{timezoneSettings.timezone}</option> : null}
                      {timezoneOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                  </span>
                ) : null}
                <small id="settings-timezone-help">Controls passive date/time display across Part Pilot. Stored timestamps and datetime-entry semantics are unchanged.</small>
                {timezoneSettingsSaving ? <small className="settings-preference-state" role="status">Saving timezone...</small> : null}
                {timezoneSettingsError ? <small className="settings-preference-state is-error" role="alert">{timezoneSettingsError}</small> : null}
                {timezoneSettingsSaved && !timezoneSettingsError ? <small className="settings-preference-state is-success" role="status">Timezone saved and applied.</small> : null}
              </label>
            </div>
          </section>

          <section className="settings-preference-card settings-unified-stage" aria-labelledby="settings-search-title" data-partpilot-compact-search="PARTPILOT:COMPACT_OUT_OF_STOCK_PREFERENCE:V418">
            <div className="settings-preference-card-heading settings-unified-stage-heading">
              <SettingsStageIcon name="inventory" />
              <div>
                <span className="card-label">Inventory display</span>
                <h3 id="settings-search-title">Separate out-of-stock results</h3>
                <p id="settings-search-description">Show zero-stock matches below available parts when All is selected. The explicit Out filter always remains available.</p>
              </div>
              <button className="settings-action settings-action-secondary" type="button" disabled={searchSettingsLoading || searchSettingsSaving || preferenceResetting} onClick={() => openPreferenceResetDialog("inventory")}>Reset to default</button>
            </div>
            <div className="settings-preference-inline-control">
              {searchSettingsLoading ? <span className="settings-search-compact-status" role="status">Loading...</span> : null}
              {!searchSettingsLoading && searchSettings ? (
                <label className={searchSettingsSaving ? "settings-compact-switch-control is-disabled" : "settings-compact-switch-control"}>
                  <span className="settings-compact-switch-state">{searchSettingsSaving ? "Saving..." : searchSettings.show_out_of_stock_section ? "On" : "Off"}</span>
                  <input type="checkbox" role="switch" checked={searchSettings.show_out_of_stock_section} onChange={(event) => void handleOutOfStockPreference(event.target.checked)} disabled={searchSettingsSaving} aria-label="Show a separate out-of-stock section" aria-describedby="settings-search-description" />
                  <span className="settings-switch" aria-hidden="true" />
                </label>
              ) : null}
            </div>
            {searchSettingsError ? <p className="settings-search-compact-feedback is-error" role="alert">{searchSettingsError}</p> : null}
            {searchSettingsSaved && !searchSettingsError ? <p className="settings-search-compact-feedback is-success" role="status">Preference saved automatically.</p> : null}
            {preferenceResetMessage?.target === "inventory" ? <p className="settings-preference-state is-success" role="status">{preferenceResetMessage.text}</p> : null}
            <p className="settings-preference-default-note">Default: On</p>
          </section>

          <section className="settings-preference-card settings-unified-stage" aria-labelledby="settings-reservation-title" data-partpilot-marker="PARTPILOT:RESERVATION_EXPIRY_SETTINGS_UI:V362" data-partpilot-preference-autosave="PARTPILOT:REVERSIBLE_PREFERENCE_AUTOSAVE:V667">
            <div className="settings-preference-card-heading settings-unified-stage-heading">
              <SettingsStageIcon name="reservation" />
              <div>
                <span className="card-label">Reservation workflow</span>
                <h3 id="settings-reservation-title">Reservation defaults</h3>
                <p>Set the suggested expiry for new manual reservations. Existing reservations are never rewritten.</p>
              </div>
              <button className="settings-action settings-action-secondary" type="button" disabled={reservationSettingsLoading || reservationSettingsSaving || preferenceResetting} onClick={() => openPreferenceResetDialog("reservations")}>Reset to default</button>
            </div>
            {reservationSettingsLoading ? <p className="settings-preference-state" role="status">Loading reservation defaults...</p> : null}
            {!reservationSettingsLoading && reservationDraft ? (
              <div className="settings-reservation-form">
                <div className="settings-segmented-control" role="radiogroup" aria-label="Default reservation expiry">
                  <button type="button" role="radio" aria-checked={reservationDraft.expiry_mode === "none"} className={reservationDraft.expiry_mode === "none" ? "is-active" : ""} onClick={() => chooseReservationExpiryMode("none")} disabled={reservationSettingsSaving}>No automatic expiry</button>
                  <button type="button" role="radio" aria-checked={reservationDraft.expiry_mode === "default"} className={reservationDraft.expiry_mode === "default" ? "is-active" : ""} onClick={() => chooseReservationExpiryMode("default")} disabled={reservationSettingsSaving}>Default expiry after</button>
                </div>
                {reservationDraft.expiry_mode === "default" ? (
                  <label className="settings-days-field">
                    <span>Default expiry duration</span>
                    <span className="settings-days-control"><input type="number" min={1} max={3650} step={1} inputMode="numeric" value={reservationDraft.default_days ?? ""} onChange={(event) => updateReservationDefaultDays(event.currentTarget.value)} aria-invalid={Boolean(reservationDaysError)} aria-describedby="reservation-default-days-help" disabled={reservationSettingsSaving} /><strong>days</strong></span>
                    <small id="reservation-default-days-help">Calculated when New reservation is opened.</small>
                  </label>
                ) : <p className="settings-reservation-summary">New reservations start with no expiry selected.</p>}
                {reservationDaysError ? <p className="settings-preference-state is-error" role="alert">{reservationDaysError}</p> : null}
              </div>
            ) : null}
            {reservationSettingsSaving ? <p className="settings-preference-state" role="status">Saving reservation defaults...</p> : null}
            {reservationSettingsError && !reservationDaysError ? <div className="settings-preference-state is-error" role="alert"><span>{reservationSettingsError}</span>{!reservationDraft ? <button type="button" onClick={() => setReservationReloadVersion((value) => value + 1)}>Retry</button> : null}</div> : null}
            {reservationSettingsSaved && !reservationSettingsError ? <p className="settings-preference-state is-success" role="status">Reservation defaults saved automatically.</p> : null}
            {preferenceResetMessage?.target === "reservations" ? <p className="settings-preference-state is-success" role="status">{preferenceResetMessage.text}</p> : null}
            <p className="settings-preference-default-note">Default: No automatic expiry</p>
          </section>
        </div>
      </section>
      ) : null}

      <div
        className="settings-content-grid"
        data-partpilot-settings-layout="PARTPILOT:SETTINGS_DESKTOP_COMPOSITION:V423"
      >
        <ApiKeySettingsSection
          token={token}
          hidden={activeSettingsSection !== "api"}
          liveReloadVersion={apiKeyLiveReloadVersion}
        />

        {canAdministerWorkspace ? (
        <section
          id="settings-mcp"
          className="card settings-section settings-mcp-section settings-grid-mcp"
          aria-labelledby="settings-mcp-title"
          hidden={activeSettingsSection !== "mcp"}
          data-partpilot-mcp-direct-auth="PARTPILOT:MCP_DIRECT_AUTH_UI:V500"
          data-partpilot-mcp-autosave="PARTPILOT:MCP_AUTOSAVE:V715"
          data-partpilot-mcp-background-refresh="PARTPILOT:MCP_BACKGROUND_REFRESH:V716"
        >
          <div className="settings-section-heading settings-mcp-heading">
            <div>
              <span className="card-label">Integrations</span>
              <h2 id="settings-mcp-title">Model Context Protocol</h2>
              <p>
                Control the MCP server, OAuth clients, and named direct clients
                from one security boundary.
              </p>
            </div>
            {mcpDraft ? (
              <span
                className={
                  mcpDraft.enabled
                    ? "settings-mcp-state is-enabled"
                    : "settings-mcp-state"
                }
              >
                {mcpDraft.enabled ? "Server enabled" : "Server disabled"}
              </span>
            ) : null}
          </div>

          {mcpSettingsLoading && !mcpDraft ? (
            <p className="settings-preference-state" role="status">
              Loading MCP settings...
            </p>
          ) : null}

          {mcpDraft ? (
            <>
              <div
                className="settings-mcp-architecture"
                data-partpilot-mcp-settings-hierarchy="PARTPILOT:MCP_SETTINGS_HIERARCHY:V780"
              >
                <section className="settings-mcp-stage settings-mcp-stage-server" aria-labelledby="settings-mcp-server-stage-title">
                  <div className="settings-mcp-stage-heading">
                    <SettingsStageIcon name="server" />
                    <div>
                      <span className="settings-mcp-stage-kicker">Server</span>
                      <h3 id="settings-mcp-server-stage-title">MCP endpoint</h3>
                      <p>Start with the server itself. This master switch controls every MCP connection and capability below.</p>
                    </div>
                    <span className={mcpDraft.enabled ? "settings-mcp-stage-status is-enabled" : "settings-mcp-stage-status"}>{mcpDraft.enabled ? "Enabled" : "Disabled"}</span>
                  </div>

                  <label className={mcpSettingsSaving ? "settings-toggle-row settings-mcp-primary-toggle is-disabled is-saving" : "settings-toggle-row settings-mcp-primary-toggle"}>
                    <span className="settings-toggle-copy"><strong>Enable MCP server</strong><span>Allow MCP clients to connect to the exact <code>/mcp</code> endpoint.</span></span>
                    <input type="checkbox" role="switch" checked={mcpDraft.enabled} disabled={mcpSettingsSaving} onChange={(event) => updateMcpDraft("enabled", event.target.checked)} />
                    <span className="settings-switch" aria-hidden="true" />
                  </label>

                  <div className="settings-mcp-endpoint">
                    <div className="settings-mcp-endpoint-copy">
                      <strong>MCP server URL</strong>
                      <span>Use this exact URL when adding Part Pilot to a client.</span>
                    </div>
                    <div className="settings-copy-field settings-mcp-url-row">
                      <input type="text" value={mcpServerUrl} readOnly aria-label="MCP server URL" onFocus={(event) => event.currentTarget.select()} />
                      <span className="settings-copy-field-actions"><button type="button" onClick={() => void copyMcpServerUrl()}>{mcpUrlCopied ? "Copied" : "Copy"}</button></span>
                    </div>
                    <p className={mcpUsesPublicHttps ? "settings-mcp-endpoint-note is-ready" : "settings-mcp-endpoint-note is-warning"}>
                      {mcpUsesPublicHttps ? "This page is using HTTPS, as required for remote MCP credentials." : "Remote MCP clients should use Part Pilot through its public HTTPS address."}
                    </p>
                    {mcpCopyError ? <p className="settings-mcp-copy-error" role="alert">{mcpCopyError}</p> : null}
                  </div>
                </section>

                <section className={!mcpDraft.enabled ? "settings-mcp-stage settings-mcp-stage-capabilities is-disabled" : "settings-mcp-stage settings-mcp-stage-capabilities"} aria-labelledby="settings-mcp-capabilities-stage-title" aria-disabled={!mcpDraft.enabled}>
                  <div className="settings-mcp-stage-heading">
                    <SettingsStageIcon name="capabilities" />
                    <div>
                      <span className="settings-mcp-stage-kicker">Capabilities</span>
                      <h3 id="settings-mcp-capabilities-stage-title">Tools clients can use</h3>
                      <p>Set the broad read/write ceilings first. Expand a catalogue only when you need to change an individual tool.</p>
                    </div>
                    {mcpToolPermissionsDraft ? (
                      <span className="settings-mcp-stage-status">{mcpToolPermissionsDraft.tools.filter((tool) => tool.enabled).length}/{mcpToolPermissionsDraft.tools.length} tools enabled</span>
                    ) : null}
                  </div>

                  <div className="settings-mcp-capability-master-grid">
                    <label className={mcpSettingsSaving ? "settings-toggle-row is-disabled is-saving" : !mcpDraft.enabled ? "settings-toggle-row is-disabled" : "settings-toggle-row"}>
                      <span className="settings-toggle-copy"><strong>Read tools</strong><span>Permit inventory, Project, and Reservation inspection tools.</span></span>
                      <input type="checkbox" role="switch" checked={mcpDraft.read_tools_enabled} disabled={!mcpDraft.enabled || mcpSettingsSaving} onChange={(event) => updateMcpDraft("read_tools_enabled", event.target.checked)} />
                      <span className="settings-switch" aria-hidden="true" />
                    </label>
                    <label className={mcpSettingsSaving ? "settings-toggle-row is-disabled is-saving" : !mcpDraft.enabled ? "settings-toggle-row is-disabled" : "settings-toggle-row"}>
                      <span className="settings-toggle-copy"><strong>Safeguarded writes</strong><span>Allow eligible clients to request <code>mcp:write</code>. Every write still requires its own policy, preview and confirmation.</span></span>
                      <input type="checkbox" role="switch" checked={mcpDraft.write_tools_enabled} disabled={!mcpDraft.enabled || mcpSettingsSaving} onChange={(event) => updateMcpDraft("write_tools_enabled", event.target.checked)} />
                      <span className="settings-switch" aria-hidden="true" />
                    </label>
                  </div>

                  <div
                    className={!mcpDraft.enabled ? "settings-mcp-tool-permissions settings-mcp-tool-catalogues is-disabled" : "settings-mcp-tool-permissions settings-mcp-tool-catalogues"}
                    data-partpilot-mcp-tool-permissions="PARTPILOT:MCP_WRITE_TOOL_PERMISSIONS_UI:V734"
                    aria-disabled={!mcpDraft.enabled}
                  >
                    <div className="settings-mcp-permission-heading">
                      <div>
                        <strong>Per-tool policy</strong>
                        <span>These are global ceilings for every MCP client. Client-specific permissions can inherit or deny, never override a global block.</span>
                      </div>
                    </div>
                    {mcpToolPermissionsLoading && !mcpToolPermissionsDraft ? <p className="settings-mcp-permission-state" role="status">Loading tool permissions...</p> : null}
                    {mcpToolPermissionsDraft ? (
                      <div className="settings-mcp-disclosure-list">
                        <details className="settings-mcp-tool-disclosure">
                          <summary className="settings-mcp-tool-disclosure-summary">
                            <span className="settings-mcp-disclosure-copy"><strong>Read tool catalogue</strong><span>6 inventory, Project, and Reservation inspection tools</span></span>
                            <span className="settings-mcp-permission-count">{mcpToolPermissionsDraft.tools.filter((tool) => tool.capability === "read" && tool.enabled).length}/{mcpToolPermissionsDraft.tools.filter((tool) => tool.capability === "read").length} enabled</span>
                            <span className="settings-mcp-disclosure-chevron" aria-hidden="true">⌄</span>
                          </summary>
                          <div className="settings-mcp-tool-disclosure-body">
                            <div className="settings-mcp-tool-permission-list">
                              {mcpToolPermissionsDraft.tools.filter((tool) => tool.capability === "read").map((tool) => {
                                const disabled = !mcpDraft.enabled || !mcpDraft.read_tools_enabled || mcpToolPermissionsSaving;
                                return (
                                  <label className={mcpToolPermissionsSaving ? "settings-toggle-row settings-mcp-tool-row is-disabled is-saving" : disabled ? "settings-toggle-row settings-mcp-tool-row is-disabled" : "settings-toggle-row settings-mcp-tool-row"} key={tool.name}>
                                    <span className="settings-toggle-copy"><strong>{tool.label}</strong><span><code>{tool.name}</code> · Read tool</span></span>
                                    <input type="checkbox" role="switch" checked={tool.enabled} disabled={disabled} onChange={(event) => updateMcpToolPermissionDraft(tool.name, event.target.checked)} />
                                    <span className="settings-switch" aria-hidden="true" />
                                  </label>
                                );
                              })}
                            </div>
                            {!mcpDraft.enabled || !mcpDraft.read_tools_enabled ? <p className="settings-mcp-permission-state">Enable the MCP server and Read tools to edit read-tool permissions.</p> : null}
                          </div>
                        </details>

                        <details className="settings-mcp-tool-disclosure is-write" data-partpilot-mcp-write-tool-catalogue="PARTPILOT:MCP_WRITE_TOOL_CATALOGUE:V734">
                          <summary className="settings-mcp-tool-disclosure-summary">
                            <span className="settings-mcp-disclosure-copy"><strong>Safeguarded write catalogue</strong><span>8 confirmed inventory and lifecycle mutation tools</span></span>
                            <span className="settings-mcp-permission-count">{mcpToolPermissionsDraft.tools.filter((tool) => tool.capability === "write" && tool.enabled).length}/{mcpToolPermissionsDraft.tools.filter((tool) => tool.capability === "write").length} enabled</span>
                            <span className="settings-mcp-disclosure-chevron" aria-hidden="true">⌄</span>
                          </summary>
                          <div className="settings-mcp-tool-disclosure-body">
                            <p className="settings-mcp-write-safeguard-note">Every write uses an exact preview, five-minute one-time confirmation token, idempotency, active backing-user authority, and canonical transactional rules.</p>
                            <div className="settings-mcp-tool-permission-list">
                              {mcpToolPermissionsDraft.tools.filter((tool) => tool.capability === "write").map((tool) => {
                                const disabled = !mcpDraft.enabled || !mcpDraft.write_tools_enabled || mcpToolPermissionsSaving;
                                return (
                                  <label className={mcpToolPermissionsSaving ? "settings-toggle-row settings-mcp-tool-row is-disabled is-saving" : disabled ? "settings-toggle-row settings-mcp-tool-row is-disabled" : "settings-toggle-row settings-mcp-tool-row"} key={tool.name}>
                                    <span className="settings-toggle-copy"><strong>{tool.label}</strong><span><code>{tool.name}</code> · Safeguarded write tool</span></span>
                                    <input type="checkbox" role="switch" checked={tool.enabled} disabled={disabled} onChange={(event) => updateMcpToolPermissionDraft(tool.name, event.target.checked)} />
                                    <span className="settings-switch" aria-hidden="true" />
                                  </label>
                                );
                              })}
                            </div>
                            {!mcpDraft.enabled || !mcpDraft.write_tools_enabled ? <p className="settings-mcp-permission-state is-caution">Enable the MCP server and Safeguarded writes before any write-tool permission can be enabled. No-auth clients remain read-only.</p> : null}
                          </div>
                        </details>
                      </div>
                    ) : null}
                    {mcpToolPermissionsError ? <div className="settings-preference-state is-error" role="alert"><span>{mcpToolPermissionsError}</span>{!mcpToolPermissionsDraft ? <button type="button" onClick={() => setMcpToolPermissionsReloadVersion((value) => value + 1)}>Retry</button> : null}</div> : null}
                    {mcpToolPermissionsSaving && !mcpToolPermissionsError ? <p className="settings-preference-state" role="status">Saving tool permission automatically...</p> : null}
                    {mcpToolPermissionsSaved && !mcpToolPermissionsError ? <p className="settings-preference-state is-success" role="status" data-feedback-version="consistent-autosave-feedback-v751">MCP tool permission saved automatically.</p> : null}
                  </div>
                </section>

                <section className={!mcpDraft.enabled ? "settings-mcp-stage settings-mcp-stage-connections is-disabled" : "settings-mcp-stage settings-mcp-stage-connections"} aria-labelledby="settings-mcp-connections-stage-title" aria-disabled={!mcpDraft.enabled}>
                  <div className="settings-mcp-stage-heading">
                    <SettingsStageIcon name="connections" />
                    <div>
                      <span className="settings-mcp-stage-kicker">Connections</span>
                      <h3 id="settings-mcp-connections-stage-title">How clients authenticate</h3>
                      <p>OAuth applications and named direct clients share the same MCP server and global tool policy, but use separate credentials.</p>
                    </div>
                  </div>

                  <div className={!mcpDraft.enabled ? "settings-mcp-subordinate settings-mcp-connection-stack is-disabled" : "settings-mcp-subordinate settings-mcp-connection-stack"} aria-disabled={!mcpDraft.enabled}>
                    <div className="settings-mcp-connection-panel settings-mcp-oauth-clients" data-partpilot-mcp-oauth-clients="PARTPILOT:MCP_OAUTH_MANUAL_REGISTRATION_UI:V569">
                      <div className="settings-mcp-connection-method-heading settings-mcp-oauth-heading">
                        <div><span className="settings-mcp-connection-type">OAuth 2.1</span><strong>OAuth applications</strong><span>For clients that can complete browser authorization and refresh tokens. Confidential client secrets are shown only once when created.</span></div>
                        <div className="settings-mcp-oauth-heading-actions"><button className="settings-action settings-action-primary" type="button" disabled={mcpOAuthRegistering} onClick={mcpOAuthRegisterOpen ? closeMcpOAuthRegistration : openMcpOAuthRegistration}>{mcpOAuthRegisterOpen ? "Close form" : "Register client"}</button></div>
                      </div>

                      {mcpOAuthRegisterOpen ? (
                        <div className="settings-mcp-oauth-register-form">
                          <div className="settings-mcp-oauth-register-heading"><div><strong>Manual OAuth registration</strong><span>Add the redirect URI supplied by your MCP client. Part Pilot fixes the authorization-code and refresh-token grant types automatically.</span></div></div>
                          <div className="settings-mcp-oauth-register-grid">
                            <label><span>Client name</span><input type="text" value={mcpOAuthClientNameDraft} maxLength={200} autoComplete="off" disabled={mcpOAuthRegistering} aria-invalid={mcpOAuthRegisterAttempted && Boolean(mcpOAuthClientNameError)} placeholder="Claude Desktop" onChange={(event) => { setMcpOAuthClientNameDraft(event.target.value); setMcpOAuthRegisterError(null); }} /></label>
                            <label><span>Client type</span><select value={mcpOAuthClientTypeDraft} disabled={mcpOAuthRegistering} onChange={(event) => chooseMcpOAuthClientType(event.target.value as McpOAuthClientType)}><option value="public">Public</option><option value="confidential">Confidential</option></select></label>
                            <label className="settings-mcp-oauth-register-wide"><span>Redirect URIs</span><textarea value={mcpOAuthRedirectUrisDraft} rows={3} autoComplete="off" spellCheck={false} disabled={mcpOAuthRegistering} aria-invalid={mcpOAuthRegisterAttempted && Boolean(mcpOAuthRedirectUrisError)} placeholder={"https://client.example/oauth/callback\nhttp://127.0.0.1:8765/callback"} onChange={(event) => { setMcpOAuthRedirectUrisDraft(event.target.value); setMcpOAuthRegisterError(null); }} /><small>One URI per line, maximum 20.</small></label>
                            <label><span>Token authentication</span><select value={mcpOAuthAuthMethodDraft} disabled={mcpOAuthRegistering || mcpOAuthClientTypeDraft === "public"} onChange={(event) => { setMcpOAuthAuthMethodDraft(event.target.value as McpOAuthTokenEndpointAuthMethod); setMcpOAuthRegisterError(null); }}>{mcpOAuthClientTypeDraft === "public" ? <option value="none">None</option> : <><option value="client_secret_post">Client secret POST</option><option value="client_secret_basic">Client secret Basic</option></>}</select></label>
                          </div>
                          {mcpOAuthDisplayedRegistrationError ? <p className="form-error" role="alert">{mcpOAuthDisplayedRegistrationError}</p> : null}
                          <div className="settings-mcp-oauth-register-actions"><button className="settings-action settings-action-secondary" type="button" disabled={mcpOAuthRegistering} onClick={closeMcpOAuthRegistration}>Cancel</button><button className="settings-action settings-action-primary" type="button" disabled={mcpOAuthRegistering} onClick={() => void submitMcpOAuthRegistration()}>{mcpOAuthRegistering ? "Registering..." : "Register OAuth client"}</button></div>
                        </div>
                      ) : null}

                      {mcpOAuthClientsLoading && !mcpOAuthClients ? <p className="settings-mcp-oauth-state" role="status">Loading OAuth clients...</p> : null}
                      {mcpOAuthVisibleClients && mcpOAuthVisibleClients.length > 0 ? (
                        <div className="settings-mcp-oauth-list">
                          {mcpOAuthVisibleClients.map((client) => (
                            <article className={`settings-mcp-oauth-client is-${client.status}`} key={client.database_id}>
                              <header><div><strong>{client.client_name}</strong><span>{client.client_type === "confidential" ? "Confidential OAuth client" : "Public OAuth client"}</span></div><span className={`settings-mcp-oauth-status is-${client.status}`}>{client.status === "connected" ? "Connected" : client.status === "registered" ? "Registered" : "Revoked"}</span></header>
                              <dl><div><dt>Origin</dt><dd>{client.redirect_origins.length > 0 ? client.redirect_origins.join(", ") : "No web origin"}</dd></div><div><dt>Auth</dt><dd>{client.token_endpoint_auth_method === "none" ? "None" : client.token_endpoint_auth_method === "client_secret_basic" ? "Client secret Basic" : "Client secret POST"}</dd></div><div><dt>Created</dt><dd>{formatUtc(client.created_at, timezone)}</dd></div><div><dt>Connected</dt><dd>{client.connected_at ? formatUtc(client.connected_at, timezone) : "Not yet"}</dd></div></dl>
                              <footer><span>{client.status === "connected" ? `${client.active_token_count} active session${client.active_token_count === 1 ? "" : "s"}` : client.status === "registered" ? "Awaiting first authorization" : "Registration disabled"} · {client.tool_permissions.filter((tool) => tool.effective_enabled).length}/{client.tool_permissions.length} allowed by policy{client.status === "connected" ? " · OAuth scopes can further limit active tools" : ""}</span>{client.status !== "revoked" ? <div className="settings-mcp-oauth-actions"><button className="settings-action settings-action-secondary" type="button" disabled={mcpOAuthRevokingId !== null || mcpOAuthPermissionSaving} onClick={() => openMcpOAuthPermissions(client)}>Permissions</button><button className="settings-action settings-action-danger" type="button" disabled={mcpOAuthRevokingId !== null || mcpOAuthPermissionSaving} onClick={() => openMcpOAuthRevokeDialog(client)}>{client.status === "connected" ? "Revoke access" : "Revoke client"}</button></div> : null}</footer>
                            </article>
                          ))}
                        </div>
                      ) : null}
                      {mcpOAuthVisibleClients?.length === 0 ? <p className="settings-mcp-oauth-state">No active OAuth clients are registered or connected.</p> : null}
                      {mcpOAuthClientsError ? <div className="settings-preference-state is-error" role="alert"><span>{mcpOAuthClientsError}</span>{!mcpOAuthClients ? <button type="button" onClick={() => setMcpOAuthReloadVersion((value) => value + 1)}>Retry</button> : null}</div> : null}
                      {mcpOAuthClientsMessage && !mcpOAuthClientsError ? <p className="settings-preference-state is-success" role="status">{mcpOAuthClientsMessage}</p> : null}
                    </div>

                    {mcpOAuthPermissionTarget ? (
                      <McpClientPermissionsDialog
                        key={`oauth-${mcpOAuthPermissionTarget.database_id}`}
                        clientName={mcpOAuthPermissionTarget.client_name}
                        deniedTools={mcpOAuthPermissionTarget.denied_tools}
                        tools={mcpOAuthPermissionTarget.tool_permissions}
                        saving={mcpOAuthPermissionSaving}
                        error={mcpOAuthPermissionError}
                        onClose={() => { if (mcpOAuthPermissionSaving) return; setMcpOAuthPermissionTarget(null); setMcpOAuthPermissionError(null); }}
                        onSave={(deniedTools) => void saveMcpOAuthPermissions(deniedTools)}
                      />
                    ) : null}

                    <div className="settings-mcp-connection-panel settings-mcp-direct-access" data-partpilot-mcp-direct-access-hierarchy="PARTPILOT:MCP_DIRECT_ACCESS_HIERARCHY:V663">
                      <div className="settings-mcp-connection-method-heading settings-mcp-direct-access-heading">
                        <div><span className="settings-mcp-connection-type">Direct</span><strong>Named direct clients</strong><span>For Bearer, custom-header, or trusted-network clients that connect without an OAuth browser flow.</span></div>
                      </div>
                      <label className={mcpSettingsSaving ? "settings-toggle-row is-disabled is-saving" : !mcpDraft.enabled ? "settings-toggle-row is-disabled" : "settings-toggle-row"}>
                        <span className="settings-toggle-copy"><strong>Allow direct MCP clients</strong><span>Enable credentialed named direct clients alongside OAuth.</span></span>
                        <input type="checkbox" role="switch" checked={mcpDraft.direct_clients_enabled} disabled={!mcpDraft.enabled || mcpSettingsSaving} onChange={(event) => updateMcpDraft("direct_clients_enabled", event.target.checked)} />
                        <span className="settings-switch" aria-hidden="true" />
                      </label>
                      <McpDirectClientsSection token={token ?? ""} disabled={!mcpDraft.enabled || !mcpDraft.direct_clients_enabled} permissionReloadVersion={mcpPermissionRefreshVersion} />
                    </div>
                  </div>
                </section>

                <section className={!mcpDraft.enabled ? "settings-mcp-stage settings-mcp-stage-advanced is-disabled" : "settings-mcp-stage settings-mcp-stage-advanced"} aria-labelledby="settings-mcp-advanced-stage-title" aria-disabled={!mcpDraft.enabled}>
                  <div className="settings-mcp-stage-heading">
                    <SettingsStageIcon name="advanced" />
                    <div>
                      <span className="settings-mcp-stage-kicker">Advanced access</span>
                      <h3 id="settings-mcp-advanced-stage-title">Anonymous fallback</h3>
                      <p>This mode is intentionally separated from normal connection methods because it removes credential checks for reachable read clients.</p>
                    </div>
                    <span className={mcpDraft.direct_no_auth_enabled ? "settings-mcp-stage-status is-danger" : "settings-mcp-stage-status"}>{mcpDraft.direct_no_auth_enabled ? "Enabled" : "Off"}</span>
                  </div>
                  <div className="settings-mcp-risk-panel">
                    <label className={mcpSettingsSaving ? "settings-toggle-row settings-mcp-no-auth-row is-disabled is-saving" : !mcpDraft.enabled || !mcpDraft.direct_clients_enabled ? "settings-toggle-row settings-mcp-no-auth-row is-disabled" : "settings-toggle-row settings-mcp-no-auth-row"}>
                      <span className="settings-toggle-copy"><strong>No authentication</strong><span>Dangerous read-only fallback. Any reachable client may use allowed MCP read tools without credentials.</span></span>
                      <input type="checkbox" role="switch" checked={mcpDraft.direct_no_auth_enabled} disabled={!mcpDraft.enabled || !mcpDraft.direct_clients_enabled || mcpSettingsSaving} onChange={(event) => requestMcpNoAuth(event.target.checked)} />
                      <span className="settings-switch" aria-hidden="true" />
                    </label>
                    {!mcpDraft.direct_clients_enabled ? <p className="settings-mcp-risk-helper">Direct clients must be enabled before anonymous fallback can be changed.</p> : null}
                    {mcpDraft.direct_no_auth_enabled ? <div className="settings-mcp-no-auth-warning" role="status"><strong>No authentication is enabled.</strong><span>Access remains read-only and is still gated by the MCP server, Read tools and individual read-tool permissions. Last resolved source: {mcpDraft.direct_no_auth_last_client_ip ?? "Not used yet"}.</span></div> : null}
                  </div>
                </section>
              </div>

              {mcpSettingsSaving && !mcpSettingsError ? (
                <p className="settings-preference-state" role="status">
                  Saving MCP access automatically...
                </p>
              ) : null}
            </>
          ) : null}

          {mcpSettingsError ? (
            <div
              className="settings-preference-state is-error"
              role="alert"
            >
              <span>{mcpSettingsError}</span>
              {!mcpDraft ? (
                <button
                  type="button"
                  onClick={() =>
                    setMcpReloadVersion((value) => value + 1)
                  }
                >
                  Retry
                </button>
              ) : null}
            </div>
          ) : null}

          {mcpSettingsSaved && !mcpSettingsError ? (
            <p
              className="settings-preference-state is-success"
              role="status"
            >
              MCP access settings saved automatically.
            </p>
          ) : null}
        </section>
        ) : null}

        {canAdministerWorkspace ? (
        <section
          id="settings-data"
          data-partpilot-background-refresh="PARTPILOT:STABLE_BACKGROUND_REFRESH:V718"
          className="card settings-section settings-data-section settings-grid-data"
          aria-labelledby="settings-data-title"
          hidden={activeSettingsSection !== "data"}
        >
          <div className="settings-section-heading">
            <div>
              <span className="card-label">Local data</span>
              <h2 id="settings-data-title">
                {isPrimaryOwner ? "Backup and restore" : "Backup"}
              </h2>
              <p>
                {isPrimaryOwner
                  ? "Download a complete portable backup or validate and restore a previous Part Pilot backup."
                  : "Download a complete portable backup. Restore and database reset are reserved for the primary Owner."}
              </p>
            </div>
          </div>

          <div className="settings-data-actions">
            <article className="settings-data-action settings-unified-stage">
              <div className="settings-data-stage-heading settings-unified-stage-heading">
                <SettingsStageIcon name="backup" />
                <div>
                  <span className="card-label">Backup</span>
                  <h3>Download backup</h3>
                  <p>
                    Creates a validated snapshot while Part Pilot remains
                    available. The download contains the database and manifest.
                  </p>
                </div>
              </div>
              <div
                className="settings-backup-status"
                data-partpilot-backup-status="PARTPILOT:SETTINGS_MANUAL_BACKUP_STATUS_UI:V454"
              >
                {backupStatusLoading ? (
                  <p
                    className="settings-backup-status-state"
                    role="status"
                  >
                    Loading manual backup history...
                  </p>
                ) : backupStatusError ? (
                  <div
                    className="settings-backup-status-error"
                    role="alert"
                  >
                    <span>{backupStatusError}</span>
                    <button
                      className="settings-action settings-action-secondary"
                      type="button"
                      onClick={() =>
                        setBackupStatusReloadVersion(
                          (value) => value + 1
                        )
                      }
                    >
                      Retry
                    </button>
                  </div>
                ) : backupStatus?.latest_manual_backup ? (
                  <>
                    <div className="settings-backup-status-heading">
                      <strong>Latest manual download</strong>
                      <span>
                        {backupStatus.recorded_download_count} recorded
                      </span>
                    </div>
                    <dl className="settings-backup-status-summary">
                      <div>
                        <dt>Generated</dt>
                        <dd>
                          {formatUtc(
                            backupStatus.latest_manual_backup
                              .generated_at_utc,
                            timezone
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt>Archive</dt>
                        <dd>
                          {formatFileSize(
                            backupStatus.latest_manual_backup
                              .archive_size_bytes
                          )}
                        </dd>
                      </div>
                      <div className="settings-backup-status-file">
                        <dt>File</dt>
                        <dd>
                          {backupStatus.latest_manual_backup.filename}
                        </dd>
                      </div>
                      <div>
                        <dt>Database</dt>
                        <dd>
                          {formatFileSize(
                            backupStatus.latest_manual_backup
                              .database_size_bytes
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt>Schema</dt>
                        <dd>
                          {
                            backupStatus.latest_manual_backup
                              .alembic_revision
                          }
                        </dd>
                      </div>
                    </dl>
                    <p className="settings-backup-status-note">
                      Manual only. Scheduling is inactive and no server
                      copy is retained.
                    </p>
                  </>
                ) : (
                  <>
                    <strong>No recorded manual downloads</strong>
                    <p className="settings-backup-status-note">
                      Backups are generated only when downloaded.
                      Scheduling is inactive and no server copy is
                      retained.
                    </p>
                  </>
                )}
              </div>
              <button
                className="settings-action settings-action-primary"
                type="button"
                disabled={!token || backupDownloading}
                onClick={() => void handleBackupDownload()}
              >
                {backupDownloading
                  ? "Preparing backup..."
                  : "Download backup"}
              </button>
              <p
                className={
                  backupError
                    ? "settings-data-action-status is-error"
                    : backupMessage
                      ? "settings-data-action-status is-success"
                      : "settings-data-action-status"
                }
                role={backupError ? "alert" : "status"}
              >
                {backupError ?? backupMessage ?? "Versioned .ppbackup file"}
              </p>
            </article>

            {isPrimaryOwner ? (
            <article className="settings-data-action settings-unified-stage">
              <div className="settings-data-stage-heading settings-unified-stage-heading">
                <SettingsStageIcon name="restore" />
                <div>
                  <span className="card-label">Restore</span>
                  <h3>Restore backup</h3>
                  <p>
                    Validate a backup before review. Restoring restarts Part
                    Pilot, replaces local data, and signs out every session.
                  </p>
                </div>
              </div>
              <input
                ref={restoreFileInputRef}
                type="file"
                accept=".ppbackup,application/vnd.partpilot.backup+zip,application/zip"
                hidden
                onChange={(event) =>
                  chooseRestoreFile(event.currentTarget.files?.[0] ?? null)
                }
              />
              {restoreFile ? (
                <div className="settings-restore-file">
                  <strong>{restoreFile.name}</strong>
                  <span>{formatFileSize(restoreFile.size)}</span>
                </div>
              ) : null}
              <div className="settings-data-action-buttons">
                <button
                  className="settings-action settings-action-secondary"
                  type="button"
                  disabled={restoreValidating}
                  onClick={() => restoreFileInputRef.current?.click()}
                >
                  {restoreFile ? "Choose another file" : "Choose backup file"}
                </button>
                <button
                  className="settings-action settings-action-primary"
                  type="button"
                  disabled={!restoreFile || restoreValidating || !token}
                  onClick={() => void reviewRestoreBackup()}
                >
                  {restoreValidating
                    ? "Validating backup..."
                    : "Validate and review"}
                </button>
                {restoreFile ? (
                  <button
                    className="settings-action settings-action-secondary"
                    type="button"
                    disabled={restoreValidating}
                    onClick={clearRestoreSelection}
                  >
                    Clear
                  </button>
                ) : null}
              </div>
              <p
                className={
                  restoreError
                    ? "settings-data-action-status is-error"
                    : "settings-data-action-status"
                }
                role={restoreError ? "alert" : "status"}
              >
                {restoreError ?? "Maximum upload size: 256 MiB"}
              </p>
            </article>
            ) : null}
          </div>

          {isPrimaryOwner ? (<>
          <div className="settings-data-reset-stage settings-unified-stage">
            <div className="settings-data-reset-heading settings-unified-stage-heading">
              <SettingsStageIcon name="reset" />
              <div>
                <span className="card-label">Danger zone</span>
                <h3>Database reset</h3>
                <p>Erase this installation and return to first-run setup.</p>
              </div>
              <span className="settings-danger-badge">Permanent action</span>
            </div>

            <div className="settings-danger-summary">
            <p>
              This deletes the owner account, sessions, inventory,
              Projects, Reservations, History, and application settings.
              Files outside the database are not removed.
            </p>
            <button
              className="danger-button settings-danger-launch"
              type="button"
              onClick={openDatabaseResetDialog}
            >
              Review database reset
            </button>
            </div>
          </div>
          </>) : null}
        </section>
        ) : null}
      </div>

      {canAdministerWorkspace && mcpNoAuthDialogOpen ? (
        <div className="settings-security-dialog-backdrop" data-partpilot-mcp-no-auth-dialog="PARTPILOT:MCP_NO_AUTH_CONFIRMATION_DIALOG:V627">
          <section className="settings-security-dialog is-danger" role="dialog" aria-modal="true" aria-labelledby="settings-mcp-no-auth-title" aria-describedby="settings-mcp-no-auth-description">
            <header><span className="card-label">MCP security</span><h2 id="settings-mcp-no-auth-title">Enable MCP without authentication?</h2></header>
            <div className="settings-security-dialog-content">
              <p id="settings-mcp-no-auth-description">Any device that can reach the MCP endpoint will be able to use enabled read tools without OAuth, a key, or a trusted-network identity. Write tools remain unavailable in this build.</p>
              <label className="settings-security-credential-field" htmlFor="settings-mcp-no-auth-confirmation"><span>Type ALLOW NO AUTH to continue</span><input id="settings-mcp-no-auth-confirmation" type="text" value={mcpNoAuthConfirmation} autoComplete="off" spellCheck={false} onChange={(event) => setMcpNoAuthConfirmation(event.target.value)} /></label>
            </div>
            <footer><button className="settings-action settings-action-secondary" type="button" onClick={() => { setMcpNoAuthDialogOpen(false); setMcpNoAuthConfirmation(""); }}>Cancel</button><button className="settings-action settings-action-danger" type="button" disabled={!mcpNoAuthConfirmationReady} onClick={confirmMcpNoAuth}>Enable no authentication</button></footer>
          </section>
        </div>
      ) : null}

      {canAdministerWorkspace && mcpOAuthCredential ? (
        <div className="settings-mcp-oauth-backdrop" data-partpilot-mcp-oauth-credential-dialog="PARTPILOT:MCP_OAUTH_ONE_TIME_CREDENTIAL_DIALOG:V569">
          <section className="settings-mcp-oauth-dialog settings-mcp-oauth-credential-dialog" role="dialog" aria-modal="true" aria-labelledby="settings-mcp-oauth-credential-title" aria-describedby="settings-mcp-oauth-credential-description">
            <header><p className="eyebrow">OAuth client registered</p><h2 id="settings-mcp-oauth-credential-title">Save {mcpOAuthCredential.client_name} credentials</h2></header>
            <div className="settings-mcp-oauth-dialog-content">
              <p id="settings-mcp-oauth-credential-description">Copy these values into the client now.{mcpOAuthCredential.client_secret ? " The client secret is shown only in this result and cannot be retrieved later." : " This public client does not use a client secret."}</p>
              <div className="settings-mcp-oauth-credential-field"><label htmlFor="settings-mcp-oauth-client-id">Client ID</label><div className="settings-copy-field"><input id="settings-mcp-oauth-client-id" type="text" value={mcpOAuthCredential.client_id} readOnly spellCheck={false} autoComplete="off" onFocus={(event) => event.currentTarget.select()} /><span className="settings-copy-field-actions"><button type="button" onClick={() => void copyMcpOAuthCredential(mcpOAuthCredential.client_id, "client_id")}>{mcpOAuthCredentialCopied === "client_id" ? "Copied" : "Copy"}</button></span></div></div>
              {mcpOAuthCredential.client_secret ? <div className="settings-mcp-oauth-credential-field is-secret"><label htmlFor="settings-mcp-oauth-client-secret">Client secret</label><div className="settings-copy-field"><input id="settings-mcp-oauth-client-secret" type={mcpOAuthSecretVisible ? "text" : "password"} value={mcpOAuthCredential.client_secret} readOnly spellCheck={false} autoComplete="off" onFocus={(event) => event.currentTarget.select()} /><span className="settings-copy-field-actions"><button type="button" onClick={() => setMcpOAuthSecretVisible((value) => !value)}>{mcpOAuthSecretVisible ? "Hide" : "Show"}</button><button type="button" onClick={() => void copyMcpOAuthCredential(mcpOAuthCredential.client_secret ?? "", "client_secret")}>{mcpOAuthCredentialCopied === "client_secret" ? "Copied" : "Copy"}</button></span></div></div> : null}
              <dl><div><dt>Record</dt><dd>#{mcpOAuthCredential.database_id}</dd></div><div><dt>Client type</dt><dd>{mcpOAuthCredential.client_type === "public" ? "Public" : "Confidential"}</dd></div><div><dt>Token auth</dt><dd>{mcpOAuthCredential.token_endpoint_auth_method}</dd></div><div><dt>Redirect URI</dt><dd>{mcpOAuthCredential.redirect_uris.join(", ")}</dd></div><div><dt>Created</dt><dd>{formatUtc(mcpOAuthCredential.created_at, timezone)}</dd></div></dl>
              {mcpOAuthCredential.client_secret ? <p className="settings-mcp-oauth-secret-warning">Closing this result permanently removes the plaintext secret from this page. Part Pilot stores only its digest.</p> : null}
            </div>
            <footer><button className="settings-action settings-action-primary" type="button" autoFocus onClick={closeMcpOAuthCredentialDialog}>I saved the credentials</button></footer>
          </section>
        </div>
      ) : null}

      {canAdministerWorkspace && mcpOAuthRevokeTarget ? (
        <div className="settings-mcp-oauth-backdrop" data-partpilot-mcp-oauth-revoke-dialog="PARTPILOT:MCP_OAUTH_CLIENT_REVOKE_DIALOG:V569">
          <section className="settings-mcp-oauth-dialog" role="dialog" aria-modal="true" aria-labelledby="settings-mcp-oauth-dialog-title" aria-describedby="settings-mcp-oauth-dialog-description">
            <header><p className="eyebrow">{mcpOAuthRevokeTarget.status === "connected" ? "Connected OAuth client" : "Registered OAuth client"}</p><h2 id="settings-mcp-oauth-dialog-title">Revoke {mcpOAuthRevokeTarget.client_name}?</h2></header>
            <div className="settings-mcp-oauth-dialog-content"><p id="settings-mcp-oauth-dialog-description">{mcpOAuthRevokeTarget.status === "connected" ? "The client will be disconnected immediately. Active tokens and consent will stop working, but Part Pilot data will not be removed." : "This registration will be disabled before its first authorization. Part Pilot data will not be removed."}</p><dl><div><dt>Client</dt><dd>{mcpOAuthRevokeTarget.client_name}</dd></div><div><dt>Origin</dt><dd>{mcpOAuthRevokeTarget.redirect_origins.join(", ")}</dd></div><div><dt>Status</dt><dd>{mcpOAuthRevokeTarget.status === "connected" ? "Connected" : "Registered"}</dd></div><div><dt>Last used</dt><dd>{mcpOAuthRevokeTarget.last_used_at ? formatUtc(mcpOAuthRevokeTarget.last_used_at, timezone) : "Never"}</dd></div></dl><p className="settings-mcp-oauth-warning">{mcpOAuthRevokeTarget.status === "connected" ? "Confirming this action may interrupt an active request from this client." : "Confirming this action permanently disables this registration."}</p>{mcpOAuthRevokeError ? <p className="form-error" role="alert">{mcpOAuthRevokeError}</p> : null}</div>
            <footer><button className="settings-action settings-action-secondary" type="button" autoFocus disabled={mcpOAuthRevokingId !== null} onClick={closeMcpOAuthRevokeDialog}>Keep client</button><button className="settings-action settings-action-danger" type="button" disabled={mcpOAuthRevokingId !== null} onClick={() => void confirmMcpOAuthRevocation()}>{mcpOAuthRevokingId !== null ? "Revoking..." : mcpOAuthRevokeTarget.status === "connected" ? "Revoke access" : "Revoke client"}</button></footer>
          </section>
        </div>
      ) : null}

      {isPrimaryOwner && restoreDialogOpen && restoreValidation ? (
        <div
          className="settings-restore-backdrop"
          data-partpilot-restore-dialog="PARTPILOT:SETTINGS_RESTORE_REVIEW_DIALOG:V442"
        >
          <section
            className="settings-restore-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="settings-restore-dialog-title"
            aria-describedby="settings-restore-dialog-description"
          >
            <header>
              <p className="eyebrow">Validated backup</p>
              <h2 id="settings-restore-dialog-title">
                Review database restore
              </h2>
            </header>
            <div className="settings-restore-dialog-content">
              {restoreRestarting ? (
                <div className="settings-restore-progress" role="status">
                  <strong>Restarting Part Pilot</strong>
                  <div className="settings-restore-pulse" aria-hidden="true" />
                  <p>
                    The database is being restored and all sessions are
                    being invalidated. This page returns to sign-in when
                    Part Pilot is ready.
                  </p>
                </div>
              ) : (
                <>
                  <p id="settings-restore-dialog-description">
                    The backup passed archive, schema, integrity, and
                    active-user checks. Confirm the details before Part
                    Pilot restarts and replaces its database.
                  </p>
                  <dl className="settings-restore-summary">
                    <div>
                      <dt>File</dt>
                      <dd>{restoreValidation.original_filename}</dd>
                    </div>
                    <div>
                      <dt>Backup created</dt>
                      <dd>{formatUtc(restoreValidation.backup_created_at_utc, timezone)}</dd>
                    </div>
                    <div>
                      <dt>Database size</dt>
                      <dd>{formatFileSize(restoreValidation.database_size_bytes)}</dd>
                    </div>
                    <div>
                      <dt>Users</dt>
                      <dd>
                        {restoreValidation.user_count} total,{" "}
                        {restoreValidation.active_user_count} active
                      </dd>
                    </div>
                    <div>
                      <dt>Schema</dt>
                      <dd>{restoreValidation.alembic_revision}</dd>
                    </div>
                    <div>
                      <dt>Review expires</dt>
                      <dd>{formatUtc(restoreValidation.expires_at_utc, timezone)}</dd>
                    </div>
                  </dl>
                  {restoreValidation.warnings.map((warning) => (
                    <p className="settings-restore-warning" key={warning}>
                      {warning}
                    </p>
                  ))}
                  <p className="settings-restore-warning">
                    Restoring replaces the current database, restarts Part
                    Pilot, and signs out every device. Download a fresh
                    backup first if the current data may be needed.
                  </p>
                  <label className="settings-restore-confirmation">
                    <span>
                      Type <code>{RESTORE_CONFIRMATION}</code> to continue
                    </span>
                    <input
                      type="text"
                      value={restoreConfirmation}
                      onChange={(event) => {
                        setRestoreConfirmation(event.target.value);
                        setRestoreError(null);
                      }}
                      placeholder={RESTORE_CONFIRMATION}
                      autoComplete="off"
                      spellCheck={false}
                      autoFocus
                      disabled={restoreCommitting}
                      aria-invalid={Boolean(restoreError)}
                    />
                  </label>
                  {restoreError ? (
                    <p className="form-error" role="alert">
                      {restoreError}
                    </p>
                  ) : null}
                </>
              )}
            </div>
            <footer>
              {!restoreRestarting ? (
                <>
                  <button
                    className="settings-action settings-action-secondary"
                    type="button"
                    disabled={restoreCommitting}
                    onClick={closeRestoreDialog}
                  >
                    Keep current database
                  </button>
                  <button
                    className="danger-button"
                    type="button"
                    disabled={!canCommitRestore}
                    onClick={() => void confirmRestoreBackup()}
                  >
                    {restoreCommitting
                      ? "Scheduling restore..."
                      : "Restart and restore backup"}
                  </button>
                </>
              ) : null}
            </footer>
          </section>
        </div>
      ) : null}

      {canAdministerWorkspace && preferenceResetTarget ? (
        <div className="settings-reset-backdrop" data-partpilot-preference-reset-dialog="PARTPILOT:TARGETED_PREFERENCE_RESET_UI:V673">
          <section className="settings-reset-dialog is-preference-reset" role="dialog" aria-modal="true" aria-labelledby="settings-preference-reset-title" aria-describedby="settings-preference-reset-description">
            <header>
              <p className="eyebrow">Preference default</p>
              <h2 id="settings-preference-reset-title">Reset {preferenceResetTarget === "appearance" ? "Theme" : preferenceResetTarget === "inventory" ? "Inventory display" : "Reservation defaults"}?</h2>
            </header>
            <div className="settings-reset-dialog-content">
              <p id="settings-preference-reset-description">
                {preferenceResetTarget === "appearance" ? "Theme will return to Dark. Inventory and reservation preferences will not change." : preferenceResetTarget === "inventory" ? "Inventory display will return to separate out-of-stock results. Theme and reservation preferences will not change." : "New-reservation defaults will return to no automatic expiry. Existing reservations, theme, and inventory preferences will not change."}
              </p>
              <p className="settings-preference-preserved-copy">Accounts, credentials, MCP/API configuration, inventory data, Projects, Reservations, backups, and history are preserved.</p>
              {preferenceResetError ? <p className="form-error" role="alert">{preferenceResetError}</p> : null}
            </div>
            <footer>
              <button className="settings-action settings-action-secondary" type="button" disabled={preferenceResetting} onClick={closePreferenceResetDialog}>Keep current setting</button>
              <button className="settings-action" type="button" disabled={!canConfirmPreferenceReset} onClick={() => void confirmPreferenceReset()}>{preferenceResetting ? "Resetting..." : "Reset to default"}</button>
            </footer>
          </section>
        </div>
      ) : null}
    </div>
  );
}
