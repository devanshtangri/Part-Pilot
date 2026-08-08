import {
  useEffect,
  useRef,
  useState
} from "react";
import { useLocation } from "react-router-dom";

import {
  APPEARANCE_STORAGE_KEY,
  useAppearance
} from "../appearance/AppearanceContext";
import { useAuth } from "../auth/AuthContext";
import { ApiKeySettingsSection } from "../components/ApiKeySettingsSection";
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
  configureMcpDirectTrustedNetworks,
  disableMcpDirectAuth,
  getMcpDirectAuth,
  getMcpOAuthManageableClients,
  getMcpSettings,
  registerMcpOAuthClient,
  getReservationSettings,
  getSearchSettings,
  revealMcpDirectKey,
  revokeMcpOAuthClient,
  rotateMcpDirectBearerKey,
  rotateMcpDirectCustomHeaderKey,
  updateMcpSettings,
  updateReservationSettings,
  updateSearchSettings
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
  McpDirectAuthStatus,
  McpDirectSelectionMode,
  McpOAuthClientRegistrationResponse,
  McpOAuthClientType,
  McpOAuthManageableClientSummary,
  McpOAuthTokenEndpointAuthMethod,
  McpSettings,
  ReservationExpiryMode,
  ReservationSettings,
  SearchSettings
} from "../types/settings";
import "./Settings.css";

const RESET_CONFIRMATION = "RESET PART PILOT";
const RESTORE_CONFIRMATION = "RESTORE";
const MCP_CUSTOM_HEADER_DEFAULT = "x-partpilot-mcp-key";
const MCP_CUSTOM_HEADER_PATTERN = /^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$/;
const MCP_RESERVED_CUSTOM_HEADERS = new Set([
  "authorization",
  "connection",
  "content-length",
  "cookie",
  "forwarded",
  "host",
  "origin",
  "proxy-authorization",
  "set-cookie",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "x-real-ip"
]);
const MAX_RESTORE_FILE_BYTES = 256 * 1024 * 1024;
const SETTINGS_SECTION_IDS = [
  "account",
  "appearance",
  "inventory",
  "reservations",
  "api",
  "mcp",
  "data"
] as const;
type SettingsSection = (typeof SETTINGS_SECTION_IDS)[number];

type McpDirectConfirmation =
  | "create"
  | "rotate"
  | "apply_networks"
  | "switch"
  | "disable";

interface ParsedTrustedNetworks {
  networks: string[];
  error: string | null;
}

function validateMcpCustomHeaderName(value: string): string | null {
  const canonical = value.trim().toLowerCase();
  if (!canonical) {
    return "Enter an HTTP header name.";
  }
  if (canonical.length > 120) {
    return "Use 120 characters or fewer.";
  }
  if (!MCP_CUSTOM_HEADER_PATTERN.test(canonical)) {
    return "Use a valid HTTP header name without spaces or punctuation separators.";
  }
  if (
    MCP_RESERVED_CUSTOM_HEADERS.has(canonical) ||
    canonical.startsWith("x-forwarded-")
  ) {
    return "That header is reserved for HTTP or proxy authentication.";
  }
  return null;
}

function isValidIpv4Address(value: string): boolean {
  const octets = value.split(".");
  return (
    octets.length === 4 &&
    octets.every((octet) => {
      if (!/^\d{1,3}$/.test(octet)) {
        return false;
      }
      if (octet.length > 1 && octet.startsWith("0")) {
        return false;
      }
      const number = Number(octet);
      return number >= 0 && number <= 255;
    })
  );
}

function isValidIpv6Address(value: string): boolean {
  if (!value.includes(":") || value.includes("%")) {
    return false;
  }
  try {
    const parsed = new URL(`http://[${value}]/`);
    return parsed.hostname.startsWith("[") && parsed.hostname.endsWith("]");
  } catch {
    return false;
  }
}

function parseMcpTrustedNetworks(value: string): ParsedTrustedNetworks {
  const networks = value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (networks.length === 0) {
    return {
      networks,
      error: "Enter at least one IPv4 or IPv6 CIDR."
    };
  }
  if (networks.length > 64) {
    return {
      networks,
      error: "Use no more than 64 trusted networks."
    };
  }

  const seen = new Set<string>();
  for (const [index, network] of networks.entries()) {
    if (/\s/.test(network)) {
      return {
        networks,
        error: `Line ${index + 1}: CIDRs cannot contain spaces.`
      };
    }
    const pieces = network.split("/");
    if (pieces.length !== 2 || !pieces[0] || !/^\d+$/.test(pieces[1])) {
      return {
        networks,
        error: `Line ${index + 1}: use address/prefix notation.`
      };
    }
    const [address, prefixText] = pieces;
    const prefix = Number(prefixText);
    const ipv6 = address.includes(":");
    const validAddress = ipv6
      ? isValidIpv6Address(address)
      : isValidIpv4Address(address);
    const maximumPrefix = ipv6 ? 128 : 32;
    if (!validAddress) {
      return {
        networks,
        error: `Line ${index + 1}: invalid ${ipv6 ? "IPv6" : "IPv4"} address.`
      };
    }
    if (!Number.isInteger(prefix) || prefix < 1 || prefix > maximumPrefix) {
      return {
        networks,
        error: `Line ${index + 1}: prefix must be 1-${maximumPrefix}.`
      };
    }
    const duplicateKey = network.toLowerCase();
    if (seen.has(duplicateKey)) {
      return {
        networks,
        error: `Line ${index + 1}: duplicate CIDR.`
      };
    }
    seen.add(duplicateKey);
  }

  return { networks, error: null };
}

function mcpDirectModeLabel(mode: McpDirectSelectionMode): string {
  if (mode === "trusted_network") {
    return "Trusted network";
  }
  return mode === "custom_header" ? "Custom header" : "Bearer key";
}

