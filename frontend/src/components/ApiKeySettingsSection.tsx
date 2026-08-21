import { useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import { formatWorkspaceDateTime } from "../utils/dateTime";
import {
  createApiKey,
  getApiKeys,
  revokeApiKey,
  rotateApiKey,
  updateApiKey
} from "../services/apiKeysClient";
import type {
  ApiKeyListResponse,
  ApiKeyScope,
  ApiKeySecretResponse,
  ApiKeySummary
} from "../types/apiKeys";

interface ApiKeySettingsSectionProps {
  token: string | null;
  hidden: boolean;
  liveReloadVersion: number;
}

type ApiKeyEditorMode = "create" | "edit";
type ApiKeySecretAction = "created" | "rotated";
type ApiKeyConfirmation = {
  action: "rotate" | "revoke";
  key: ApiKeySummary;
};

const SCOPE_DETAILS: Record<
  ApiKeyScope,
  { label: string; description: string }
> = {
  "inventory:read": {
    label: "Inventory · Read",
    description: "Search and read Parts, stock and movement history."
  },
  "inventory:write": {
    label: "Inventory · Write",
    description: "Create, edit, adjust, delete, restore and purge Parts."
  },
  "catalogues:read": {
    label: "Catalogues · Read",
    description: "Read Part Types, manufacturers, packages and locations."
  },
  "catalogues:write": {
    label: "Catalogues · Write",
    description: "Create or change reusable catalogue records."
  },
  "projects:read": {
    label: "Projects · Read",
    description: "Read Project records and item plans."
  },
  "projects:write": {
    label: "Projects · Write",
    description: "Create, edit, reserve, consume or cancel Projects."
  },
  "reservations:read": {
    label: "Reservations · Read",
    description: "Read Reservations and their activity."
  },
  "reservations:write": {
    label: "Reservations · Write",
    description: "Create, edit, cancel, consume or expire Reservations."
  },
  "history:read": {
    label: "History · Read",
    description: "Read the system-wide History workspace data."
  }
};

function formatTimestamp(value: string | null, timezone: string | null): string {
  return formatWorkspaceDateTime(value, timezone, "Never");
}

function expiryDraft(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (number: number) => String(number).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
    date.getDate()
  )}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

async function copyText(value: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const field = document.createElement("textarea");
  field.value = value;
  field.style.position = "fixed";
  field.style.opacity = "0";
  document.body.appendChild(field);
  field.select();
  const copied = document.execCommand("copy");
  field.remove();
  if (!copied) throw new Error("Clipboard copy was rejected.");
}

