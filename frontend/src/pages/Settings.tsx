import { FormEvent, useEffect, useState } from "react";

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
  ReservationExpiryMode,
  ReservationSettings,
  SearchSettings
} from "../types/settings";
import "./Settings.css";

const RESET_CONFIRMATION = "RESET PART PILOT";

export function Settings() {
  const { token } = useAuth();
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
  const [reservationReloadVersion, setReservationReloadVersion] = useState(0);
  const [confirmation, setConfirmation] = useState("");
  const [isResetting, setIsResetting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canReset =
    confirmation === RESET_CONFIRMATION && !isResetting;
  const reservationSettingsChanged = Boolean(
    reservationSettings &&
      reservationDraft &&
      (reservationSettings.expiry_mode !== reservationDraft.expiry_mode ||
        reservationSettings.default_days !== reservationDraft.default_days)
  );
  const reservationDaysError =
    reservationDraft?.expiry_mode === "default" &&
    (!Number.isInteger(reservationDraft.default_days) ||
      Number(reservationDraft.default_days) < 1 ||
      Number(reservationDraft.default_days) > 3650)
      ? "Enter a whole number from 1 to 3650 days."
      : null;

  // PATCH 194: load the out-of-stock grouping preference
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

  // PARTPILOT:RESERVATION_EXPIRY_SETTINGS_UI:V362
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

  function chooseReservationExpiryMode(
    expiryMode: ReservationExpiryMode
  ): void {
    if (!reservationDraft || reservationSettingsSaving) {
      return;
    }
    setReservationDraft({
      expiry_mode: expiryMode,
      default_days:
        expiryMode === "none" ? null : reservationDraft.default_days
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
      const saved = await updateReservationSettings(token, reservationDraft);
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

  async function handleReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (confirmation !== RESET_CONFIRMATION) {
      setError(`Type ${RESET_CONFIRMATION} exactly to continue.`);
      return;
    }

    const accepted = window.confirm(
      "This will permanently erase every Part Pilot database record, " +
        "including the user account, inventory, projects, reservations, " +
        "history, settings, and sessions. Continue?"
    );

    if (!accepted) {
      return;
    }

    const token = localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
    if (!token) {
      setError("Your session is missing. Sign in again before resetting.");
      return;
    }

    setIsResetting(true);

    try {
      await resetApplicationDatabase(token, confirmation);
      localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
      window.location.replace("/");
    } catch (caught) {
      setError(
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
    >
      <header className="page-header">
        <p className="eyebrow">Application</p>
        <h1>Settings</h1>
        <p>Configure this Part Pilot installation.</p>
      </header>

      <section
        className="card settings-section settings-search-section"
        aria-labelledby="settings-search-title"
      >
        <span className="card-label">Inventory search</span>
        <h2 id="settings-search-title">Out-of-stock results</h2>
        <p>
          Control whether matching zero-stock parts appear in a separate
          section below normal Stored Parts results. The explicit Out filter
          remains available either way.
        </p>

        {searchSettingsLoading ? (
          <p className="settings-preference-state" role="status">
            Loading search preference...
          </p>
        ) : null}

        {!searchSettingsLoading && searchSettings ? (
          <label
            className={
              searchSettingsSaving
                ? "settings-toggle-row is-disabled"
                : "settings-toggle-row"
            }
          >
            <span className="settings-toggle-copy">
              <strong>Show a separate out-of-stock section</strong>
              <span>
                Keep zero-stock matches below available and low-stock parts
                when the All filter is selected.
              </span>
            </span>
            <input
              type="checkbox"
              role="switch"
              checked={searchSettings.show_out_of_stock_section}
              onChange={(event) =>
                void handleOutOfStockPreference(
                  event.target.checked
                )
              }
              disabled={searchSettingsSaving}
              aria-label="Show a separate out-of-stock section"
            />
            <span className="settings-switch" aria-hidden="true" />
          </label>
        ) : null}

        {searchSettingsError ? (
          <p
            className="settings-preference-state is-error"
            role="alert"
          >
            {searchSettingsError}
          </p>
        ) : null}

        {searchSettingsSaved && !searchSettingsError ? (
          <p
            className="settings-preference-state is-success"
            role="status"
          >
            Search preference saved.
          </p>
        ) : null}
      </section>

      <section
        className="card settings-section settings-reservation-section"
        aria-labelledby="settings-reservation-title"
        data-partpilot-marker="PARTPILOT:RESERVATION_EXPIRY_SETTINGS_UI:V362"
      >
        <span className="card-label">Reservations</span>
        <h2 id="settings-reservation-title">Reservation defaults</h2>
        <p>
          Choose whether new manual reservations start with an expiry. The
          suggested value can always be changed or cleared before creation.
          Existing reservations are never rewritten by this setting.
        </p>

        {reservationSettingsLoading ? (
          <p className="settings-preference-state" role="status">
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
                aria-checked={reservationDraft.expiry_mode === "none"}
                className={
                  reservationDraft.expiry_mode === "none" ? "is-active" : ""
                }
                onClick={() => chooseReservationExpiryMode("none")}
                disabled={reservationSettingsSaving}
              >
                No automatic expiry
              </button>
              <button
                type="button"
                role="radio"
                aria-checked={reservationDraft.expiry_mode === "default"}
                className={
                  reservationDraft.expiry_mode === "default"
                    ? "is-active"
                    : ""
                }
                onClick={() => chooseReservationExpiryMode("default")}
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
                    value={reservationDraft.default_days ?? ""}
                    onChange={(event) => {
                      const value = event.currentTarget.value;
                      setReservationDraft({
                        expiry_mode: "default",
                        default_days: value === "" ? null : Number(value)
                      });
                      setReservationSettingsError(null);
                      setReservationSettingsSaved(false);
                    }}
                    aria-invalid={Boolean(reservationDaysError)}
                    aria-describedby="reservation-default-days-help"
                    disabled={reservationSettingsSaving}
                  />
                  <strong>days</strong>
                </span>
                <small id="reservation-default-days-help">
                  Calculated from the moment New reservation is opened.
                </small>
              </label>
            ) : (
              <p className="settings-reservation-summary">
                New reservations will start with no expiry selected.
              </p>
            )}

            {reservationDaysError ? (
              <p className="settings-preference-state is-error" role="alert">
                {reservationDaysError}
              </p>
            ) : null}

            <div className="settings-action-row">
              <button
                className="settings-action settings-action-secondary"
                type="button"
                onClick={resetReservationDraft}
                disabled={
                  !reservationSettingsChanged || reservationSettingsSaving
                }
              >
                Reset changes
              </button>
              <button
                className="settings-action settings-action-primary"
                type="button"
                onClick={() => void saveReservationDefaults()}
                disabled={
                  !reservationSettingsChanged ||
                  reservationSettingsSaving ||
                  Boolean(reservationDaysError)
                }
              >
                {reservationSettingsSaving
                  ? "Saving reservation defaults..."
                  : "Save reservation defaults"}
              </button>
            </div>
          </div>
        ) : null}

        {reservationSettingsError && !reservationDaysError ? (
          <div className="settings-preference-state is-error" role="alert">
            <span>{reservationSettingsError}</span>
            {!reservationDraft ? (
              <button
                type="button"
                onClick={() =>
                  setReservationReloadVersion((value) => value + 1)
                }
              >
                Retry
              </button>
            ) : null}
          </div>
        ) : null}

        {reservationSettingsSaved && !reservationSettingsError ? (
          <p
            className="settings-preference-state is-success"
            role="status"
          >
            Reservation defaults saved.
          </p>
        ) : null}
      </section>

      <section className="card settings-section">
        <span className="card-label">Developer tools</span>
        <h2>Database reset</h2>
        <p>
          Erase all database records and restart Part Pilot from the first-run
          setup screen. Built-in part types, templates, and default settings
          are recreated automatically.
        </p>

        <div className="danger-panel">
          <strong>Permanent action</strong>
          <p>
            This deletes the owner account, all sessions, inventory, projects,
            reservations, history, and application settings. It does not
            delete files stored outside the database.
          </p>

          <form className="danger-reset-form" onSubmit={handleReset}>
            <label className="field-group">
              <span>
                Type <code>{RESET_CONFIRMATION}</code> to confirm
              </span>
              <input
                type="text"
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                placeholder={RESET_CONFIRMATION}
                autoComplete="off"
                spellCheck={false}
              />
            </label>

            {error ? <p className="form-error">{error}</p> : null}

            <button
              className="danger-button"
              type="submit"
              disabled={!canReset}
            >
              {isResetting
                ? "Resetting database..."
                : "Erase database and restart setup"}
            </button>
          </form>
        </div>
      </section>
    </div>
  );
}
