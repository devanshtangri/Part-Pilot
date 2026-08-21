import { useEffect, useMemo, useRef, useState } from "react";

import { McpClientPermissionsDialog } from "./McpClientPermissionsDialog";
import { useAuth } from "../auth/AuthContext";
import { formatWorkspaceDateTime } from "../utils/dateTime";
import {
  createMcpNamedDirectClient,
  getMcpNamedDirectClients,
  revealMcpNamedDirectClient,
  revokeMcpNamedDirectClient,
  rotateMcpNamedDirectClient,
  updateMcpNamedDirectClient,
  updateMcpNamedDirectClientNetworks,
  updateMcpNamedDirectClientPermissions
} from "../services/settingsClient";
import type {
  McpNamedDirectClient,
  McpNamedDirectClientCreateResponse,
  McpNamedDirectClientKeyResponse,
  McpNamedDirectClientMode
} from "../types/settings";

// PARTPILOT:MCP_NAMED_DIRECT_CLIENTS_UI:V627
const DEFAULT_HEADER = "x-partpilot-mcp-key";

type ConfirmAction =
  | { kind: "rotate"; client: McpNamedDirectClient }
  | { kind: "revoke"; client: McpNamedDirectClient }
  | { kind: "disable"; client: McpNamedDirectClient }
  | { kind: "enable"; client: McpNamedDirectClient };

interface EditorState {
  mode: "create" | "edit";
  client: McpNamedDirectClient | null;
  name: string;
  authMode: McpNamedDirectClientMode;
  headerName: string;
  networks: string;
}

interface CredentialState {
  client: McpNamedDirectClient;
  key: string;
  title: string;
}

interface Props {
  token: string;
  disabled: boolean;
  permissionReloadVersion?: number;
}

function formatUtc(value: string | null, timezone: string | null): string {
  return formatWorkspaceDateTime(value, timezone, "Never");
}

function modeLabel(mode: McpNamedDirectClientMode): string {
  if (mode === "bearer_key") return "Bearer key";
  if (mode === "custom_header") return "Custom header";
  return "Trusted network";
}

function networkLines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
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