function settingsSectionFromHash(): SettingsSection {
  const candidate = window.location.hash.replace(
    "#settings-",
    ""
  ) as SettingsSection;
  return SETTINGS_SECTION_IDS.includes(candidate)
    ? candidate
    : "appearance";
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

function formatUtc(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
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
  const { token, user, avatarImageUrl, refreshUser } = useAuth();
  const location = useLocation();
  const restoreFileInputRef = useRef<HTMLInputElement | null>(null);
  const accountAvatarInputRef = useRef<HTMLInputElement | null>(null);
  const [activeSettingsSection, setActiveSettingsSection] =
    useState<SettingsSection>(settingsSectionFromHash);
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
  const [mcpReloadVersion, setMcpReloadVersion] = useState(0);
  const [mcpUrlCopied, setMcpUrlCopied] = useState(false);
  const [mcpCopyError, setMcpCopyError] =
    useState<string | null>(null);
  // PARTPILOT:MCP_OAUTH_MANUAL_REGISTRATION_UI:V569
  const [mcpOAuthClients, setMcpOAuthClients] = useState<
    McpOAuthManageableClientSummary[] | null
  >(null);
  const [mcpOAuthClientsLoading, setMcpOAuthClientsLoading] = useState(true);
  const [mcpOAuthClientsError, setMcpOAuthClientsError] = useState<string | null>(null);
  const [mcpOAuthClientsMessage, setMcpOAuthClientsMessage] = useState<string | null>(null);
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
  const [mcpDirectAuth, setMcpDirectAuth] =
    useState<McpDirectAuthStatus | null>(null);
  const [mcpDirectAuthLoading, setMcpDirectAuthLoading] =
    useState(true);
  const [mcpDirectAuthBusy, setMcpDirectAuthBusy] = useState<
    "configure" | "reveal" | "disable" | null
  >(null);
  const [mcpDirectAuthError, setMcpDirectAuthError] =
    useState<string | null>(null);
  const [mcpDirectAuthMessage, setMcpDirectAuthMessage] =
    useState<string | null>(null);
  const [mcpDirectKey, setMcpDirectKey] =
    useState<string | null>(null);
  const [mcpDirectKeyVisible, setMcpDirectKeyVisible] =
    useState(false);
  const [mcpDirectKeyCopied, setMcpDirectKeyCopied] =
    useState(false);
  const [mcpDirectConfirm, setMcpDirectConfirm] =
    useState<McpDirectConfirmation | null>(null);
  const [mcpDirectCredentialDialogOpen, setMcpDirectCredentialDialogOpen] =
    useState(false);
  const [mcpDirectSelectedMode, setMcpDirectSelectedMode] =
    useState<McpDirectSelectionMode>("bearer_key");
  const [mcpDirectHeaderDraft, setMcpDirectHeaderDraft] = useState(
    MCP_CUSTOM_HEADER_DEFAULT
  );
  const [mcpDirectTrustedNetworksDraft, setMcpDirectTrustedNetworksDraft] =
    useState("");
  const [mcpDirectReloadVersion, setMcpDirectReloadVersion] =
    useState(0);

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

  const canReset =
    confirmation === RESET_CONFIRMATION && !isResetting;
  const canCommitRestore =
    restoreConfirmation === RESTORE_CONFIRMATION &&
    Boolean(restoreValidation) &&
    !restoreCommitting &&
    !restoreRestarting;

  const reservationSettingsChanged = Boolean(
    reservationSettings &&
      reservationDraft &&
      (reservationSettings.expiry_mode !==
        reservationDraft.expiry_mode ||
        reservationSettings.default_days !==
          reservationDraft.default_days)
  );

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
        mcpSettings.read_tools_enabled !==
          mcpDraft.read_tools_enabled ||
        mcpSettings.write_tools_enabled !==
          mcpDraft.write_tools_enabled)
  );
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
  const mcpDirectConfiguredMode: McpDirectSelectionMode | null =
    mcpDirectAuth?.configured && mcpDirectAuth.mode !== "disabled"
      ? mcpDirectAuth.mode
      : null;
  const mcpDirectModeMatches =
    mcpDirectConfiguredMode === mcpDirectSelectedMode;
  const mcpDirectHeaderError =
    mcpDirectSelectedMode === "custom_header"
      ? validateMcpCustomHeaderName(mcpDirectHeaderDraft)
      : null;
  const parsedMcpTrustedNetworks = parseMcpTrustedNetworks(
    mcpDirectTrustedNetworksDraft
  );
  const mcpDirectTrustedNetworksError =
    mcpDirectSelectedMode === "trusted_network"
      ? parsedMcpTrustedNetworks.error
      : null;
  const mcpDirectConfigurationError =
    mcpDirectHeaderError ?? mcpDirectTrustedNetworksError;
  const mcpDirectHeaderChanged = Boolean(
    mcpDirectConfiguredMode === "custom_header" &&
      mcpDirectSelectedMode === "custom_header" &&
      mcpDirectHeaderDraft.trim().toLowerCase() !==
        mcpDirectAuth?.custom_header_name
  );
  const mcpDirectTrustedNetworksChanged = Boolean(
    mcpDirectConfiguredMode === "trusted_network" &&
      mcpDirectSelectedMode === "trusted_network" &&
      parsedMcpTrustedNetworks.networks.join("\n") !==
        (mcpDirectAuth?.trusted_networks ?? []).join("\n")
  );
  const mcpDirectSelectionChanged =
    mcpDirectHeaderChanged || mcpDirectTrustedNetworksChanged;
  const mcpDirectActiveNetworks = mcpDirectAuth?.trusted_networks ?? [];
  const mcpDirectActiveNetworkPreview = mcpDirectActiveNetworks.slice(0, 3);
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

  useEffect(() => {
    return () => {
      if (accountAvatarPreviewUrl) {
        URL.revokeObjectURL(accountAvatarPreviewUrl);
      }
    };
  }, [accountAvatarPreviewUrl]);

  useEffect(() => {
    if (!token) {
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
    setAccountLoading(true);
    setSessionsLoading(true);
    setAccountError(null);
    setSessionsError(null);

    Promise.all([getProfile(token), getSessions(token)])
      .then(([profile, sessions]) => {
        if (cancelled) return;
        setAccountProfile(profile);
        setAccountDraft({
          username: profile.username,
          displayName: profile.display_name,
          avatarId: profile.avatar_id
        });
        setAccountSessions(sessions.sessions);
      })
      .catch((caught) => {
        if (cancelled) return;
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
    if (!token) {
      setSearchSettings(null);
      setSearchSettingsLoading(false);
      setSearchSettingsError(
        "Your session is unavailable. Sign in again."
      );
      return;
    }

    let cancelled = false;
    setSearchSettingsLoading(true);
    setSearchSettingsError(null);

    getSearchSettings(token)
      .then((result) => {
        if (!cancelled) {
          setSearchSettings(result);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setSearchSettings(null);
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
  }, [token]);

  useEffect(() => {
    if (!token) {
      setReservationSettings(null);
      setReservationDraft(null);
      setReservationSettingsLoading(false);
      setReservationSettingsError(
        "Your session is unavailable. Sign in again."
      );
      return;
    }

    let cancelled = false;
    setReservationSettingsLoading(true);
    setReservationSettingsError(null);
    setReservationSettingsSaved(false);

    getReservationSettings(token)
      .then((result) => {
        if (!cancelled) {
          setReservationSettings(result);
          setReservationDraft(result);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setReservationSettings(null);
          setReservationDraft(null);
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
  }, [reservationReloadVersion, token]);

  // PARTPILOT:MCP_SETTINGS_UI:V473
  useEffect(() => {
    if (!token) {
      setMcpSettings(null);
      setMcpDraft(null);
      setMcpSettingsLoading(false);
      setMcpSettingsError(
        "Your session is unavailable. Sign in again."
      );
      return;
    }

    let cancelled = false;
    setMcpSettingsLoading(true);
    setMcpSettingsError(null);
    setMcpSettingsSaved(false);

    getMcpSettings(token)
      .then((result) => {
        if (!cancelled) {
          setMcpSettings(result);
          setMcpDraft(result);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setMcpSettings(null);
          setMcpDraft(null);
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
  }, [mcpReloadVersion, token]);

  // PARTPILOT:MCP_OAUTH_MANUAL_REGISTRATION_UI:V569
  useEffect(() => {
    if (!token) {
      setMcpOAuthClients(null);
      setMcpOAuthClientsLoading(false);
      setMcpOAuthClientsError("Your session is unavailable. Sign in again.");
      setMcpOAuthCredential(null);
      return;
    }
    let cancelled = false;
    setMcpOAuthClientsLoading(true);
    setMcpOAuthClientsError(null);
    getMcpOAuthManageableClients(token)
      .then((result) => { if (!cancelled) setMcpOAuthClients(result.clients); })
      .catch((caught) => {
        if (!cancelled) {
          setMcpOAuthClients(null);
          setMcpOAuthClientsError(caught instanceof Error ? caught.message : "Unable to load OAuth clients");
        }
      })
      .finally(() => { if (!cancelled) setMcpOAuthClientsLoading(false); });
    return () => { cancelled = true; };
  }, [mcpOAuthReloadVersion, token]);

  // PARTPILOT:MCP_TRUSTED_NETWORK_UI:V510
  useEffect(() => {
    if (!token) {
      setMcpDirectAuth(null);
      setMcpDirectAuthLoading(false);
      setMcpDirectAuthError(
        "Your session is unavailable. Sign in again."
      );
      return;
    }

    let cancelled = false;
    setMcpDirectAuthLoading(true);
    setMcpDirectAuthError(null);

    getMcpDirectAuth(token)
      .then((result) => {
        if (!cancelled) {
          setMcpDirectAuth(result);
          if (result.mode === "custom_header") {
            setMcpDirectSelectedMode("custom_header");
            setMcpDirectHeaderDraft(
              result.custom_header_name ?? MCP_CUSTOM_HEADER_DEFAULT
            );
          } else if (result.mode === "bearer_key") {
            setMcpDirectSelectedMode("bearer_key");
          } else if (result.mode === "trusted_network") {
            setMcpDirectSelectedMode("trusted_network");
            setMcpDirectTrustedNetworksDraft(
              result.trusted_networks.join("\n")
            );
          }
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setMcpDirectAuth(null);
          setMcpDirectAuthError(
            caught instanceof Error
              ? caught.message
              : "Unable to load direct authentication"
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setMcpDirectAuthLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [mcpDirectReloadVersion, token]);

  // PARTPILOT:SETTINGS_MANUAL_BACKUP_STATUS_UI:V454
  useEffect(() => {
    if (!token) {
      setBackupStatus(null);
      setBackupStatusLoading(false);
      setBackupStatusError(
        "Your session is unavailable. Sign in again."
      );
      return;
    }

    let cancelled = false;
    setBackupStatusLoading(true);
    setBackupStatusError(null);

    getManualBackupStatus(token)
      .then((result) => {
        if (!cancelled) {
          setBackupStatus(result);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setBackupStatus(null);
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
  }, [backupStatusReloadVersion, token]);

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

  function chooseReservationExpiryMode(
    expiryMode: ReservationExpiryMode
  ): void {
    if (!reservationDraft || reservationSettingsSaving) {
      return;
    }
    setReservationDraft({
      expiry_mode: expiryMode,
      default_days:
        expiryMode === "none"
          ? null
          : reservationDraft.default_days
    });
    setReservationSettingsError(null);
    setReservationSettingsSaved(false);
  }

  function resetReservationDraft(): void {
    if (!reservationSettings || reservationSettingsSaving) {
      return;
    }
    setReservationDraft(reservationSettings);
    setReservationSettingsError(null);
    setReservationSettingsSaved(false);
  }

  async function saveReservationDefaults(): Promise<void> {
    if (
      !token ||
      !reservationDraft ||
      reservationSettingsSaving ||
      reservationDaysError
    ) {
      return;
    }

    setReservationSettingsSaving(true);
    setReservationSettingsError(null);
    setReservationSettingsSaved(false);
    try {
      const saved = await updateReservationSettings(
        token,
        reservationDraft
      );
      setReservationSettings(saved);
      setReservationDraft(saved);
      setReservationSettingsSaved(true);
    } catch (caught) {
      setReservationSettingsError(
        caught instanceof Error
          ? caught.message
          : "Unable to save reservation defaults"
      );
    } finally {
      setReservationSettingsSaving(false);
    }
  }

  function updateMcpDraft(
    field: keyof McpSettings,
    value: boolean
  ): void {
    if (!mcpDraft || mcpSettingsSaving) {
      return;
    }
    setMcpDraft({ ...mcpDraft, [field]: value });
    setMcpSettingsError(null);
    setMcpSettingsSaved(false);
  }

  function resetMcpDraft(): void {
    if (!mcpSettings || mcpSettingsSaving) {
      return;
    }
    setMcpDraft(mcpSettings);
    setMcpSettingsError(null);
    setMcpSettingsSaved(false);
  }

  async function saveMcpAccess(): Promise<void> {
    if (!token || !mcpDraft || mcpSettingsSaving) {
      return;
    }

    setMcpSettingsSaving(true);
    setMcpSettingsError(null);
    setMcpSettingsSaved(false);
    try {
      const saved = await updateMcpSettings(token, mcpDraft);
      setMcpSettings(saved);
      setMcpDraft(saved);
      setMcpSettingsSaved(true);
    } catch (caught) {
      setMcpSettingsError(
        caught instanceof Error
          ? caught.message
          : "Unable to save MCP settings"
      );
    } finally {
      setMcpSettingsSaving(false);
    }
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

  function clearMcpDirectFeedback(): void {
    setMcpDirectAuthError(null);
    setMcpDirectAuthMessage(null);
    setMcpDirectKeyCopied(false);
  }

  function chooseMcpDirectMode(mode: McpDirectSelectionMode): void {
    if (mcpDirectAuthBusy) {
      return;
    }
    clearMcpDirectFeedback();
    setMcpDirectConfirm(null);
    setMcpDirectCredentialDialogOpen(false);
    setMcpDirectKey(null);
    setMcpDirectKeyVisible(false);
    setMcpDirectSelectedMode(mode);
    if (mode === "custom_header") {
      setMcpDirectHeaderDraft(
        mcpDirectAuth?.mode === "custom_header" &&
          mcpDirectAuth.custom_header_name
          ? mcpDirectAuth.custom_header_name
          : MCP_CUSTOM_HEADER_DEFAULT
      );
    }
    if (mode === "trusted_network" && mcpDirectAuth?.mode === "trusted_network") {
      setMcpDirectTrustedNetworksDraft(
        mcpDirectAuth.trusted_networks.join("\n")
      );
    }
  }

  async function configureMcpDirectSelection(): Promise<void> {
    if (!token || mcpDirectAuthBusy || mcpDirectConfigurationError) {
      return;
    }
    const previousMode = mcpDirectConfiguredMode;
    const wasConfigured = Boolean(previousMode);
    setMcpDirectAuthBusy("configure");
    clearMcpDirectFeedback();
    try {
      if (mcpDirectSelectedMode === "trusted_network") {
        const result = await configureMcpDirectTrustedNetworks(token, {
          networks: parsedMcpTrustedNetworks.networks
        });
        setMcpDirectAuth(result);
        setMcpDirectSelectedMode("trusted_network");
        setMcpDirectTrustedNetworksDraft(
          result.trusted_networks.join("\n")
        );
        setMcpDirectKey(null);
        setMcpDirectKeyVisible(false);
        setMcpDirectCredentialDialogOpen(false);
        setMcpDirectConfirm(null);
        setMcpDirectAuthMessage(
          !wasConfigured
            ? "Trusted-network authentication enabled. Requests are accepted only from the configured CIDRs."
            : previousMode !== "trusted_network"
              ? "Switched to trusted-network authentication. The previous direct key stopped working."
              : "Trusted networks updated. Removed networks are rejected immediately."
        );
        return;
      }

      const result =
        mcpDirectSelectedMode === "custom_header"
          ? await rotateMcpDirectCustomHeaderKey(token, {
              header_name: mcpDirectHeaderDraft.trim().toLowerCase()
            })
          : await rotateMcpDirectBearerKey(token);
      setMcpDirectAuth(result);
      setMcpDirectSelectedMode(
        result.mode === "custom_header" ? "custom_header" : "bearer_key"
      );
      setMcpDirectHeaderDraft(
        result.custom_header_name ?? MCP_CUSTOM_HEADER_DEFAULT
      );
      setMcpDirectKey(result.key);
      setMcpDirectKeyVisible(true);
      setMcpDirectConfirm(null);
      setMcpDirectCredentialDialogOpen(true);
      const label = mcpDirectModeLabel(mcpDirectSelectedMode);
      setMcpDirectAuthMessage(
        !wasConfigured
          ? `${label} created. Copy the key into your MCP client.`
          : previousMode !== mcpDirectSelectedMode
            ? `Switched to ${label.toLowerCase()}. The previous direct mode stopped working.`
            : `${label} rotated. Existing direct clients must use the new key.`
      );
    } catch (caught) {
      setMcpDirectAuthError(
        caught instanceof Error
          ? caught.message
          : "Unable to configure direct authentication"
      );
    } finally {
      setMcpDirectAuthBusy(null);
    }
  }

  async function revealMcpDirectCredential(): Promise<void> {
    if (
      !token ||
      mcpDirectAuthBusy ||
      !mcpDirectAuth?.configured ||
      mcpDirectConfiguredMode === "trusted_network"
    ) {
      return;
    }
    setMcpDirectAuthBusy("reveal");
    clearMcpDirectFeedback();
    try {
      const result = await revealMcpDirectKey(token);
      setMcpDirectAuth(result);
      setMcpDirectKey(result.key);
      setMcpDirectKeyVisible(true);
      setMcpDirectCredentialDialogOpen(true);
      setMcpDirectAuthMessage(
        `${mcpDirectModeLabel(
          result.mode === "custom_header" ? "custom_header" : "bearer_key"
        )} revealed. Keep it private and use HTTPS.`
      );
    } catch (caught) {
      setMcpDirectAuthError(
        caught instanceof Error
          ? caught.message
          : "Unable to reveal the direct key"
      );
    } finally {
      setMcpDirectAuthBusy(null);
    }
  }

  async function disableMcpDirectKey(): Promise<void> {
    if (!token || mcpDirectAuthBusy || !mcpDirectAuth?.configured) {
      return;
    }
    setMcpDirectAuthBusy("disable");
    clearMcpDirectFeedback();
    try {
      const result = await disableMcpDirectAuth(token);
      setMcpDirectAuth(result);
      setMcpDirectKey(null);
      setMcpDirectKeyVisible(false);
      setMcpDirectCredentialDialogOpen(false);
      setMcpDirectConfirm(null);
      setMcpDirectAuthMessage(
        mcpDirectConfiguredMode === "trusted_network"
          ? "Trusted-network authentication disabled."
          : "Direct-key authentication disabled."
      );
    } catch (caught) {
      setMcpDirectAuthError(
        caught instanceof Error
          ? caught.message
          : "Unable to disable direct authentication"
      );
    } finally {
      setMcpDirectAuthBusy(null);
    }
  }

  async function copyMcpDirectKey(): Promise<void> {
    if (!mcpDirectKey) {
      return;
    }
    clearMcpDirectFeedback();
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(mcpDirectKey);
      } else {
        const field = document.createElement("textarea");
        field.value = mcpDirectKey;
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
      setMcpDirectKeyCopied(true);
      setMcpDirectAuthMessage("Direct key copied.");
    } catch (caught) {
      setMcpDirectAuthError(
        caught instanceof Error
          ? caught.message
          : "Unable to copy the direct key"
      );
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
      data-partpilot-active-settings-section={activeSettingsSection}
    >
      <header className="page-header settings-page-header">
        <div>
          <p className="eyebrow">Application configuration</p>
          <h1>Settings</h1>
          <p>
            Manage your account, security, appearance, inventory behavior,
            reservation defaults, REST API access, MCP access, and local data controls.
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
        <button
          className={
            activeSettingsSection === "appearance"
              ? "is-active"
              : ""
          }
          type="button"
          aria-current={
            activeSettingsSection === "appearance"
              ? "page"
              : undefined
          }
          aria-controls="settings-appearance"
          onClick={() => chooseSettingsSection("appearance")}
        >
          Appearance
        </button>
        <button
          className={
            activeSettingsSection === "inventory"
              ? "is-active"
              : ""
          }
          type="button"
          aria-current={
            activeSettingsSection === "inventory"
              ? "page"
              : undefined
          }
          aria-controls="settings-inventory"
          onClick={() => chooseSettingsSection("inventory")}
        >
          Inventory
        </button>
        <button
          className={
            activeSettingsSection === "reservations"
              ? "is-active"
              : ""
          }
          type="button"
          aria-current={
            activeSettingsSection === "reservations"
              ? "page"
              : undefined
          }
          aria-controls="settings-reservations"
          onClick={() => chooseSettingsSection("reservations")}
        >
          Reservations
        </button>
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
      </nav>

      <section
        id="settings-account"
        className="card settings-section settings-account-section"
        aria-labelledby="settings-account-title"
        hidden={activeSettingsSection !== "account"}
        data-partpilot-account-security="PARTPILOT:SETTINGS_ACCOUNT_SECURITY_UI:V592"
      >
        <div className="settings-section-heading">
          <div>
            <span className="card-label">Owner account</span>
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
          <div className="settings-account-panel settings-account-primary-panel">
            <div className="settings-account-panel-heading">
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

          <div className="settings-account-panel settings-account-primary-panel">
            <div className="settings-account-panel-heading">
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
            className="settings-account-panel settings-account-sessions-panel"
          >
            <div className="settings-account-sessions-heading">
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
                          Signed in {formatUtc(session.created_at)}
                        </span>
                        <span>
                          Expires {formatUtc(session.expires_at)}
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

      <section
        id="settings-appearance"
        className="card settings-section settings-appearance-section"
        aria-labelledby="settings-appearance-title"
        hidden={activeSettingsSection !== "appearance"}
      >
        <div className="settings-section-heading">
          <div>
            <span className="card-label">Workspace</span>
            <h2 id="settings-appearance-title">Appearance</h2>
            <p>
              Choose a stored preference for the complete Part Pilot
              interface. System mode follows operating-system changes
              without a reload.
            </p>
          </div>
        </div>

        {appearanceLoading ? (
          <p className="settings-preference-state" role="status">
            Loading appearance preference...
          </p>
        ) : (
          <div
            className="settings-theme-options"
            role="radiogroup"
            aria-label="Application appearance"
          >
            {APPEARANCE_OPTIONS.map((option) => {
              const disabled =
                appearanceSaving ||
                (option.value !== "dark" &&
                  !lightThemeAvailable);
              return (
                <button
                  key={option.value}
                  className={
                    theme === option.value
                      ? "settings-theme-option is-selected"
                      : "settings-theme-option"
                  }
                  type="button"
                  role="radio"
                  aria-checked={theme === option.value}
                  disabled={disabled}
                  onClick={() =>
                    void selectTheme(option.value)
                  }
                >
                  <span
                    className={`settings-theme-preview is-${option.value}`}
                    aria-hidden="true"
                  >
                    <span className="settings-preview-sidebar" />
                    <span className="settings-preview-main">
                      <i />
                      <i />
                      <i />
                    </span>
                  </span>
                  <span className="settings-theme-copy">
                    <strong>{option.title}</strong>
                    <span>{option.description}</span>
                  </span>
                  <span
                    className="settings-theme-check"
                    aria-hidden="true"
                  >
                    {theme === option.value ? "Selected" : ""}
                  </span>
                </button>
              );
            })}
          </div>
        )}

        {!lightThemeAvailable ? (
          <p className="settings-preference-state">
            Light and System modes are unavailable for this
            installation. Dark remains active.
          </p>
        ) : null}

        {appearanceError ? (
          <div
            className="settings-preference-state is-error"
            role="alert"
          >
            <span>{appearanceError}</span>
            <button type="button" onClick={reloadAppearance}>
              Retry
            </button>
          </div>
        ) : null}

        {appearanceSaved && !appearanceError ? (
          <p
            className="settings-preference-state is-success"
            role="status"
          >
            Appearance saved and applied across Part Pilot.
          </p>
        ) : null}
      </section>

      <div
        className="settings-content-grid"
        data-partpilot-settings-layout="PARTPILOT:SETTINGS_DESKTOP_COMPOSITION:V423"
      >
        <section
          id="settings-inventory"
          className="card settings-search-compact settings-grid-inventory"
          aria-labelledby="settings-search-title"
          hidden={activeSettingsSection !== "inventory"}
          data-partpilot-compact-search="PARTPILOT:COMPACT_OUT_OF_STOCK_PREFERENCE:V418"
        >
          <div className="settings-search-compact-copy">
            <span className="card-label">Inventory search</span>
            <h2 id="settings-search-title">
              Separate out-of-stock results
            </h2>
            <p id="settings-search-description">
              Show zero-stock matches below available parts when All is
              selected. The explicit Out filter always remains available.
            </p>
          </div>

          <div className="settings-search-compact-control">
            {searchSettingsLoading ? (
              <span
                className="settings-search-compact-status"
                role="status"
              >
                Loading...
              </span>
            ) : null}

            {!searchSettingsLoading && searchSettings ? (
              <label
                className={
                  searchSettingsSaving
                    ? "settings-compact-switch-control is-disabled"
                    : "settings-compact-switch-control"
                }
              >
                <span className="settings-compact-switch-state">
                  {searchSettingsSaving
                    ? "Saving..."
                    : searchSettings.show_out_of_stock_section
                      ? "On"
                      : "Off"}
                </span>
                <input
                  type="checkbox"
                  role="switch"
                  checked={
                    searchSettings.show_out_of_stock_section
                  }
                  onChange={(event) =>
                    void handleOutOfStockPreference(
                      event.target.checked
                    )
                  }
                  disabled={searchSettingsSaving}
                  aria-label="Show a separate out-of-stock section"
                  aria-describedby="settings-search-description"
                />
                <span
                  className="settings-switch"
                  aria-hidden="true"
                />
              </label>
            ) : null}
          </div>

          {searchSettingsError ? (
            <p
              className="settings-search-compact-feedback is-error"
              role="alert"
            >
              {searchSettingsError}
            </p>
          ) : null}

          {searchSettingsSaved && !searchSettingsError ? (
            <p
              className="settings-search-compact-feedback is-success"
              role="status"
            >
              Preference saved.
            </p>
          ) : null}
        </section>

        <section
          id="settings-reservations"
          className="card settings-section settings-reservation-section settings-grid-reservations"
          aria-labelledby="settings-reservation-title"
          hidden={activeSettingsSection !== "reservations"}
          data-partpilot-marker="PARTPILOT:RESERVATION_EXPIRY_SETTINGS_UI:V362"
        >
          <div className="settings-section-heading">
            <div>
              <span className="card-label">Reservations</span>
              <h2 id="settings-reservation-title">
                Reservation defaults
              </h2>
              <p>
                Set the suggested expiry for new manual reservations.
                Existing reservations are never rewritten.
              </p>
            </div>
          </div>

          {reservationSettingsLoading ? (
            <p
              className="settings-preference-state"
              role="status"
            >
              Loading reservation defaults...
            </p>
          ) : null}

          {!reservationSettingsLoading && reservationDraft ? (
            <div className="settings-reservation-form">
              <div
                className="settings-segmented-control"
                role="radiogroup"
                aria-label="Default reservation expiry"
              >
                <button
                  type="button"
                  role="radio"
                  aria-checked={
                    reservationDraft.expiry_mode === "none"
                  }
                  className={
                    reservationDraft.expiry_mode === "none"
                      ? "is-active"
                      : ""
                  }
                  onClick={() =>
                    chooseReservationExpiryMode("none")
                  }
                  disabled={reservationSettingsSaving}
                >
                  No automatic expiry
                </button>
                <button
                  type="button"
                  role="radio"
                  aria-checked={
                    reservationDraft.expiry_mode === "default"
                  }
                  className={
                    reservationDraft.expiry_mode === "default"
                      ? "is-active"
                      : ""
                  }
                  onClick={() =>
                    chooseReservationExpiryMode("default")
                  }
                  disabled={reservationSettingsSaving}
                >
                  Default expiry after
                </button>
              </div>

              {reservationDraft.expiry_mode === "default" ? (
                <label className="settings-days-field">
                  <span>Default expiry duration</span>
                  <span className="settings-days-control">
                    <input
                      type="number"
                      min={1}
                      max={3650}
                      step={1}
                      inputMode="numeric"
                      value={
                        reservationDraft.default_days ?? ""
                      }
                      onChange={(event) => {
                        const value =
                          event.currentTarget.value;
                        setReservationDraft({
                          expiry_mode: "default",
                          default_days:
                            value === ""
                              ? null
                              : Number(value)
                        });
                        setReservationSettingsError(null);
                        setReservationSettingsSaved(false);
                      }}
                      aria-invalid={Boolean(
                        reservationDaysError
                      )}
                      aria-describedby="reservation-default-days-help"
                      disabled={reservationSettingsSaving}
                    />
                    <strong>days</strong>
                  </span>
                  <small id="reservation-default-days-help">
                    Calculated when New reservation is opened.
                  </small>
                </label>
              ) : (
                <p className="settings-reservation-summary">
                  New reservations start with no expiry selected.
                </p>
              )}

              {reservationDaysError ? (
                <p
                  className="settings-preference-state is-error"
                  role="alert"
                >
                  {reservationDaysError}
                </p>
              ) : null}

              <div className="settings-action-row">
                <button
                  className="settings-action settings-action-secondary"
                  type="button"
                  onClick={resetReservationDraft}
                  disabled={
                    !reservationSettingsChanged ||
                    reservationSettingsSaving
                  }
                >
                  Reset changes
                </button>
                <button
                  className="settings-action settings-action-primary"
                  type="button"
                  onClick={() =>
                    void saveReservationDefaults()
                  }
                  disabled={
                    !reservationSettingsChanged ||
                    reservationSettingsSaving ||
                    Boolean(reservationDaysError)
                  }
                >
                  {reservationSettingsSaving
                    ? "Saving defaults..."
                    : "Save reservation defaults"}
                </button>
              </div>
            </div>
          ) : null}

          {reservationSettingsError &&
          !reservationDaysError ? (
            <div
              className="settings-preference-state is-error"
              role="alert"
            >
              <span>{reservationSettingsError}</span>
              {!reservationDraft ? (
                <button
                  type="button"
                  onClick={() =>
                    setReservationReloadVersion(
                      (value) => value + 1
                    )
                  }
                >
                  Retry
                </button>
              ) : null}
            </div>
          ) : null}

          {reservationSettingsSaved &&
          !reservationSettingsError ? (
            <p
              className="settings-preference-state is-success"
              role="status"
            >
              Reservation defaults saved.
            </p>
          ) : null}
        </section>

        <ApiKeySettingsSection
          token={token}
          hidden={activeSettingsSection !== "api"}
        />

        <section
          id="settings-mcp"
          className="card settings-section settings-mcp-section settings-grid-mcp"
          aria-labelledby="settings-mcp-title"
          hidden={activeSettingsSection !== "mcp"}
          data-partpilot-mcp-direct-auth="PARTPILOT:MCP_DIRECT_AUTH_UI:V500"
        >
          <div className="settings-section-heading settings-mcp-heading">
            <div>
              <span className="card-label">Integrations</span>
              <h2 id="settings-mcp-title">Model Context Protocol</h2>
              <p>
                Connect compatible clients through OAuth, a static bearer
                key, or a dedicated custom HTTP header.
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

          {mcpSettingsLoading ? (
            <p className="settings-preference-state" role="status">
              Loading MCP settings...
            </p>
          ) : null}

          {!mcpSettingsLoading && mcpDraft ? (
            <>
              <div className="settings-mcp-endpoint">
                <div className="settings-mcp-endpoint-copy">
                  <strong>MCP server URL</strong>
                  <span>Use this exact URL when adding Part Pilot to a client.</span>
                </div>
                <div className="settings-mcp-url-row">
                  <input
                    type="text"
                    value={mcpServerUrl}
                    readOnly
                    aria-label="MCP server URL"
                    onFocus={(event) => event.currentTarget.select()}
                  />
                  <button
                    className="settings-action settings-action-secondary"
                    type="button"
                    onClick={() => void copyMcpServerUrl()}
                  >
                    {mcpUrlCopied ? "Copied" : "Copy URL"}
                  </button>
                </div>
                <p
                  className={
                    mcpUsesPublicHttps
                      ? "settings-mcp-endpoint-note is-ready"
                      : "settings-mcp-endpoint-note is-warning"
                  }
                >
                  {mcpUsesPublicHttps
                    ? "This page is using HTTPS, as required for remote MCP credentials."
                    : "Remote MCP clients should use Part Pilot through its public HTTPS address."}
                </p>
                {mcpCopyError ? (
                  <p className="settings-mcp-copy-error" role="alert">
                    {mcpCopyError}
                  </p>
                ) : null}
              </div>

              <div
                className="settings-mcp-oauth-clients"
                data-partpilot-mcp-oauth-clients="PARTPILOT:MCP_OAUTH_MANUAL_REGISTRATION_UI:V569"
              >
                <div className="settings-mcp-oauth-heading">
                  <div>
                    <strong>OAuth clients</strong>
                    <span>Register clients manually or review clients that have connected through OAuth. Confidential client secrets are shown only once when the client is created.</span>
                  </div>
                  <div className="settings-mcp-oauth-heading-actions">
                    <button className="settings-action settings-action-primary" type="button" disabled={mcpOAuthRegistering} onClick={mcpOAuthRegisterOpen ? closeMcpOAuthRegistration : openMcpOAuthRegistration}>{mcpOAuthRegisterOpen ? "Close form" : "Register client"}</button>
                  </div>
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

                {mcpOAuthClientsLoading ? <p className="settings-mcp-oauth-state" role="status">Loading OAuth clients...</p> : null}
                {!mcpOAuthClientsLoading && mcpOAuthVisibleClients && mcpOAuthVisibleClients.length > 0 ? (
                  <div className="settings-mcp-oauth-list">
                    {mcpOAuthVisibleClients.map((client) => (
                      <article className={`settings-mcp-oauth-client is-${client.status}`} key={client.database_id}>
                        <header><div><strong>{client.client_name}</strong><span>{client.client_type === "confidential" ? "Confidential OAuth client" : "Public OAuth client"}</span></div><span className={`settings-mcp-oauth-status is-${client.status}`}>{client.status === "connected" ? "Connected" : client.status === "registered" ? "Registered" : "Revoked"}</span></header>
                        <dl><div><dt>Origin</dt><dd>{client.redirect_origins.length > 0 ? client.redirect_origins.join(", ") : "No web origin"}</dd></div><div><dt>Auth</dt><dd>{client.token_endpoint_auth_method === "none" ? "None" : client.token_endpoint_auth_method === "client_secret_basic" ? "Client secret Basic" : "Client secret POST"}</dd></div><div><dt>Created</dt><dd>{formatUtc(client.created_at)}</dd></div><div><dt>Connected</dt><dd>{client.connected_at ? formatUtc(client.connected_at) : "Not yet"}</dd></div></dl>
                        <footer><span>{client.status === "connected" ? `${client.active_token_count} active session${client.active_token_count === 1 ? "" : "s"}` : client.status === "registered" ? "Awaiting first authorization" : "Registration disabled"}</span>{client.status !== "revoked" ? <button className="settings-action settings-action-danger" type="button" disabled={mcpOAuthRevokingId !== null} onClick={() => openMcpOAuthRevokeDialog(client)}>{client.status === "connected" ? "Revoke access" : "Revoke client"}</button> : null}</footer>
                      </article>
                    ))}
                  </div>
                ) : null}
                {!mcpOAuthClientsLoading && mcpOAuthVisibleClients?.length === 0 ? <p className="settings-mcp-oauth-state">No active OAuth clients are registered or connected.</p> : null}
                {mcpOAuthClientsError ? <div className="settings-preference-state is-error" role="alert"><span>{mcpOAuthClientsError}</span>{!mcpOAuthClients ? <button type="button" onClick={() => setMcpOAuthReloadVersion((value) => value + 1)}>Retry</button> : null}</div> : null}
                {mcpOAuthClientsMessage && !mcpOAuthClientsError ? <p className="settings-preference-state is-success" role="status">{mcpOAuthClientsMessage}</p> : null}
              </div>

              <div
                className="settings-mcp-direct-auth"
                data-partpilot-mcp-trusted-network="PARTPILOT:MCP_TRUSTED_NETWORK_UI:V510"
              >
                <div className="settings-mcp-direct-heading">
                  <div>
                    <strong>Direct client authentication</strong>
                    <span>
                      Choose one installation-wide direct method for clients that
                      cannot complete OAuth. OAuth remains available in every mode.
                    </span>
                  </div>
                  {mcpDirectAuth ? (
                    <span className={mcpDirectAuth.configured ? "settings-mcp-direct-state is-configured" : "settings-mcp-direct-state"}>
                      {mcpDirectConfiguredMode ? `${mcpDirectModeLabel(mcpDirectConfiguredMode)} configured` : "Not configured"}
                    </span>
                  ) : null}
                </div>
                {mcpDirectAuthLoading ? <p className="settings-mcp-direct-note" role="status">Loading direct authentication...</p> : null}
                {!mcpDirectAuthLoading && mcpDirectAuth ? (
                  <>
                    <div className="settings-mcp-direct-mode" role="group" aria-label="Direct authentication mode">
                      {(["bearer_key", "custom_header", "trusted_network"] as McpDirectSelectionMode[]).map((mode) => (
                        <button key={mode} className={mcpDirectSelectedMode === mode ? "is-selected" : ""} type="button" aria-pressed={mcpDirectSelectedMode === mode} disabled={Boolean(mcpDirectAuthBusy)} onClick={() => chooseMcpDirectMode(mode)}>
                          <strong>{mcpDirectModeLabel(mode)}</strong>
                          <span>{mode === "bearer_key" ? "Authorization: Bearer <key>" : mode === "custom_header" ? "Send the key in one dedicated HTTP header." : "Allow resolved client IPs in approved CIDRs."}</span>
                        </button>
                      ))}
                    </div>
                    <p className="settings-mcp-direct-switch-note">Only one direct mode can be active. Switching modes disables the previous direct method immediately; OAuth is unaffected.</p>
                    {mcpDirectSelectedMode === "custom_header" ? (
                      <div className="settings-mcp-direct-config">
                        <label htmlFor="settings-mcp-direct-header-name">HTTP header name</label>
                        <input id="settings-mcp-direct-header-name" type="text" value={mcpDirectHeaderDraft} maxLength={120} spellCheck={false} autoComplete="off" disabled={Boolean(mcpDirectAuthBusy)} aria-invalid={Boolean(mcpDirectHeaderError)} aria-describedby="settings-mcp-direct-header-note" onChange={(event) => { setMcpDirectHeaderDraft(event.target.value); clearMcpDirectFeedback(); setMcpDirectConfirm(null); }} />
                        <p id="settings-mcp-direct-header-note" className={mcpDirectHeaderError ? "is-error" : ""}>{mcpDirectHeaderError ?? "Your reverse proxy must pass this header unchanged and must not log its value."}</p>
                      </div>
                    ) : null}
                    {mcpDirectSelectedMode === "trusted_network" ? (
                      <div className="settings-mcp-direct-config">
                        <label htmlFor="settings-mcp-trusted-networks">Trusted IPv4 and IPv6 CIDRs</label>
                        <textarea id="settings-mcp-trusted-networks" value={mcpDirectTrustedNetworksDraft} rows={5} spellCheck={false} autoComplete="off" placeholder={"192.168.1.0/24\n2001:db8:1234::/64"} disabled={Boolean(mcpDirectAuthBusy)} aria-invalid={Boolean(mcpDirectTrustedNetworksError)} aria-describedby="settings-mcp-trusted-networks-note" onChange={(event) => { setMcpDirectTrustedNetworksDraft(event.target.value); clearMcpDirectFeedback(); setMcpDirectConfirm(null); }} />
                        <p id="settings-mcp-trusted-networks-note" className={mcpDirectTrustedNetworksError ? "is-error" : ""}>{mcpDirectTrustedNetworksError ?? "One CIDR per line, maximum 64. Trust-all, multicast, unspecified, duplicate, and overlapping networks are rejected by the server."}</p>
                        <p className="settings-mcp-trusted-warning">Access uses the resolved client IP after the configured proxy chain. Do not add a network unless every device on it may use Part Pilot without an MCP key.</p>
                      </div>
                    ) : null}
                    <dl className="settings-mcp-direct-summary">
                      <div><dt>Active mode</dt><dd>{mcpDirectConfiguredMode ? mcpDirectModeLabel(mcpDirectConfiguredMode) : "Disabled"}{mcpDirectConfiguredMode === "custom_header" && mcpDirectAuth.custom_header_name ? <small>{mcpDirectAuth.custom_header_name}</small> : null}</dd></div>
                      <div><dt>{mcpDirectConfiguredMode === "trusted_network" ? "Networks" : "Key"}</dt><dd>{mcpDirectConfiguredMode === "trusted_network" ? `${mcpDirectActiveNetworks.length} configured` : mcpDirectAuth.masked_key ?? "Not created"}</dd></div>
                      <div><dt>{mcpDirectConfiguredMode === "trusted_network" ? "Changed" : "Rotated"}</dt><dd>{mcpDirectAuth.rotated_at ? formatUtc(mcpDirectAuth.rotated_at) : "Never"}</dd></div>
                      <div><dt>Last used</dt><dd>{mcpDirectAuth.last_used_at ? formatUtc(mcpDirectAuth.last_used_at) : "Never"}</dd></div>
                    </dl>
                    {mcpDirectConfiguredMode === "trusted_network" && mcpDirectActiveNetworks.length > 0 ? (
                      <div className="settings-mcp-trusted-active"><strong>Active trusted CIDRs</strong><div>{mcpDirectActiveNetworkPreview.map((network) => <code key={network}>{network}</code>)}{mcpDirectActiveNetworks.length > 3 ? <span>+{mcpDirectActiveNetworks.length - 3} more</span> : null}</div></div>
                    ) : null}
                    <div className="settings-mcp-direct-actions">
                      {!mcpDirectAuth.configured ? <button className="settings-action settings-action-primary" type="button" disabled={Boolean(mcpDirectAuthBusy) || Boolean(mcpDirectConfigurationError)} onClick={() => { clearMcpDirectFeedback(); setMcpDirectConfirm("create"); }}>{mcpDirectSelectedMode === "trusted_network" ? "Enable trusted network" : `Create ${mcpDirectModeLabel(mcpDirectSelectedMode)}`}</button> : mcpDirectModeMatches ? <>{mcpDirectConfiguredMode !== "trusted_network" ? <button className="settings-action settings-action-secondary" type="button" disabled={Boolean(mcpDirectAuthBusy)} onClick={() => void revealMcpDirectCredential()}>{mcpDirectAuthBusy === "reveal" ? "Revealing..." : "Reveal key"}</button> : null}{mcpDirectConfiguredMode === "trusted_network" ? mcpDirectTrustedNetworksChanged ? <button className="settings-action settings-action-primary" type="button" disabled={Boolean(mcpDirectAuthBusy) || Boolean(mcpDirectConfigurationError)} onClick={() => { clearMcpDirectFeedback(); setMcpDirectConfirm("apply_networks"); }}>Apply network changes</button> : null : <button className="settings-action settings-action-secondary" type="button" disabled={Boolean(mcpDirectAuthBusy) || Boolean(mcpDirectConfigurationError)} onClick={() => { clearMcpDirectFeedback(); setMcpDirectConfirm("rotate"); }}>{mcpDirectSelectionChanged ? "Apply header & rotate" : "Rotate key"}</button>}<button className="settings-action settings-action-danger" type="button" disabled={Boolean(mcpDirectAuthBusy)} onClick={() => { clearMcpDirectFeedback(); setMcpDirectConfirm("disable"); }}>Disable direct mode</button></> : <><button className="settings-action settings-action-primary" type="button" disabled={Boolean(mcpDirectAuthBusy) || Boolean(mcpDirectConfigurationError)} onClick={() => { clearMcpDirectFeedback(); setMcpDirectConfirm("switch"); }}>Switch to {mcpDirectModeLabel(mcpDirectSelectedMode).toLowerCase()}</button><button className="settings-action settings-action-danger" type="button" disabled={Boolean(mcpDirectAuthBusy)} onClick={() => { clearMcpDirectFeedback(); setMcpDirectConfirm("disable"); }}>Disable current mode</button></>}
                    </div>
                  </>
                ) : null}
                {mcpDirectAuthError ? <div className="settings-preference-state is-error" role="alert"><span>{mcpDirectAuthError}</span>{!mcpDirectAuth ? <button type="button" onClick={() => setMcpDirectReloadVersion((value) => value + 1)}>Retry</button> : null}</div> : null}
                {mcpDirectAuthMessage && !mcpDirectAuthError ? <p className="settings-preference-state is-success" role="status">{mcpDirectAuthMessage}</p> : null}
              </div>

              <div className="settings-mcp-toggle-list">
                <label
                  className={
                    mcpSettingsSaving
                      ? "settings-toggle-row is-disabled"
                      : "settings-toggle-row"
                  }
                >
                  <span className="settings-toggle-copy">
                    <strong>Enable MCP server</strong>
                    <span>
                      Allow authenticated MCP clients to connect to the
                      exact /mcp endpoint.
                    </span>
                  </span>
                  <input
                    type="checkbox"
                    role="switch"
                    checked={mcpDraft.enabled}
                    disabled={mcpSettingsSaving}
                    onChange={(event) =>
                      updateMcpDraft("enabled", event.target.checked)
                    }
                  />
                  <span className="settings-switch" aria-hidden="true" />
                </label>

                <label
                  className={
                    mcpSettingsSaving
                      ? "settings-toggle-row is-disabled"
                      : "settings-toggle-row"
                  }
                >
                  <span className="settings-toggle-copy">
                    <strong>Read tools</strong>
                    <span>
                      Permit inventory search and details for Parts,
                      Projects, and Reservations.
                    </span>
                  </span>
                  <input
                    type="checkbox"
                    role="switch"
                    checked={mcpDraft.read_tools_enabled}
                    disabled={mcpSettingsSaving}
                    onChange={(event) =>
                      updateMcpDraft(
                        "read_tools_enabled",
                        event.target.checked
                      )
                    }
                  />
                  <span className="settings-switch" aria-hidden="true" />
                </label>

                <label
                  className={
                    mcpSettingsSaving
                      ? "settings-toggle-row is-disabled"
                      : "settings-toggle-row"
                  }
                >
                  <span className="settings-toggle-copy">
                    <strong>Write authorization</strong>
                    <span>
                      Allow clients to request mcp:write permission. No
                      write tools are exposed in this build.
                    </span>
                  </span>
                  <input
                    type="checkbox"
                    role="switch"
                    checked={mcpDraft.write_tools_enabled}
                    disabled={mcpSettingsSaving}
                    onChange={(event) =>
                      updateMcpDraft(
                        "write_tools_enabled",
                        event.target.checked
                      )
                    }
                  />
                  <span className="settings-switch" aria-hidden="true" />
                </label>
              </div>

              <dl className="settings-mcp-summary">
                <div>
                  <dt>Authentication</dt>
                  <dd>OAuth 2.1 or bearer key</dd>
                </div>
                <div>
                  <dt>Transport</dt>
                  <dd>Streamable HTTP</dd>
                </div>
                <div>
                  <dt>Available tools</dt>
                  <dd>6 read-only tools</dd>
                </div>
              </dl>

              <div className="settings-action-row">
                <button
                  className="settings-action settings-action-secondary"
                  type="button"
                  onClick={resetMcpDraft}
                  disabled={!mcpSettingsChanged || mcpSettingsSaving}
                >
                  Reset changes
                </button>
                <button
                  className="settings-action settings-action-primary"
                  type="button"
                  onClick={() => void saveMcpAccess()}
                  disabled={!mcpSettingsChanged || mcpSettingsSaving}
                >
                  {mcpSettingsSaving
                    ? "Saving MCP access..."
                    : "Save MCP access"}
                </button>
              </div>
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
              MCP access settings saved.
            </p>
          ) : null}
        </section>

        <section
          id="settings-data"
          className="card settings-section settings-data-section settings-grid-data"
          aria-labelledby="settings-data-title"
          hidden={activeSettingsSection !== "data"}
        >
          <div className="settings-section-heading">
            <div>
              <span className="card-label">Local data</span>
              <h2 id="settings-data-title">Backup and restore</h2>
              <p>
                Download a complete portable backup or validate and
                restore a previous Part Pilot backup.
              </p>
            </div>
          </div>

          <div className="settings-data-actions">
            <article className="settings-data-action">
              <h3>Download backup</h3>
              <p>
                Creates a validated snapshot while Part Pilot remains
                available. The download contains the database and manifest.
              </p>
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
                              .generated_at_utc
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

            <article className="settings-data-action">
              <h3>Restore backup</h3>
              <p>
                Validate a backup before review. Restoring restarts Part
                Pilot, replaces local data, and signs out every session.
              </p>
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
          </div>

          <hr className="settings-data-divider" />

          <div className="settings-data-reset-heading">
            <div>
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
        </section>
      </div>

      {mcpDirectConfirm ? (
        <div className="settings-security-dialog-backdrop" data-partpilot-mcp-direct-security-dialog="PARTPILOT:MCP_DIRECT_SECURITY_DIALOG:V620">
          <section className={mcpDirectConfirm === "disable" ? "settings-security-dialog is-danger" : "settings-security-dialog"} role="dialog" aria-modal="true" aria-labelledby="settings-mcp-direct-action-dialog-title" aria-describedby="settings-mcp-direct-action-dialog-description">
            <header><span className="card-label">MCP direct authentication</span><h2 id="settings-mcp-direct-action-dialog-title">{mcpDirectConfirm === "disable" ? "Disable direct authentication?" : mcpDirectConfirm === "switch" ? `Switch to ${mcpDirectModeLabel(mcpDirectSelectedMode).toLowerCase()}?` : mcpDirectConfirm === "apply_networks" ? "Apply trusted-network changes?" : mcpDirectConfirm === "create" ? mcpDirectSelectedMode === "trusted_network" ? "Enable trusted-network authentication?" : `Create ${mcpDirectModeLabel(mcpDirectSelectedMode).toLowerCase()}?` : mcpDirectHeaderChanged ? "Apply the header and rotate the key?" : `Rotate the ${mcpDirectModeLabel(mcpDirectSelectedMode).toLowerCase()}?`}</h2></header>
            <div className="settings-security-dialog-content">
              <p id="settings-mcp-direct-action-dialog-description">{mcpDirectConfirm === "disable" ? "Clients using the active direct method will be rejected immediately. OAuth clients are unaffected." : mcpDirectSelectedMode === "trusted_network" ? "Removed networks lose access immediately; added networks gain keyless MCP access. OAuth clients are unaffected." : mcpDirectConfirm === "create" ? "A new credential will be generated and displayed in this dialog. Copy it into the MCP client before closing the result." : "The active direct credential will stop working immediately. The replacement credential will be displayed in this dialog. OAuth clients are unaffected."}</p>
              <dl className="settings-security-dialog-summary"><div><dt>Selected mode</dt><dd>{mcpDirectModeLabel(mcpDirectSelectedMode)}</dd></div><div><dt>Current mode</dt><dd>{mcpDirectConfiguredMode ? mcpDirectModeLabel(mcpDirectConfiguredMode) : "Disabled"}</dd></div></dl>
              {mcpDirectAuthError ? <p className="form-error" role="alert">{mcpDirectAuthError}</p> : null}
            </div>
            <footer><button className="settings-action settings-action-secondary" type="button" disabled={Boolean(mcpDirectAuthBusy)} onClick={() => setMcpDirectConfirm(null)}>Cancel</button><button className={mcpDirectConfirm === "disable" ? "settings-action settings-action-danger" : "settings-action settings-action-primary"} type="button" disabled={Boolean(mcpDirectAuthBusy) || (mcpDirectConfirm !== "disable" && Boolean(mcpDirectConfigurationError))} onClick={() => void (mcpDirectConfirm === "disable" ? disableMcpDirectKey() : configureMcpDirectSelection())}>{mcpDirectAuthBusy ? "Working..." : mcpDirectConfirm === "disable" ? "Disable mode" : mcpDirectConfirm === "switch" ? "Switch mode" : mcpDirectConfirm === "apply_networks" ? "Apply networks" : mcpDirectConfirm === "create" ? mcpDirectSelectedMode === "trusted_network" ? "Enable trusted network" : "Create credential" : mcpDirectHeaderChanged ? "Apply & rotate" : "Rotate key"}</button></footer>
          </section>
        </div>
      ) : null}

      {mcpDirectCredentialDialogOpen && mcpDirectKey && mcpDirectConfiguredMode && mcpDirectConfiguredMode !== "trusted_network" ? (
        <div className="settings-security-dialog-backdrop" data-partpilot-mcp-direct-credential-dialog="PARTPILOT:MCP_DIRECT_CREDENTIAL_DIALOG:V620">
          <section className="settings-security-dialog" role="dialog" aria-modal="true" aria-labelledby="settings-mcp-direct-credential-dialog-title">
            <header><span className="card-label">MCP direct credential</span><h2 id="settings-mcp-direct-credential-dialog-title">{mcpDirectModeLabel(mcpDirectConfiguredMode)} ready</h2><p>Copy the credential into the MCP client before closing this dialog.</p></header>
            <div className="settings-security-dialog-content"><label className="settings-security-credential-field" htmlFor="settings-mcp-direct-dialog-key"><span>{mcpDirectConfiguredMode === "custom_header" ? "Custom-header key" : "Bearer key"}</span><input id="settings-mcp-direct-dialog-key" type={mcpDirectKeyVisible ? "text" : "password"} value={mcpDirectKey} readOnly spellCheck={false} autoComplete="off" onFocus={(event) => event.currentTarget.select()} /></label><p>Treat this value like a password. Never paste it into logs, screenshots, issue reports, or chat messages.</p>{mcpDirectAuthError ? <p className="form-error" role="alert">{mcpDirectAuthError}</p> : null}</div>
            <footer><button className="settings-action settings-action-secondary" type="button" onClick={() => setMcpDirectKeyVisible((value) => !value)}>{mcpDirectKeyVisible ? "Hide" : "Show"}</button><button className="settings-action settings-action-primary" type="button" onClick={() => void copyMcpDirectKey()}>{mcpDirectKeyCopied ? "Copied" : "Copy key"}</button><button className="settings-action settings-action-secondary" type="button" onClick={() => { setMcpDirectCredentialDialogOpen(false); setMcpDirectKey(null); setMcpDirectKeyVisible(false); setMcpDirectKeyCopied(false); }}>Done</button></footer>
          </section>
        </div>
      ) : null}

      {mcpOAuthCredential ? (
        <div className="settings-mcp-oauth-backdrop" data-partpilot-mcp-oauth-credential-dialog="PARTPILOT:MCP_OAUTH_ONE_TIME_CREDENTIAL_DIALOG:V569">
          <section className="settings-mcp-oauth-dialog settings-mcp-oauth-credential-dialog" role="dialog" aria-modal="true" aria-labelledby="settings-mcp-oauth-credential-title" aria-describedby="settings-mcp-oauth-credential-description">
            <header><p className="eyebrow">OAuth client registered</p><h2 id="settings-mcp-oauth-credential-title">Save {mcpOAuthCredential.client_name} credentials</h2></header>
            <div className="settings-mcp-oauth-dialog-content">
              <p id="settings-mcp-oauth-credential-description">Copy these values into the client now.{mcpOAuthCredential.client_secret ? " The client secret is shown only in this result and cannot be retrieved later." : " This public client does not use a client secret."}</p>
              <div className="settings-mcp-oauth-credential-field"><label htmlFor="settings-mcp-oauth-client-id">Client ID</label><div><input id="settings-mcp-oauth-client-id" type="text" value={mcpOAuthCredential.client_id} readOnly spellCheck={false} autoComplete="off" onFocus={(event) => event.currentTarget.select()} /><button className="settings-action settings-action-secondary" type="button" onClick={() => void copyMcpOAuthCredential(mcpOAuthCredential.client_id, "client_id")}>{mcpOAuthCredentialCopied === "client_id" ? "Copied" : "Copy ID"}</button></div></div>
              {mcpOAuthCredential.client_secret ? <div className="settings-mcp-oauth-credential-field is-secret"><label htmlFor="settings-mcp-oauth-client-secret">Client secret</label><div><input id="settings-mcp-oauth-client-secret" type={mcpOAuthSecretVisible ? "text" : "password"} value={mcpOAuthCredential.client_secret} readOnly spellCheck={false} autoComplete="off" onFocus={(event) => event.currentTarget.select()} /><button className="settings-action settings-action-secondary" type="button" onClick={() => setMcpOAuthSecretVisible((value) => !value)}>{mcpOAuthSecretVisible ? "Hide" : "Show"}</button><button className="settings-action settings-action-secondary" type="button" onClick={() => void copyMcpOAuthCredential(mcpOAuthCredential.client_secret ?? "", "client_secret")}>{mcpOAuthCredentialCopied === "client_secret" ? "Copied" : "Copy secret"}</button></div></div> : null}
              <dl><div><dt>Record</dt><dd>#{mcpOAuthCredential.database_id}</dd></div><div><dt>Client type</dt><dd>{mcpOAuthCredential.client_type === "public" ? "Public" : "Confidential"}</dd></div><div><dt>Token auth</dt><dd>{mcpOAuthCredential.token_endpoint_auth_method}</dd></div><div><dt>Redirect URI</dt><dd>{mcpOAuthCredential.redirect_uris.join(", ")}</dd></div><div><dt>Created</dt><dd>{formatUtc(mcpOAuthCredential.created_at)}</dd></div></dl>
              {mcpOAuthCredential.client_secret ? <p className="settings-mcp-oauth-secret-warning">Closing this result permanently removes the plaintext secret from this page. Part Pilot stores only its digest.</p> : null}
            </div>
            <footer><button className="settings-action settings-action-primary" type="button" autoFocus onClick={closeMcpOAuthCredentialDialog}>I saved the credentials</button></footer>
          </section>
        </div>
      ) : null}

      {mcpOAuthRevokeTarget ? (
        <div className="settings-mcp-oauth-backdrop" data-partpilot-mcp-oauth-revoke-dialog="PARTPILOT:MCP_OAUTH_CLIENT_REVOKE_DIALOG:V569">
          <section className="settings-mcp-oauth-dialog" role="dialog" aria-modal="true" aria-labelledby="settings-mcp-oauth-dialog-title" aria-describedby="settings-mcp-oauth-dialog-description">
            <header><p className="eyebrow">{mcpOAuthRevokeTarget.status === "connected" ? "Connected OAuth client" : "Registered OAuth client"}</p><h2 id="settings-mcp-oauth-dialog-title">Revoke {mcpOAuthRevokeTarget.client_name}?</h2></header>
            <div className="settings-mcp-oauth-dialog-content"><p id="settings-mcp-oauth-dialog-description">{mcpOAuthRevokeTarget.status === "connected" ? "The client will be disconnected immediately. Active tokens and consent will stop working, but Part Pilot data will not be removed." : "This registration will be disabled before its first authorization. Part Pilot data will not be removed."}</p><dl><div><dt>Client</dt><dd>{mcpOAuthRevokeTarget.client_name}</dd></div><div><dt>Origin</dt><dd>{mcpOAuthRevokeTarget.redirect_origins.join(", ")}</dd></div><div><dt>Status</dt><dd>{mcpOAuthRevokeTarget.status === "connected" ? "Connected" : "Registered"}</dd></div><div><dt>Last used</dt><dd>{mcpOAuthRevokeTarget.last_used_at ? formatUtc(mcpOAuthRevokeTarget.last_used_at) : "Never"}</dd></div></dl><p className="settings-mcp-oauth-warning">{mcpOAuthRevokeTarget.status === "connected" ? "Confirming this action may interrupt an active request from this client." : "Confirming this action permanently disables this registration."}</p>{mcpOAuthRevokeError ? <p className="form-error" role="alert">{mcpOAuthRevokeError}</p> : null}</div>
            <footer><button className="settings-action settings-action-secondary" type="button" autoFocus disabled={mcpOAuthRevokingId !== null} onClick={closeMcpOAuthRevokeDialog}>Keep client</button><button className="settings-action settings-action-danger" type="button" disabled={mcpOAuthRevokingId !== null} onClick={() => void confirmMcpOAuthRevocation()}>{mcpOAuthRevokingId !== null ? "Revoking..." : mcpOAuthRevokeTarget.status === "connected" ? "Revoke access" : "Revoke client"}</button></footer>
          </section>
        </div>
      ) : null}

      {restoreDialogOpen && restoreValidation ? (
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
                      <dd>{formatUtc(restoreValidation.backup_created_at_utc)}</dd>
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
                      <dd>{formatUtc(restoreValidation.expires_at_utc)}</dd>
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

      {resetDialogOpen ? (
        <div
          className="settings-reset-backdrop"
          data-partpilot-reset-dialog="PARTPILOT:SETTINGS_RESET_DIALOG:V412"
          data-partpilot-reset-refinement="PARTPILOT:SETTINGS_RESET_DIALOG_REFINEMENT:V415"
        >
          <section
            className="settings-reset-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="settings-reset-dialog-title"
            aria-describedby="settings-reset-dialog-description"
          >
            <header>
              <p className="eyebrow">Final confirmation</p>
              <h2 id="settings-reset-dialog-title">
                Erase the Part Pilot database?
              </h2>
            </header>
            <div className="settings-reset-dialog-content">
              <p id="settings-reset-dialog-description">
                This immediately removes every local database record
                and signs you out. This action cannot be undone.
              </p>
              <dl>
                <div>
                  <dt>Scope</dt>
                  <dd>Accounts, inventory, workflows, history, settings</dd>
                </div>
              </dl>
              <label className="settings-reset-confirmation">
                <span>
                  Type <code>{RESET_CONFIRMATION}</code> to continue
                </span>
                <input
                  type="text"
                  value={confirmation}
                  onChange={(event) => {
                    setConfirmation(event.target.value);
                    setResetError(null);
                  }}
                  placeholder={RESET_CONFIRMATION}
                  autoComplete="off"
                  spellCheck={false}
                  autoFocus
                  aria-invalid={Boolean(resetError)}
                />
              </label>
              {resetError ? (
                <p className="form-error" role="alert">
                  {resetError}
                </p>
              ) : null}
            </div>
            <footer>
              <button
                className="settings-action settings-action-secondary"
                type="button"
                disabled={isResetting}
                onClick={closeDatabaseResetDialog}
              >
                Keep existing data
              </button>
              <button
                className="danger-button"
                type="button"
                disabled={!canReset}
                onClick={() =>
                  void confirmDatabaseReset()
                }
              >
                {isResetting
                  ? "Erasing database..."
                  : "Erase database permanently"}
              </button>
            </footer>
          </section>
        </div>
      ) : null}
    </div>
  );
}
