import {
  useEffect,
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
  getReservationSettings,
  getSearchSettings,
  updateReservationSettings,
  updateSearchSettings
} from "../services/settingsClient";
import type {
  AppearanceTheme,
  ReservationExpiryMode,
  ReservationSettings,
  SearchSettings
} from "../types/settings";
import "./Settings.css";

const RESET_CONFIRMATION = "RESET PART PILOT";

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

  const canReset =
    confirmation === RESET_CONFIRMATION && !isResetting;

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
        <a href="#settings-appearance">Appearance</a>
        <a href="#settings-inventory">Inventory</a>
        <a href="#settings-reservations">Reservations</a>
        <a href="#settings-data">Data</a>
      </nav>

      <section
        id="settings-appearance"
        className="card settings-section settings-appearance-section"
        aria-labelledby="settings-appearance-title"
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
          className="card settings-section settings-danger-section settings-grid-data"
          aria-labelledby="settings-data-title"
        >
          <div className="settings-section-heading">
            <div>
              <span className="card-label">Local data</span>
              <h2 id="settings-data-title">Database reset</h2>
              <p>
                Return this installation to first-run setup. Built-in
                part types, templates, and default settings are recreated.
              </p>
            </div>
            <span className="settings-danger-badge">
              Permanent action
            </span>
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
