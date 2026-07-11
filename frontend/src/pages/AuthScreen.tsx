import { FormEvent, useMemo, useState } from "react";

import { useAuth } from "../auth/AuthContext";

const USERNAME_ALLOWED_PATTERN = /^[a-z0-9._]+$/;

function cleanUsername(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9._]/g, "");
}

export function AuthScreen() {
  const { setupComplete, setup, login, authError, clearAuthError } = useAuth();
  const isSetupMode = setupComplete === false;

  const [displayName, setDisplayName] = useState("");
  const [username, setUsername] = useState("");
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
      return Boolean(displayName.trim()) && password.length >= 8 && password === confirmPassword;
    }

    return true;
  }, [confirmPassword, displayName, isSetupMode, password, username]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearAuthError();
    setLocalError(null);

    if (!USERNAME_ALLOWED_PATTERN.test(username)) {
      setLocalError("Username can only contain letters, numbers, period, and underscore.");
      return;
    }

    if (isSetupMode && !displayName.trim()) {
      setLocalError("Display name is required.");
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
          password
        });
      } else {
        await login({ username, password });
      }
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : "Authentication failed");
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
              <p className="eyebrow">{isSetupMode ? "First-run setup" : "Local access"}</p>
              <h1>{isSetupMode ? "Set up Part Pilot" : "Welcome back"}</h1>
              <p>
                {isSetupMode
                  ? "Create the owner account for this installation. Your inventory remains on this server."
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

        <section className="auth-form-panel" aria-label={isSetupMode ? "Create owner account" : "Sign in"}>
          <header className="auth-form-header">
            <p className="eyebrow">{isSetupMode ? "Owner account" : "Account"}</p>
            <h2>{isSetupMode ? "Create account" : "Sign in"}</h2>
            <p>
              {isSetupMode
                ? "Add a display name, username, and password."
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
                onChange={(event) => setUsername(cleanUsername(event.target.value))}
                placeholder="username"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                autoComplete="username"
              />
              {isSetupMode ? (
                <small>Lowercase letters, numbers, period, and underscore. No spaces.</small>
              ) : null}
            </label>

            <label className="field-group">
              <span>Password</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder={isSetupMode ? "Minimum 8 characters" : "Password"}
                autoComplete={isSetupMode ? "new-password" : "current-password"}
              />
            </label>

            {isSetupMode ? (
              <label className="field-group">
                <span>Confirm password</span>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  placeholder="Repeat password"
                  autoComplete="new-password"
                />
              </label>
            ) : null}

            {visibleError ? <p className="form-error">{visibleError}</p> : null}

            <button className="primary-button" type="submit" disabled={!canSubmit || isSubmitting}>
              {isSubmitting ? "Working..." : isSetupMode ? "Create account" : "Sign in"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
