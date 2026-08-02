import {
  useEffect,
  useRef,
  useState
} from "react";

import {
  APPEARANCE_STORAGE_KEY,
  useAppearance
} from "../appearance/AppearanceContext";
import { useAuth } from "../auth/AuthContext";
import {
  AUTH_TOKEN_STORAGE_KEY,
  resetApplicationDatabase
} from "../services/authClient";
import {
  commitRestoreBackup,
  downloadBackup,
  getManualBackupStatus,
  validateRestoreBackup,
  waitForPartPilotReady
} from "../services/backupsClient";
import {
  getReservationSettings,
  getSearchSettings,
  updateReservationSettings,
  updateSearchSettings
} from "../services/settingsClient";
import type {
  ManualBackupStatusResponse,
  RestoreValidationResponse
} from "../types/backups";
import type {
  AppearanceTheme,
  ReservationExpiryMode,
  ReservationSettings,
  SearchSettings
} from "../types/settings";
import "./Settings.css";

const RESET_CONFIRMATION = "RESET PART PILOT";
const RESTORE_CONFIRMATION = "RESTORE";
const MAX_RESTORE_FILE_BYTES = 256 * 1024 * 1024;
const SETTINGS_SECTION_IDS = [
  "appearance",
  "inventory",
  "reservations",
  "data"
] as const;
type SettingsSection = (typeof SETTINGS_SECTION_IDS)[number];

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
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString();
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
  const { token } = useAuth();
  const restoreFileInputRef = useRef<HTMLInputElement | null>(null);
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
      data-partpilot-active-settings-section={activeSettingsSection}
    >
      <header className="page-header settings-page-header">
        <div>
          <p className="eyebrow">Application configuration</p>
          <h1>Settings</h1>
          <p>
            Manage appearance, inventory behavior, reservation defaults,
            and local data controls for this installation.
          </p>
        </div>
      </header>

      <nav
        className="settings-section-nav"
        aria-label="Settings sections"
      >
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
