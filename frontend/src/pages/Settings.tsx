import { FormEvent, useState } from "react";

import {
  AUTH_TOKEN_STORAGE_KEY,
  resetApplicationDatabase
} from "../services/authClient";

const RESET_CONFIRMATION = "RESET PART PILOT";

export function Settings() {
  const [confirmation, setConfirmation] = useState("");
  const [isResetting, setIsResetting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canReset =
    confirmation === RESET_CONFIRMATION && !isResetting;

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
    <div className="page-stack">
      <header className="page-header">
        <p className="eyebrow">Application</p>
        <h1>Settings</h1>
        <p>Configure this Part Pilot installation.</p>
      </header>

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
