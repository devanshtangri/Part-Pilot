import { useEffect, useMemo, useState } from "react";

import type { McpClientToolPermission } from "../types/settings";

// PARTPILOT:MCP_CLIENT_PERMISSIONS_DIALOG:V654
interface Props {
  clientName: string;
  deniedTools: string[];
  tools: McpClientToolPermission[];
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onSave: (deniedTools: string[]) => void;
}

export function McpClientPermissionsDialog({
  clientName,
  deniedTools,
  tools,
  saving,
  error,
  onClose,
  onSave
}: Props) {
  const [draftDenied, setDraftDenied] = useState<Set<string>>(
    () => new Set(deniedTools)
  );

  useEffect(() => {
    setDraftDenied(new Set(deniedTools));
  }, [clientName, deniedTools]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape" && !saving) onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, saving]);

  const canonicalDenied = useMemo(
    () => tools.filter((tool) => draftDenied.has(tool.name)).map((tool) => tool.name),
    [draftDenied, tools]
  );
  const changed = canonicalDenied.length !== deniedTools.length ||
    canonicalDenied.some((name, index) => name !== deniedTools[index]);

  function setAllowed(toolName: string, allowed: boolean): void {
    if (saving) return;
    setDraftDenied((current) => {
      const next = new Set(current);
      if (allowed) next.delete(toolName);
      else next.add(toolName);
      return next;
    });
  }

  return (
    <div
      className="settings-security-dialog-backdrop"
      data-partpilot-mcp-client-permissions="PARTPILOT:MCP_CLIENT_PERMISSIONS_DIALOG:V654"
    >
      <section
        className="settings-security-dialog settings-mcp-permission-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-mcp-client-permission-title"
      >
        <header>
          <span className="card-label">MCP permissions</span>
          <h2 id="settings-mcp-client-permission-title">{clientName}</h2>
          <p>
            Global permissions are the hard ceiling. This client can inherit a
            globally enabled tool or block it, but cannot override a global block.
          </p>
        </header>
        <div className="settings-security-dialog-content">
          <div className="settings-mcp-client-permission-list">
            {tools.map((tool) => {
              const clientAllowed = !draftDenied.has(tool.name);
              const effectiveAllowed = tool.global_enabled && clientAllowed;
              const toggleDisabled = saving || !tool.global_enabled;
              return (
                <article
                  className={
                    tool.global_enabled
                      ? "settings-mcp-client-permission"
                      : "settings-mcp-client-permission is-global-disabled"
                  }
                  key={tool.name}
                >
                  <div className="settings-mcp-client-permission-copy">
                    <strong>{tool.label}</strong>
                    <span><code>{tool.name}</code> · Read tool</span>
                  </div>
                  <div className="settings-mcp-permission-badges" aria-label={`${tool.label} status`}>
                    <span className={tool.global_enabled ? "is-enabled" : "is-blocked"}>
                      {tool.global_enabled ? "Global on" : "Global off"}
                    </span>
                    <span className={effectiveAllowed ? "is-enabled" : "is-blocked"}>
                      {effectiveAllowed ? "Effective: allowed" : "Effective: blocked"}
                    </span>
                  </div>
                  <label
                    className={
                      toggleDisabled
                        ? "settings-toggle-row settings-mcp-client-permission-toggle is-toggle-disabled"
                        : "settings-toggle-row settings-mcp-client-permission-toggle"
                    }
                  >
                    <span className="settings-toggle-copy">
                      <strong>{clientAllowed ? "Allowed for client" : "Blocked for client"}</strong>
                      <span>
                        {tool.global_enabled
                          ? "Client-level inherit or deny."
                          : "Global policy currently blocks this tool. Re-enable it globally to edit this client override."}
                      </span>
                    </span>
                    <input
                      type="checkbox"
                      role="switch"
                      checked={clientAllowed}
                      disabled={toggleDisabled}
                      aria-label={`Allow ${tool.label} for ${clientName}`}
                      onChange={(event) => setAllowed(tool.name, event.target.checked)}
                    />
                    <span className="settings-switch" aria-hidden="true" />
                  </label>
                </article>
              );
            })}
          </div>
          {error ? <p className="form-error" role="alert">{error}</p> : null}
        </div>
        <footer>
          <button
            className="settings-action settings-action-secondary"
            type="button"
            disabled={saving}
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="settings-action settings-action-primary"
            type="button"
            disabled={saving || !changed}
            onClick={() => onSave(canonicalDenied)}
          >
            {saving ? "Saving permissions..." : "Save permissions"}
          </button>
        </footer>
      </section>
    </div>
  );
}
