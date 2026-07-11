import { FormEvent, useMemo, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import {
  detectDefaultCurrency,
  detectTimezone,
  getCurrencyOptions,
  getTimezoneOptions
} from "../utils/setupDefaults";

export function SetupPreferencesScreen() {
  const {
    defaultCurrency: savedCurrency,
    timezone: savedTimezone,
    completeSetup,
    authError,
    clearAuthError
  } = useAuth();

  const currencyOptions = useMemo(() => getCurrencyOptions(), []);
  const timezoneOptions = useMemo(() => getTimezoneOptions(), []);

  const [defaultCurrency, setDefaultCurrency] = useState(
    savedCurrency ?? detectDefaultCurrency()
  );
  const [timezone, setTimezone] = useState(
    savedTimezone ?? detectTimezone()
  );
  const [localError, setLocalError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canSubmit = Boolean(defaultCurrency && timezone);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearAuthError();
    setLocalError(null);

    if (!defaultCurrency) {
      setLocalError("Select a default currency.");
      return;
    }

    if (!timezone) {
      setLocalError("Select a timezone.");
      return;
    }

    setIsSubmitting(true);

    try {
      await completeSetup({
        defaultCurrency,
        timezone
      });
    } catch (error) {
      setLocalError(
        error instanceof Error ? error.message : "Unable to save setup"
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  const visibleError = localError ?? authError;

  return (
    <main className="auth-page">
      <div className="auth-window">
        <section className="auth-summary">
          <div>
            <div className="auth-brand-row">
              <div className="brand-mark">P</div>
              <div>
                <strong>Part Pilot</strong>
                <span>Local inventory manager</span>
              </div>
            </div>

            <div className="auth-summary-copy">
              <p className="eyebrow">Installation defaults</p>
              <h1>Finish setup</h1>
              <p>
                Confirm the detected currency and timezone for this
                installation.
              </p>
            </div>
          </div>

          <dl className="auth-facts">
            <div>
              <dt>Currency</dt>
              <dd>Used for part values</dd>
            </div>
            <div>
              <dt>Timezone</dt>
              <dd>Used for local dates</dd>
            </div>
            <div>
              <dt>Scope</dt>
              <dd>This installation</dd>
            </div>
          </dl>
        </section>

        <section
          className="auth-form-panel"
          aria-label="Complete installation setup"
        >
          <header className="auth-form-header">
            <p className="eyebrow">Regional settings</p>
            <h2>Choose defaults</h2>
            <p>
              Part Pilot detected suggested values from this browser.
            </p>
          </header>

          <form className="auth-form" onSubmit={handleSubmit}>
            <label className="field-group">
              <span>Default currency</span>
              <select
                value={defaultCurrency}
                onChange={(event) =>
                  setDefaultCurrency(event.target.value)
                }
              >
                <option value="" disabled>
                  Select currency
                </option>
                {currencyOptions.map((option) => (
                  <option key={option.code} value={option.code}>
                    {option.label}
                  </option>
                ))}
              </select>
              <small>Used for inventory values and price history.</small>
            </label>

            <label className="field-group">
              <span>Timezone</span>
              <select
                value={timezone}
                onChange={(event) => setTimezone(event.target.value)}
              >
                <option value="" disabled>
                  Select timezone
                </option>
                {timezoneOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <small>
                The current GMT offset is shown beside every timezone.
              </small>
            </label>

            {visibleError ? <p className="form-error">{visibleError}</p> : null}

            <button
              className="primary-button"
              type="submit"
              disabled={!canSubmit || isSubmitting}
            >
              {isSubmitting ? "Saving..." : "Save and continue"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