export function McpDirectClientsSection({
  token,
  disabled,
  permissionReloadVersion = 0
}: Props) {
  const { timezone } = useAuth();
  const [clients, setClients] = useState<McpNamedDirectClient[]>([]);
  const loadedTokenRef = useRef<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [busy, setBusy] = useState(false);
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [confirm, setConfirm] = useState<ConfirmAction | null>(null);
  const [credential, setCredential] = useState<CredentialState | null>(null);
  const [keyVisible, setKeyVisible] = useState(true);
  const [copied, setCopied] = useState(false);
  const [permissionTarget, setPermissionTarget] = useState<McpNamedDirectClient | null>(null);
  const [permissionSaving, setPermissionSaving] = useState(false);
  const [permissionError, setPermissionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const hasCachedClients = loadedTokenRef.current === token;
    setLoading(!hasCachedClients);
    if (!hasCachedClients) setClients([]);
    setError(null);
    getMcpNamedDirectClients(token)
      .then((result) => {
        if (!cancelled) {
          setClients(result.clients);
          loadedTokenRef.current = token;
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setError(
            caught instanceof Error
              ? caught.message
              : "Unable to load direct clients"
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [permissionReloadVersion, reload, token]);

  useEffect(() => {
    if (disabled) {
      setPermissionTarget(null);
      setPermissionError(null);
    }
  }, [disabled]);

  const editorNetworks = useMemo(
    () => (editor ? networkLines(editor.networks) : []),
    [editor]
  );
  const editorError = editor
    ? !editor.name.trim()
      ? "Enter a client name."
      : editor.authMode === "custom_header" && !editor.headerName.trim()
        ? "Enter a custom HTTP header name."
        : editor.authMode === "trusted_network" && editorNetworks.length === 0
          ? "Enter at least one trusted CIDR."
          : null
    : null;

  function openCreate(): void {
    if (disabled || busy) return;
    setError(null);
    setMessage(null);
    setEditor({
      mode: "create",
      client: null,
      name: "",
      authMode: "bearer_key",
      headerName: DEFAULT_HEADER,
      networks: ""
    });
  }

  function openEdit(client: McpNamedDirectClient): void {
    if (disabled || busy) return;
    setError(null);
    setMessage(null);
    setEditor({
      mode: "edit",
      client,
      name: client.name,
      authMode: client.mode,
      headerName: client.custom_header_name ?? DEFAULT_HEADER,
      networks: client.trusted_networks.join("\n")
    });
  }

  async function submitEditor(): Promise<void> {
    if (!editor || editorError || busy || disabled) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      if (editor.mode === "create") {
        const created: McpNamedDirectClientCreateResponse =
          await createMcpNamedDirectClient(token, {
            name: editor.name.trim(),
            mode: editor.authMode,
            header_name:
              editor.authMode === "custom_header"
                ? editor.headerName.trim().toLowerCase()
                : null,
            networks:
              editor.authMode === "trusted_network" ? editorNetworks : []
          });
        setClients((current) => [...current, created]);
        setEditor(null);
        if (created.key) {
          setCredential({
            client: created,
            key: created.key,
            title: `${created.name} credential ready`
          });
          setKeyVisible(true);
          setCopied(false);
        } else {
          setMessage(`${created.name} created.`);
        }
      } else if (editor.client) {
        let updated = await updateMcpNamedDirectClient(
          token,
          editor.client.id,
          { name: editor.name.trim() }
        );
        if (updated.mode === "trusted_network") {
          updated = await updateMcpNamedDirectClientNetworks(
            token,
            updated.id,
            editorNetworks
          );
        }
        setClients((current) =>
          current.map((item) => (item.id === updated.id ? updated : item))
        );
        setEditor(null);
        setMessage(`${updated.name} updated.`);
      }
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to save direct client"
      );
    } finally {
      setBusy(false);
    }
  }

  async function reveal(client: McpNamedDirectClient): Promise<void> {
    if (disabled || busy || client.mode === "trusted_network") return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result: McpNamedDirectClientKeyResponse =
        await revealMcpNamedDirectClient(token, client.id);
      setCredential({ client: result, key: result.key, title: `${result.name} credential` });
      setKeyVisible(true);
      setCopied(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to reveal credential");
    } finally {
      setBusy(false);
    }
  }

  async function confirmAction(): Promise<void> {
    if (!confirm || disabled || busy) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      if (confirm.kind === "rotate") {
        const result = await rotateMcpNamedDirectClient(
          token,
          confirm.client.id,
          confirm.client.mode === "custom_header"
            ? { header_name: confirm.client.custom_header_name }
            : {}
        );
        setClients((current) =>
          current.map((item) => (item.id === result.id ? result : item))
        );
        setConfirm(null);
        setCredential({
          client: result,
          key: result.key,
          title: `${result.name} rotated`
        });
        setKeyVisible(true);
        setCopied(false);
        return;
      }
      if (confirm.kind === "revoke") {
        const result = await revokeMcpNamedDirectClient(token, confirm.client.id);
        setClients(result.clients);
        setConfirm(null);
        setMessage(
          `${confirm.client.name} revoked. Its backend audit record is retained and hidden from this list.`
        );
        return;
      }
      const updated = await updateMcpNamedDirectClient(
        token,
        confirm.client.id,
        { enabled: confirm.kind === "enable" }
      );
      setClients((current) =>
        current.map((item) => (item.id === updated.id ? updated : item))
      );
      setConfirm(null);
      setMessage(
        `${updated.name} ${updated.enabled ? "enabled" : "disabled"}.`
      );
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to update direct client"
      );
    } finally {
      setBusy(false);
    }
  }

  async function copyCredential(): Promise<void> {
    if (!credential) return;
    try {
      await copyText(credential.key);
      setCopied(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to copy credential");
    }
  }


  function openPermissions(client: McpNamedDirectClient): void {
    if (disabled || busy || permissionSaving) return;
    setPermissionError(null);
    setMessage(null);
    setPermissionTarget(client);
  }

  async function savePermissions(deniedTools: string[]): Promise<void> {
    if (!permissionTarget || disabled || permissionSaving) return;
    const target = permissionTarget;
    setPermissionSaving(true);
    setPermissionError(null);
    try {
      const result = await updateMcpNamedDirectClientPermissions(
        token,
        target.id,
        { denied_tools: deniedTools }
      );
      setClients((current) =>
        current.map((item) =>
          item.id === target.id
            ? {
                ...item,
                denied_tools: result.denied_tools,
                tool_permissions: result.tools
              }
            : item
        )
      );
      setPermissionTarget(null);
      setMessage(`${target.name} permissions saved.`);
    } catch (caught) {
      setPermissionError(
        caught instanceof Error ? caught.message : "Unable to save client permissions"
      );
    } finally {
      setPermissionSaving(false);
    }
  }

  return (
    <section
      className={`settings-mcp-named-direct${disabled ? " is-disabled" : ""}`}
      data-partpilot-mcp-named-direct-clients="PARTPILOT:MCP_NAMED_DIRECT_CLIENTS_UI:V627"
      aria-disabled={disabled}
    >
      <div className="settings-mcp-named-direct-heading">
        <div>
          <strong>Named direct clients</strong>
          <span>
            Give non-OAuth clients independent credentials or trusted-network identities.
            Revoking one client does not affect the others or OAuth.
          </span>
        </div>
        <button
          className="settings-action settings-action-primary"
          type="button"
          disabled={disabled || busy}
          onClick={openCreate}
        >
          Add direct client
        </button>
      </div>

      {disabled ? (
        <p className="settings-mcp-named-direct-note">
          Enable the MCP server and Allow direct MCP clients to manage clients.
        </p>
      ) : null}
      {loading ? <p className="settings-mcp-named-direct-note">Loading direct clients...</p> : null}
      {!loading && clients.length === 0 ? (
        <p className="settings-mcp-named-direct-note">No named direct clients configured.</p>
      ) : null}

      {clients.length > 0 ? (
        <div className="settings-mcp-named-direct-list">
          {clients.map((client) => (
            <article className={`settings-mcp-named-direct-client${client.enabled ? "" : " is-disabled"}`} key={client.id}>
              <header>
                <div>
                  <strong>{client.name}</strong>
                  <span>{modeLabel(client.mode)}</span>
                </div>
                <span className={`settings-mcp-direct-state${client.enabled ? " is-configured" : ""}`}>
                  {client.enabled ? "Enabled" : "Disabled"}
                </span>
              </header>
              <dl>
                <div><dt>Credential</dt><dd>{client.mode === "trusted_network" ? `${client.trusted_networks.length} CIDR${client.trusted_networks.length === 1 ? "" : "s"}` : client.masked_key ?? "Not available"}</dd></div>
                <div><dt>Last used</dt><dd>{formatUtc(client.last_used_at, timezone)}</dd></div>
                <div><dt>Last address</dt><dd>{client.last_resolved_client_ip ?? "Never resolved"}</dd></div>
                <div><dt>{client.mode === "trusted_network" ? "Updated" : "Rotated"}</dt><dd>{formatUtc(client.mode === "trusted_network" ? client.updated_at : client.rotated_at, timezone)}</dd></div>
              </dl>
              {client.mode === "custom_header" && client.custom_header_name ? (
                <p className="settings-mcp-named-direct-detail">Header: <code>{client.custom_header_name}</code></p>
              ) : null}
              {client.mode === "trusted_network" && client.trusted_networks.length > 0 ? (
                <div className="settings-mcp-named-direct-networks">
                  {client.trusted_networks.slice(0, 4).map((network) => <code key={network}>{network}</code>)}
                  {client.trusted_networks.length > 4 ? <span>+{client.trusted_networks.length - 4} more</span> : null}
                </div>
              ) : null}
              <footer>
                <div>
                  <button className="settings-action settings-action-secondary" type="button" disabled={disabled || busy} onClick={() => openEdit(client)}>Edit</button>
                  {client.mode !== "trusted_network" ? <button className="settings-action settings-action-secondary" type="button" disabled={disabled || busy || !client.enabled} onClick={() => void reveal(client)}>Reveal</button> : null}
                  {client.mode !== "trusted_network" ? <button className="settings-action settings-action-secondary" type="button" disabled={disabled || busy} onClick={() => setConfirm({ kind: "rotate", client })}>Rotate</button> : null}
                  <button className="settings-action settings-action-secondary" type="button" disabled={disabled || busy} onClick={() => setConfirm({ kind: client.enabled ? "disable" : "enable", client })}>{client.enabled ? "Disable" : "Enable"}</button>
                  <button className="settings-action settings-action-secondary" type="button" disabled={disabled || busy || permissionSaving} onClick={() => openPermissions(client)}>Permissions</button>
                </div>
                <button className="settings-action settings-action-danger" type="button" disabled={disabled || busy} onClick={() => setConfirm({ kind: "revoke", client })}>Revoke</button>
              </footer>
            </article>
          ))}
        </div>
      ) : null}

      {error ? <div className="settings-preference-state is-error" role="alert"><span>{error}</span><button type="button" onClick={() => setReload((value) => value + 1)}>Retry</button></div> : null}
      {message && !error ? <p className="settings-preference-state is-success" role="status">{message}</p> : null}

      {permissionTarget ? (
        <McpClientPermissionsDialog
          key={`direct-${permissionTarget.id}`}
          clientName={permissionTarget.name}
          deniedTools={permissionTarget.denied_tools}
          tools={permissionTarget.tool_permissions}
          saving={permissionSaving}
          error={permissionError}
          onClose={() => {
            if (permissionSaving) return;
            setPermissionTarget(null);
            setPermissionError(null);
          }}
          onSave={(deniedTools) => void savePermissions(deniedTools)}
        />
      ) : null}

      {editor ? (
        <div className="settings-security-dialog-backdrop">
          <section className="settings-security-dialog" role="dialog" aria-modal="true" aria-labelledby="settings-mcp-direct-editor-title">
            <header>
              <span className="card-label">MCP direct client</span>
              <h2 id="settings-mcp-direct-editor-title">{editor.mode === "create" ? "Add direct client" : `Edit ${editor.client?.name ?? "client"}`}</h2>
              <p>{editor.mode === "create" ? "Name the client and choose how it authenticates. Secret credentials are shown once after creation." : "Update the client identity or trusted networks without affecting other clients."}</p>
            </header>
            <div className="settings-security-dialog-content settings-mcp-direct-editor-grid">
              <label><span>Client name</span><input type="text" maxLength={120} value={editor.name} disabled={busy} onChange={(event) => setEditor({ ...editor, name: event.target.value })} /></label>
              <label><span>Authentication</span><select value={editor.authMode} disabled={busy || editor.mode === "edit"} onChange={(event) => setEditor({ ...editor, authMode: event.target.value as McpNamedDirectClientMode })}><option value="bearer_key">Bearer key</option><option value="custom_header">Custom header</option><option value="trusted_network">Trusted network</option></select></label>
              {editor.authMode === "custom_header" ? <label className="settings-mcp-direct-editor-wide"><span>HTTP header</span><input type="text" maxLength={120} value={editor.headerName} disabled={busy || editor.mode === "edit"} onChange={(event) => setEditor({ ...editor, headerName: event.target.value })} /><small>The reverse proxy must pass this header unchanged and must not log its value.</small></label> : null}
              {editor.authMode === "trusted_network" ? <label className="settings-mcp-direct-editor-wide"><span>Trusted IPv4/IPv6 CIDRs</span><textarea rows={5} value={editor.networks} disabled={busy} placeholder={"192.168.1.0/24\n2001:db8:1234::/64"} onChange={(event) => setEditor({ ...editor, networks: event.target.value })} /><small>One CIDR per line. Overlap with another enabled named client is rejected.</small></label> : null}
              {editorError ? <p className="form-error settings-mcp-direct-editor-wide" role="alert">{editorError}</p> : null}
            </div>
            <footer>
              <button className="settings-action settings-action-secondary" type="button" disabled={busy} onClick={() => setEditor(null)}>Cancel</button>
              <button className="settings-action settings-action-primary" type="button" disabled={busy || Boolean(editorError)} onClick={() => void submitEditor()}>{busy ? "Working..." : editor.mode === "create" ? "Create client" : "Save changes"}</button>
            </footer>
          </section>
        </div>
      ) : null}

      {confirm ? (
        <div className="settings-security-dialog-backdrop" data-partpilot-mcp-named-direct-confirm="PARTPILOT:MCP_NAMED_DIRECT_SECURITY_DIALOG:V627">
          <section className={confirm.kind === "revoke" ? "settings-security-dialog is-danger" : "settings-security-dialog"} role="dialog" aria-modal="true" aria-labelledby="settings-mcp-direct-confirm-title">
            <header>
              <span className="card-label">MCP direct client</span>
              <h2 id="settings-mcp-direct-confirm-title">{confirm.kind === "rotate" ? `Rotate ${confirm.client.name}?` : confirm.kind === "revoke" ? `Revoke ${confirm.client.name}?` : confirm.kind === "disable" ? `Disable ${confirm.client.name}?` : `Enable ${confirm.client.name}?`}</h2>
            </header>
            <div className="settings-security-dialog-content">
              <p>{confirm.kind === "rotate" ? "The current key stops working immediately. The replacement is displayed once after rotation." : confirm.kind === "revoke" ? "This client stops authenticating immediately. Its secret material is cleared; the backend audit record remains and disappears from this list." : confirm.kind === "disable" ? "This client stops authenticating until it is enabled again. Other direct clients and OAuth are unaffected." : "This client may authenticate again using its current configuration. Other clients are unaffected."}</p>
              <dl className="settings-security-dialog-summary"><div><dt>Client</dt><dd>{confirm.client.name}</dd></div><div><dt>Authentication</dt><dd>{modeLabel(confirm.client.mode)}</dd></div></dl>
              {error ? <p className="form-error" role="alert">{error}</p> : null}
            </div>
            <footer>
              <button className="settings-action settings-action-secondary" type="button" disabled={busy} onClick={() => setConfirm(null)}>Cancel</button>
              <button className={confirm.kind === "revoke" ? "settings-action settings-action-danger" : "settings-action settings-action-primary"} type="button" disabled={busy} onClick={() => void confirmAction()}>{busy ? "Working..." : confirm.kind === "rotate" ? "Rotate key" : confirm.kind === "revoke" ? "Revoke client" : confirm.kind === "disable" ? "Disable client" : "Enable client"}</button>
            </footer>
          </section>
        </div>
      ) : null}

      {credential ? (
        <div className="settings-security-dialog-backdrop" data-partpilot-mcp-named-direct-credential="PARTPILOT:MCP_NAMED_DIRECT_CREDENTIAL_DIALOG:V627">
          <section className="settings-security-dialog" role="dialog" aria-modal="true" aria-labelledby="settings-mcp-direct-credential-title">
            <header><span className="card-label">MCP direct credential</span><h2 id="settings-mcp-direct-credential-title">{credential.title}</h2><p>Copy this credential into only the named client. Treat it like a password.</p></header>
            <div className="settings-security-dialog-content">
              <label className="settings-security-credential-field"><span>{modeLabel(credential.client.mode)}</span><input type={keyVisible ? "text" : "password"} readOnly value={credential.key} onFocus={(event) => event.currentTarget.select()} /></label>
              {credential.client.mode === "custom_header" ? <p>Send the key in <code>{credential.client.custom_header_name}</code>.</p> : <p>Send it as <code>Authorization: Bearer &lt;key&gt;</code>.</p>}
            </div>
            <footer>
              <button className="settings-action settings-action-secondary" type="button" onClick={() => setKeyVisible((value) => !value)}>{keyVisible ? "Hide" : "Show"}</button>
              <button className="settings-action settings-action-primary" type="button" onClick={() => void copyCredential()}>{copied ? "Copied" : "Copy key"}</button>
              <button className="settings-action settings-action-secondary" type="button" onClick={() => { setCredential(null); setCopied(false); setKeyVisible(true); }}>Done</button>
            </footer>
          </section>
        </div>
      ) : null}
    </section>
  );
}