export function ApiKeySettingsSection({
  token,
  hidden,
  liveReloadVersion
}: ApiKeySettingsSectionProps) {
  const { timezone } = useAuth();
  const [collection, setCollection] = useState<ApiKeyListResponse | null>(null);
  const loadedTokenRef = useRef<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [reloadVersion, setReloadVersion] = useState(0);
  const [editorMode, setEditorMode] = useState<ApiKeyEditorMode | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [nameDraft, setNameDraft] = useState("");
  const [scopeDraft, setScopeDraft] = useState<ApiKeyScope[]>([]);
  const [expiryValue, setExpiryValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [editorAttempted, setEditorAttempted] = useState(false);
  const [confirmation, setConfirmation] = useState<ApiKeyConfirmation | null>(null);
  const [actionBusy, setActionBusy] = useState<"rotate" | "revoke" | null>(null);
  const [secret, setSecret] = useState<ApiKeySecretResponse | null>(null);
  const [secretAction, setSecretAction] = useState<ApiKeySecretAction>("created");
  const [secretCopied, setSecretCopied] = useState(false);
  const [secretCopyError, setSecretCopyError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      loadedTokenRef.current = null;
      setCollection(null);
      setLoading(false);
      setError("Your session is unavailable. Sign in again.");
      return;
    }
    let cancelled = false;
    const hasCachedCollection = loadedTokenRef.current === token;
    setLoading(!hasCachedCollection);
    setError(null);
    getApiKeys(token)
      .then((result) => {
        if (!cancelled) {
          loadedTokenRef.current = token;
          setCollection(result);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          if (!hasCachedCollection) setCollection(null);
          setError(
            caught instanceof Error ? caught.message : "Unable to load API keys"
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [liveReloadVersion, reloadVersion, token]);

  const availableScopes = collection?.available_scopes ?? [];
  const readScopes = useMemo(
    () => availableScopes.filter((scope) => scope.endsWith(":read")),
    [availableScopes]
  );
  const visibleKeys = collection?.keys.filter((key) => key.status !== "revoked") ?? [];
  const activeCount = visibleKeys.filter((key) => key.status === "active").length;

  const nameError = editorAttempted && !nameDraft.trim()
    ? "Enter a name for this API key."
    : null;
  const scopeError = editorAttempted && scopeDraft.length === 0
    ? "Select at least one permission."
    : null;
  const expiryError = (() => {
    if (!editorAttempted || !expiryValue) return null;
    const parsed = new Date(expiryValue);
    if (Number.isNaN(parsed.getTime())) return "Enter a valid expiry date and time.";
    if (parsed.getTime() <= Date.now()) return "Expiry must be in the future.";
    return null;
  })();

  function clearFeedback(): void {
    setError(null);
    setMessage(null);
  }

  function openCreateEditor(): void {
    clearFeedback();
    setConfirmation(null);
    setEditorMode("create");
    setEditingId(null);
    setNameDraft("");
    setScopeDraft([]);
    setExpiryValue("");
    setEditorAttempted(false);
  }

  function openEditEditor(key: ApiKeySummary): void {
    clearFeedback();
    setConfirmation(null);
    setEditorMode("edit");
    setEditingId(key.id);
    setNameDraft(key.name);
    setScopeDraft(key.scopes);
    setExpiryValue(expiryDraft(key.expires_at));
    setEditorAttempted(false);
  }

  function closeEditor(): void {
    if (saving) return;
    setEditorMode(null);
    setEditingId(null);
    setEditorAttempted(false);
    setError(null);
  }

  function toggleScope(scope: ApiKeyScope): void {
    setScopeDraft((current) =>
      current.includes(scope)
        ? current.filter((candidate) => candidate !== scope)
        : [...current, scope]
    );
    setError(null);
  }

  async function submitEditor(): Promise<void> {
    if (!token || !editorMode || saving) return;
    setEditorAttempted(true);
    const expiry = expiryValue ? new Date(expiryValue) : null;
    if (
      !nameDraft.trim() ||
      scopeDraft.length === 0 ||
      (expiry && (Number.isNaN(expiry.getTime()) || expiry.getTime() <= Date.now()))
    ) {
      return;
    }

    setSaving(true);
    clearFeedback();
    try {
      const payload = {
        name: nameDraft.trim(),
        scopes: availableScopes.filter((scope) => scopeDraft.includes(scope)),
        expires_at: expiry ? expiry.toISOString() : null
      };
      if (editorMode === "create") {
        const created = await createApiKey(token, payload);
        setSecret(created);
        setSecretAction("created");
        setSecretCopied(false);
        setSecretCopyError(null);
        setMessage(`${created.name} created.`);
      } else if (editingId !== null) {
        const updated = await updateApiKey(token, editingId, payload);
        setMessage(`${updated.name} updated.`);
      }
      setEditorMode(null);
      setEditingId(null);
      setEditorAttempted(false);
      setReloadVersion((value) => value + 1);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save API key");
    } finally {
      setSaving(false);
    }
  }

  async function confirmAction(): Promise<void> {
    if (!token || !confirmation || actionBusy) return;
    setActionBusy(confirmation.action);
    clearFeedback();
    try {
      if (confirmation.action === "rotate") {
        const rotated = await rotateApiKey(token, confirmation.key.id);
        setSecret(rotated);
        setSecretAction("rotated");
        setSecretCopied(false);
        setSecretCopyError(null);
        setMessage(`${rotated.name} rotated.`);
      } else {
        const revoked = await revokeApiKey(token, confirmation.key.id);
        setMessage(`${revoked.name} revoked. The audit record is retained and hidden from this list.`);
      }
      setConfirmation(null);
      setReloadVersion((value) => value + 1);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update API key");
    } finally {
      setActionBusy(null);
    }
  }

  async function copySecret(): Promise<void> {
    if (!secret) return;
    setSecretCopied(false);
    setSecretCopyError(null);
    try {
      await copyText(secret.key);
      setSecretCopied(true);
    } catch (caught) {
      setSecretCopyError(
        caught instanceof Error ? caught.message : "Unable to copy API key"
      );
    }
  }

  return (
    <>
      <section
        id="settings-api"
        className="card settings-section settings-api-section settings-grid-api"
        aria-labelledby="settings-api-title"
        data-partpilot-live-sync="PARTPILOT:API_KEY_INTEGRATION_LIVE_SYNC:V708"
        data-partpilot-background-refresh="PARTPILOT:STABLE_BACKGROUND_REFRESH:V718"
        hidden={hidden}
        data-partpilot-rest-api-keys="PARTPILOT:REST_API_KEY_SETTINGS_UI:V618"
      >
        <div className="settings-section-heading settings-api-heading">
          <div>
            <span className="card-label">Developer access</span>
            <h2 id="settings-api-title">API Access</h2>
            <p>
              Create scoped REST API keys for integrations and automation. Secret
              values are shown only when a key is created or rotated.
            </p>
          </div>
          <div className="settings-api-heading-actions">
            <a
              className="settings-action settings-action-secondary"
              href="/docs"
              target="_blank"
              rel="noopener noreferrer"
            >
              API Documentation ↗
            </a>
            <button
              className="settings-action settings-action-primary"
              type="button"
              disabled={saving || actionBusy !== null}
              onClick={openCreateEditor}
            >
              Create API key
            </button>
          </div>
        </div>

        <div className="settings-api-summary" aria-label="API key summary">
          <div><span>Total keys</span><strong>{visibleKeys.length}</strong></div>
          <div><span>Active</span><strong>{activeCount}</strong></div>
          <div><span>Authentication</span><strong>Bearer token</strong></div>
          <div><span>Administration</span><strong>Session only</strong></div>
        </div>

        {editorMode ? (
          <div className="settings-api-editor">
            <div className="settings-api-editor-heading">
              <div>
                <strong>{editorMode === "create" ? "Create API key" : "Edit API key"}</strong>
                <span>Grant only the permissions this integration actually needs.</span>
              </div>
            </div>
            <div className="settings-api-editor-fields">
              <label>
                <span>Name</span>
                <input
                  type="text"
                  value={nameDraft}
                  maxLength={120}
                  autoComplete="off"
                  disabled={saving}
                  aria-invalid={Boolean(nameError)}
                  placeholder="Workshop dashboard"
                  onChange={(event) => {
                    setNameDraft(event.target.value);
                    setError(null);
                  }}
                />
                {nameError ? <small className="is-error">{nameError}</small> : null}
              </label>
              <label>
                <span>Expiry</span>
                <input
                  type="datetime-local"
                  value={expiryValue}
                  disabled={saving}
                  aria-invalid={Boolean(expiryError)}
                  onChange={(event) => {
                    setExpiryValue(event.target.value);
                    setError(null);
                  }}
                />
                <small className={expiryError ? "is-error" : ""}>
                  {expiryError ?? "Optional. Leave blank for no automatic expiry."}
                </small>
              </label>
            </div>
            <div className="settings-api-permissions">
              <div className="settings-api-permissions-heading">
                <div>
                  <strong>Permissions</strong>
                  <span>{scopeDraft.length} selected</span>
                </div>
                <div>
                  <button
                    type="button"
                    disabled={saving}
                    onClick={() => setScopeDraft(readScopes)}
                  >
                    Read only
                  </button>
                  <button
                    type="button"
                    disabled={saving}
                    onClick={() => setScopeDraft(availableScopes)}
                  >
                    All scopes
                  </button>
                  <button
                    type="button"
                    disabled={saving}
                    onClick={() => setScopeDraft([])}
                  >
                    Clear
                  </button>
                </div>
              </div>
              <div className="settings-api-scope-grid">
                {availableScopes.map((scope) => (
                  <label
                    key={scope}
                    className={scopeDraft.includes(scope) ? "is-selected" : ""}
                  >
                    <input
                      type="checkbox"
                      checked={scopeDraft.includes(scope)}
                      disabled={saving}
                      onChange={() => toggleScope(scope)}
                    />
                    <span>
                      <strong>{SCOPE_DETAILS[scope].label}</strong>
                      <small>{SCOPE_DETAILS[scope].description}</small>
                    </span>
                  </label>
                ))}
              </div>
              {scopeError ? <p className="form-error" role="alert">{scopeError}</p> : null}
            </div>
            <div className="settings-api-editor-actions">
              <button
                className="settings-action settings-action-secondary"
                type="button"
                disabled={saving}
                onClick={closeEditor}
              >
                Cancel
              </button>
              <button
                className="settings-action settings-action-primary"
                type="button"
                disabled={saving}
                onClick={() => void submitEditor()}
              >
                {saving
                  ? editorMode === "create" ? "Creating..." : "Saving..."
                  : editorMode === "create" ? "Create API key" : "Save changes"}
              </button>
            </div>
          </div>
        ) : null}

        {loading ? (
          <p className="settings-preference-state" role="status">Loading API keys...</p>
        ) : null}

        {!loading && visibleKeys.length === 0 ? (
          <div className="settings-api-empty">
            <strong>No API keys yet</strong>
            <span>Create a scoped key when an integration needs REST API access.</span>
          </div>
        ) : null}

        {!loading && collection && visibleKeys.length > 0 ? (
          <div className="settings-api-list">
            {visibleKeys.map((key) => (
              <article className={`settings-api-key is-${key.status}`} key={key.id}>
                <header>
                  <div>
                    <strong>{key.name}</strong>
                    <code>{key.masked_key}</code>
                  </div>
                  <span className={`settings-api-status is-${key.status}`}>
                    {key.status === "active"
                      ? "Active"
                      : key.status === "expired" ? "Expired" : "Revoked"}
                  </span>
                </header>
                <div className="settings-api-scope-chips" aria-label={`${key.name} permissions`}>
                  {key.scopes.map((scope) => <span key={scope}>{scope}</span>)}
                </div>
                <dl>
                  <div><dt>Created</dt><dd>{formatTimestamp(key.created_at, timezone)}</dd></div>
                  <div><dt>Last used</dt><dd>{formatTimestamp(key.last_used_at, timezone)}</dd></div>
                  <div><dt>Expires</dt><dd>{key.expires_at ? formatTimestamp(key.expires_at, timezone) : "Never"}</dd></div>
                  <div><dt>Rotated</dt><dd>{formatTimestamp(key.rotated_at, timezone)}</dd></div>
                </dl>
                <footer>
                  <span>{key.scopes.length} permission{key.scopes.length === 1 ? "" : "s"}</span>
                  <div>
                    <button
                      className="settings-action settings-action-secondary"
                      type="button"
                      disabled={key.status === "revoked" || actionBusy !== null || saving}
                      onClick={() => openEditEditor(key)}
                    >
                      Edit
                    </button>
                    <button
                      className="settings-action settings-action-secondary"
                      type="button"
                      disabled={key.status !== "active" || actionBusy !== null || saving}
                      onClick={() => {
                        clearFeedback();
                        setEditorMode(null);
                        setConfirmation({ action: "rotate", key });
                      }}
                    >
                      Rotate
                    </button>
                    {key.status !== "revoked" ? (
                      <button
                        className="settings-action settings-action-danger"
                        type="button"
                        disabled={actionBusy !== null || saving}
                        onClick={() => {
                          clearFeedback();
                          setEditorMode(null);
                          setConfirmation({ action: "revoke", key });
                        }}
                      >
                        Revoke
                      </button>
                    ) : null}
                  </div>
                </footer>
              </article>
            ))}
          </div>
        ) : null}

        {error ? (
          <div className="settings-preference-state is-error" role="alert">
            <span>{error}</span>
            {!collection && !loading ? (
              <button type="button" onClick={() => setReloadVersion((value) => value + 1)}>
                Retry
              </button>
            ) : null}
          </div>
        ) : null}
        {message && !error ? (
          <p className="settings-preference-state is-success" role="status">{message}</p>
        ) : null}
      </section>

      {confirmation ? (
        <div
          className="settings-security-dialog-backdrop"
          data-partpilot-api-key-security-dialog="PARTPILOT:REST_API_KEY_SECURITY_DIALOG:V620"
        >
          <section
            className={
              confirmation.action === "revoke"
                ? "settings-security-dialog is-danger"
                : "settings-security-dialog"
            }
            role="dialog"
            aria-modal="true"
            aria-labelledby="settings-api-action-dialog-title"
            aria-describedby="settings-api-action-dialog-description"
          >
            <header>
              <span className="card-label">API key security</span>
              <h2 id="settings-api-action-dialog-title">
                {confirmation.action === "rotate"
                  ? `Rotate ${confirmation.key.name}?`
                  : `Revoke ${confirmation.key.name}?`}
              </h2>
            </header>
            <div className="settings-security-dialog-content">
              <p id="settings-api-action-dialog-description">
                {confirmation.action === "rotate"
                  ? "The current secret stops working immediately. The replacement secret will be displayed here once so you can copy it."
                  : "This key will stop authenticating immediately. The revoked audit record is retained securely but removed from the visible API-key list."}
              </p>
              <dl className="settings-security-dialog-summary">
                <div><dt>Key</dt><dd>{confirmation.key.name}</dd></div>
                <div><dt>Permissions</dt><dd>{confirmation.key.scopes.length}</dd></div>
                <div><dt>Last used</dt><dd>{formatTimestamp(confirmation.key.last_used_at, timezone)}</dd></div>
                <div><dt>Expires</dt><dd>{confirmation.key.expires_at ? formatTimestamp(confirmation.key.expires_at, timezone) : "Never"}</dd></div>
              </dl>
              {error ? <p className="form-error" role="alert">{error}</p> : null}
            </div>
            <footer>
              <button className="settings-action settings-action-secondary" type="button" disabled={actionBusy !== null} onClick={() => setConfirmation(null)}>Cancel</button>
              <button className={confirmation.action === "revoke" ? "settings-action settings-action-danger" : "settings-action settings-action-primary"} type="button" disabled={actionBusy !== null} onClick={() => void confirmAction()}>
                {actionBusy ? "Working..." : confirmation.action === "rotate" ? "Rotate key" : "Revoke key"}
              </button>
            </footer>
          </section>
        </div>
      ) : null}

      {secret ? (
        <div className="settings-api-secret-backdrop">
          <section
            className="settings-api-secret-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="settings-api-secret-title"
            data-partpilot-api-secret="PARTPILOT:REST_API_KEY_ONE_TIME_SECRET:V618"
          >
            <header>
              <div>
                <span className="card-label">One-time secret</span>
                <h2 id="settings-api-secret-title">
                  API key {secretAction === "created" ? "created" : "rotated"}
                </h2>
                <p>Copy this secret now. Part Pilot will not show it again.</p>
              </div>
            </header>
            <div className="settings-api-secret-content">
              <div className="settings-api-secret-meta">
                <strong>{secret.name}</strong>
                <span>{secret.scopes.length} permissions · {secret.expires_at ? `expires ${formatTimestamp(secret.expires_at, timezone)}` : "no expiry"}</span>
              </div>
              <label>
                <span>API key</span>
                <input
                  type="text"
                  value={secret.key}
                  readOnly
                  spellCheck={false}
                  autoComplete="off"
                  onFocus={(event) => event.currentTarget.select()}
                />
              </label>
              <p>
                Send it as <code>Authorization: Bearer &lt;API key&gt;</code>. Treat it
                like a password and never place it in logs, screenshots or source control.
              </p>
              {secretCopyError ? <p className="form-error" role="alert">{secretCopyError}</p> : null}
            </div>
            <footer>
              <a
                className="settings-action settings-action-secondary"
                href="/docs"
                target="_blank"
                rel="noopener noreferrer"
              >
                Open API docs ↗
              </a>
              <button
                className="settings-action settings-action-primary"
                type="button"
                onClick={() => void copySecret()}
              >
                {secretCopied ? "Copied" : "Copy API key"}
              </button>
              <button
                className="settings-action settings-action-secondary"
                type="button"
                onClick={() => {
                  setSecret(null);
                  setSecretCopied(false);
                  setSecretCopyError(null);
                }}
              >
                Done
              </button>
            </footer>
          </section>
        </div>
      ) : null}
    </>
  );
}
