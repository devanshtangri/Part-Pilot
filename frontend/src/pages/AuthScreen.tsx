import { FormEvent, useMemo, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import {
  detectDefaultCurrency,
  detectTimezone,
  getCurrencyOptions,
  getTimezoneOptions
} from "../utils/setupDefaults";

const USERNAME_ALLOWED_PATTERN = /^[a-z0-9._]+$/;

function cleanUsername(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9._]/g, "");
}

export function AuthScreen() {
  const {
    accountExists,
    setup,
    login,
    authError,
    clearAuthError
  } = useAuth();

  const isSetupMode = accountExists === false;
  const currencyOptions = useMemo(() => getCurrencyOptions(), []);
  const timezoneOptions = useMemo(() => getTimezoneOptions(), []);

  const [displayName, setDisplayName] = useState("");
  const [username, setUsername] = useState("");
  const [defaultCurrency, setDefaultCurrency] = useState(() =>
    detectDefaultCurrency()
  );
  const [timezone, setTimezone] = useState(() => detectTimezone());
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const visibleError = localError ?? authError;

  const canSubmit = useMemo(() => {
    if (!username || !password || !USERNAME_ALLOWED_PATTERN.test(username)) {
      return false;
    }

    if (isSetupMode) {
      return (
        Boolean(displayName.trim()) &&
        Boolean(defaultCurrency) &&
        Boolean(timezone) &&
        password.length >= 8 &&
        password === confirmPassword
      );
    }

    return true;
  }, [
    confirmPassword,
    defaultCurrency,
    displayName,
    isSetupMode,
    password,
    timezone,
    username
  ]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearAuthError();
    setLocalError(null);

    if (!USERNAME_ALLOWED_PATTERN.test(username)) {
      setLocalError(
        "Username can only contain lowercase letters, numbers, period, and underscore."
      );
      return;
    }

    if (isSetupMode && !displayName.trim()) {
      setLocalError("Display name is required.");
      return;
    }

    if (isSetupMode && !defaultCurrency) {
      setLocalError("Select a default currency.");
      return;
    }

    if (isSetupMode && !timezone) {
      setLocalError("Select a timezone.");
      return;
    }

    if (isSetupMode && password.length < 8) {
      setLocalError("Password must be at least 8 characters.");
      return;
    }

    if (isSetupMode && password !== confirmPassword) {
      setLocalError("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);

    try {
      if (isSetupMode) {
        await setup({
          displayName: displayName.trim(),
          username,
          password,
          defaultCurrency,
          timezone
        });
      } else {
        await login({ username, password });
      }
    } catch (error) {
      setLocalError(
        error instanceof Error ? error.message : "Authentication failed"
      );
    } finally {
      setIsSubmitting(false);
    }
  }

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
              <p className="eyebrow">
                {isSetupMode ? "First-run setup" : "Local access"}
              </p>
              <h1>{isSetupMode ? "Set up Part Pilot" : "Welcome back"}</h1>
              <p>
                {isSetupMode
                  ? "Create the owner account and confirm the detected regional defaults."
                  : "Sign in with the local account for this Part Pilot installation."}
              </p>
            </div>
          </div>

          <dl className="auth-facts">
            <div>
              <dt>Mode</dt>
              <dd>Single user</dd>
            </div>
            <div>
              <dt>Storage</dt>
              <dd>Local database</dd>
            </div>
            <div>
              <dt>Access</dt>
              <dd>Private installation</dd>
            </div>
          </dl>
        </section>

        <section
          className="auth-form-panel"
          aria-label={isSetupMode ? "Create owner account" : "Sign in"}
        >
          <header className="auth-form-header">
            <p className="eyebrow">
              {isSetupMode ? "Owner account" : "Account"}
            </p>
            <h2>{isSetupMode ? "Create account" : "Sign in"}</h2>
            <p>
              {isSetupMode
                ? "Add the owner account and verify the installation defaults."
                : "Enter your username and password."}
            </p>
          </header>

          <form className="auth-form" onSubmit={handleSubmit}>
            {isSetupMode ? (
              <label className="field-group">
                <span>Display name</span>
                <input
                  type="text"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder="Your display name"
                  autoComplete="name"
                />
              </label>
            ) : null}

            <label className="field-group">
              <span>Username</span>
              <input
                type="text"
                value={username}
                onChange={(event) =>
                  setUsername(cleanUsername(event.target.value))
                }
                placeholder="username"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                autoComplete="username"
              />
              {isSetupMode ? (
                <small>
                  Lowercase letters, numbers, period, and underscore. No spaces.
                </small>
              ) : null}
            </label>

            {isSetupMode ? (
              <div className="field-row">
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
                  <small>Current GMT offset is shown for each timezone.</small>
                </label>
              </div>
            ) : null}

            <label className="field-group">
              <span>Password</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder={isSetupMode ? "Minimum 8 characters" : "Password"}
                autoComplete={
                  isSetupMode ? "new-password" : "current-password"
                }
              />
            </label>

            {isSetupMode ? (
              <label className="field-group">
                <span>Confirm password</span>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(event) =>
                    setConfirmPassword(event.target.value)
                  }
                  placeholder="Repeat password"
                  autoComplete="new-password"
                />
              </label>
            ) : null}

            {visibleError ? <p className="form-error">{visibleError}</p> : null}

            <button
              className="primary-button"
              type="submit"
              disabled={!canSubmit || isSubmitting}
            >
              {isSubmitting
                ? "Working..."
                : isSetupMode
                  ? "Create account"
                  : "Sign in"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
