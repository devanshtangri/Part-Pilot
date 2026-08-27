import {
  type FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";

import {
  createManagedUser,
  deleteManagedUser,
  forceManagedUserPassword,
  listManagedUsers,
  revokeManagedUserSessions,
  updateManagedUserAccess
} from "../services/authClient";
import type {
  AssignableUserRole,
  AuthUser,
  ManagedUser,
  UserRole
} from "../types/auth";
import { SettingsStageIcon } from "./SettingsStageIcon";
import { formatWorkspaceDateTime } from "../utils/dateTime";

const OWNER_ASSIGNABLE_ROLES: AssignableUserRole[] = [
  "administrator",
  "operator",
  "viewer"
];
const ADMIN_ASSIGNABLE_ROLES: AssignableUserRole[] = ["operator", "viewer"];

const ROLE_DESCRIPTIONS: Record<UserRole, string> = {
  owner: "Primary workspace Owner created during initial setup.",
  administrator: "Manages workspace settings and Operator / Viewer accounts.",
  operator: "Can change operational data but cannot administer workspace settings.",
  viewer: "Read-only workspace access."
};

interface CreateUserDraft {
  username: string;
  displayName: string;
  password: string;
  role: AssignableUserRole;
}

type UserDialog =
  | { kind: "create" }
  | { kind: "manage"; user: ManagedUser }
  | { kind: "status"; user: ManagedUser }
  | { kind: "password"; user: ManagedUser }
  | { kind: "sessions"; user: ManagedUser }
  | { kind: "delete"; user: ManagedUser };

interface UserManagementSectionProps {
  token: string;
  currentUser: AuthUser;
  timezone: string | null;
  liveRevision: number;
  hidden: boolean;
}

function roleLabel(role: UserRole): string {
  if (role === "owner") return "Primary Owner";
  if (role === "administrator") return "Administrator";
  return role.charAt(0).toUpperCase() + role.slice(1);
}

function assignableRoles(actorRole: UserRole): AssignableUserRole[] {
  return actorRole === "owner" ? OWNER_ASSIGNABLE_ROLES : ADMIN_ASSIGNABLE_ROLES;
}

function actorCanManage(actorRole: UserRole, targetRole: UserRole): boolean {
  if (targetRole === "owner") return false;
  if (actorRole === "owner") return true;
  return actorRole === "administrator"
    && (targetRole === "operator" || targetRole === "viewer");
}

function editableRole(role: UserRole): AssignableUserRole {
  if (role === "owner") {
    throw new Error("The primary Owner role is not editable.");
  }
  return role;
}

function mutationError(caught: unknown, fallback: string): string {
  return caught instanceof Error ? caught.message : fallback;
}

function userInitials(user: ManagedUser): string {
  const words = user.display_name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return user.username.slice(0, 2).toUpperCase();
  return words.slice(0, 2).map((word) => word[0]?.toUpperCase() ?? "").join("");
}

export function UserManagementSection({
  token,
  currentUser,
  timezone,
  liveRevision,
  hidden
}: UserManagementSectionProps) {
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [reloadVersion, setReloadVersion] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [createSaving, setCreateSaving] = useState(false);
  const [dialogSaving, setDialogSaving] = useState(false);
  const [dialog, setDialog] = useState<UserDialog | null>(null);
  const [manageRoleDraft, setManageRoleDraft] = useState<AssignableUserRole>("viewer");
  const [passwordDraft, setPasswordDraft] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const loadRequestRef = useRef(0);
  const [createDraft, setCreateDraft] = useState<CreateUserDraft>({
    username: "",
    displayName: "",
    password: "",
    role: currentUser.role === "owner" ? "administrator" : "operator"
  });

  const allowedRoles = useMemo(
    () => assignableRoles(currentUser.role),
    [currentUser.role]
  );
  const activeCount = useMemo(
    () => users.filter((managedUser) => managedUser.is_active).length,
    [users]
  );
  const disabledCount = users.length - activeCount;

  useEffect(() => {
    if (!allowedRoles.includes(createDraft.role)) {
      setCreateDraft((draft) => ({ ...draft, role: allowedRoles[0] ?? "viewer" }));
    }
  }, [allowedRoles, createDraft.role]);

  useEffect(() => {
    const requestId = ++loadRequestRef.current;
    let cancelled = false;

    async function loadUsers() {
      setLoading(true);
      setError(null);
      try {
        const response = await listManagedUsers(token);
        if (!cancelled && requestId === loadRequestRef.current) {
          setUsers(response.users);
        }
      } catch (caught) {
        if (!cancelled && requestId === loadRequestRef.current) {
          setError(mutationError(caught, "Unable to load users"));
        }
      } finally {
        if (!cancelled && requestId === loadRequestRef.current) setLoading(false);
      }
    }

    void loadUsers();
    return () => { cancelled = true; };
  }, [liveRevision, reloadVersion, token]);

  function replaceUser(updated: ManagedUser): void {
    setUsers((current) => current.map((candidate) =>
      candidate.id === updated.id ? updated : candidate
    ));
  }

  function clearDialogFields(): void {
    setPasswordDraft("");
    setPasswordConfirm("");
    setDeleteConfirmation("");
  }

  function openCreate(): void {
    setError(null);
    setMessage(null);
    clearDialogFields();
    setDialog({ kind: "create" });
  }

  function openManage(user: ManagedUser): void {
    setError(null);
    setMessage(null);
    clearDialogFields();
    setManageRoleDraft(editableRole(user.role));
    setDialog({ kind: "manage", user });
  }

  function openAction(
    kind: "status" | "password" | "sessions" | "delete",
    user: ManagedUser
  ): void {
    setError(null);
    clearDialogFields();
    setDialog({ kind, user } as UserDialog);
  }

  function closeDialog(): void {
    if (dialogSaving || createSaving) return;
    setDialog(null);
    setError(null);
    clearDialogFields();
  }

  async function submitCreate(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (createSaving) return;
    setCreateSaving(true);
    setError(null);
    setMessage(null);
    try {
      const created = await createManagedUser(token, {
        username: createDraft.username,
        displayName: createDraft.displayName,
        password: createDraft.password,
        role: createDraft.role
      });
      setUsers((current) => [...current, created]);
      setCreateDraft({
        username: "",
        displayName: "",
        password: "",
        role: currentUser.role === "owner" ? "administrator" : "operator"
      });
      setDialog(null);
      setMessage(`Created ${created.username} as ${roleLabel(created.role)}.`);
    } catch (caught) {
      setError(mutationError(caught, "Unable to create user"));
    } finally {
      setCreateSaving(false);
    }
  }

  async function applyRole(user: ManagedUser): Promise<void> {
    if (dialogSaving || manageRoleDraft === user.role) return;
    setDialogSaving(true);
    setError(null);
    try {
      const updated = await updateManagedUserAccess(token, user.id, {
        role: manageRoleDraft
      });
      replaceUser(updated);
      setManageRoleDraft(editableRole(updated.role));
      setDialog({ kind: "manage", user: updated });
      setMessage(`Changed ${updated.username} to ${roleLabel(updated.role)}.`);
    } catch (caught) {
      setManageRoleDraft(editableRole(user.role));
      setError(mutationError(caught, "Unable to change role"));
    } finally {
      setDialogSaving(false);
    }
  }

  async function confirmStatusChange(): Promise<void> {
    if (!dialog || dialog.kind !== "status" || dialogSaving) return;
    const target = dialog.user;
    setDialogSaving(true);
    setError(null);
    try {
      const updated = await updateManagedUserAccess(token, target.id, {
        isActive: !target.is_active
      });
      replaceUser(updated);
      setDialog(null);
      setMessage(updated.is_active
        ? `Reactivated ${updated.username}.`
        : `Disabled ${updated.username} and revoked its active sessions.`);
    } catch (caught) {
      setError(mutationError(caught, "Unable to update account status"));
    } finally {
      setDialogSaving(false);
    }
  }

  async function confirmPasswordReset(): Promise<void> {
    if (!dialog || dialog.kind !== "password" || dialogSaving) return;
    if (passwordDraft.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    if (passwordDraft !== passwordConfirm) {
      setError("Password confirmation does not match.");
      return;
    }
    const target = dialog.user;
    setDialogSaving(true);
    setError(null);
    try {
      const response = await forceManagedUserPassword(token, target.id, passwordDraft);
      setDialog(null);
      setMessage(
        `Password reset for ${target.username}; ${response.revoked_sessions} session${
          response.revoked_sessions === 1 ? "" : "s"
        } revoked.`
      );
    } catch (caught) {
      setError(mutationError(caught, "Unable to force password reset"));
    } finally {
      setDialogSaving(false);
    }
  }

  async function confirmSessionRevocation(): Promise<void> {
    if (!dialog || dialog.kind !== "sessions" || dialogSaving) return;
    const target = dialog.user;
    setDialogSaving(true);
    setError(null);
    try {
      const response = await revokeManagedUserSessions(token, target.id);
      setDialog(null);
      setMessage(
        `Revoked ${response.revoked_sessions} session${
          response.revoked_sessions === 1 ? "" : "s"
        } for ${target.username}.`
      );
    } catch (caught) {
      setError(mutationError(caught, "Unable to revoke sessions"));
    } finally {
      setDialogSaving(false);
    }
  }

  async function confirmDelete(): Promise<void> {
    if (!dialog || dialog.kind !== "delete" || dialogSaving) return;
    const target = dialog.user;
    if (deleteConfirmation.trim().toLowerCase() !== target.username) {
      setError(`Type ${target.username} exactly to confirm deletion.`);
      return;
    }
    setDialogSaving(true);
    setError(null);
    try {
      await deleteManagedUser(token, target.id, deleteConfirmation);
      setUsers((current) => current.filter((user) => user.id !== target.id));
      setDialog(null);
      setMessage(`Permanently deleted ${target.username}.`);
    } catch (caught) {
      setError(mutationError(caught, "Unable to delete user"));
    } finally {
      setDialogSaving(false);
    }
  }

  const manageTarget = dialog?.kind === "manage" ? dialog.user : null;

  return (
    <>
      <section
        id="settings-users"
        className="card settings-section settings-users-section"
        aria-labelledby="settings-users-title"
        hidden={hidden}
        data-partpilot-user-management="PARTPILOT:SETTINGS_USER_MANAGEMENT_UI:V774"
        data-partpilot-users-settings-hierarchy="PARTPILOT:USERS_SETTINGS_HIERARCHY:V781"
      >
        <div className="settings-section-heading settings-users-heading">
          <div>
            <span className="card-label">Workspace access</span>
            <h2 id="settings-users-title">Users &amp; Roles</h2>
            <p>
              See who can access Part Pilot and open one focused panel to manage
              an account.
            </p>
          </div>
          <button
            type="button"
            className="settings-action settings-action-primary"
            onClick={openCreate}
          >
            Add user
          </button>
        </div>

        <div className="settings-users-stage settings-unified-stage">
          <div className="settings-unified-stage-heading">
            <SettingsStageIcon name="users" />
            <div>
              <span className="card-label">Directory</span>
              <h3>Workspace accounts</h3>
              <p>Review role, account status and recent sign-in activity before opening focused management actions.</p>
            </div>
            <span className="settings-unified-stage-status">{activeCount} active</span>
          </div>

          <div className="settings-users-summary" aria-label="User summary">
          <div><span>Total</span><strong>{users.length}</strong></div>
          <div><span>Active</span><strong>{activeCount}</strong></div>
          <div><span>Disabled</span><strong>{disabledCount}</strong></div>
        </div>

        {loading && users.length === 0 ? (
          <div className="settings-users-empty" role="status">
            Loading user accounts...
          </div>
        ) : null}
        {!loading && users.length === 0 ? (
          <div className="settings-users-empty">No user accounts were returned.</div>
        ) : null}

        <div className="settings-users-roster" aria-busy={loading}>
          {users.length > 0 ? (
            <div className="settings-users-roster-head" aria-hidden="true">
              <span>User</span>
              <span>Role</span>
              <span>Status</span>
              <span>Last login</span>
              <span>Action</span>
            </div>
          ) : null}
          {users.map((managedUser) => {
            const manageable = actorCanManage(currentUser.role, managedUser.role);
            const isSelf = managedUser.id === currentUser.id;
            const isPrimaryOwner = managedUser.role === "owner";
            return (
              <article
                className="settings-user-row"
                key={managedUser.id}
                data-user-id={managedUser.id}
              >
                <div className="settings-user-person">
                  <span className="settings-user-avatar" aria-hidden="true">
                    {userInitials(managedUser)}
                  </span>
                  <div>
                    <strong>{managedUser.display_name}</strong>
                    <span>@{managedUser.username}</span>
                    <div className="settings-user-inline-badges">
                      {isSelf ? (
                        <span className="settings-user-self-badge">You</span>
                      ) : null}
                    </div>
                  </div>
                </div>
                <div className="settings-user-roster-cell" data-label="Role">
                  <span className={`settings-user-role is-${managedUser.role}`}>
                    {roleLabel(managedUser.role)}
                  </span>
                </div>
                <div className="settings-user-roster-cell" data-label="Status">
                  <span
                    className={`settings-user-state ${
                      managedUser.is_active ? "is-active" : "is-disabled"
                    }`}
                  >
                    {managedUser.is_active ? "Active" : "Disabled"}
                  </span>
                </div>
                <div className="settings-user-login" data-label="Last login">
                  {managedUser.last_login_at
                    ? formatWorkspaceDateTime(managedUser.last_login_at, timezone)
                    : "Never"}
                </div>
                <div className="settings-user-row-action">
                  <button
                    type="button"
                    className="settings-action settings-action-secondary"
                    onClick={() => openManage(managedUser)}
                    disabled={!manageable}
                    title={!manageable
                      ? isPrimaryOwner
                        ? "The initial Owner account is protected."
                        : "This account is above your role ceiling."
                      : undefined}
                  >
                    {manageable ? "Manage" : "Protected"}
                  </button>
                </div>
              </article>
            );
          })}
        </div>

        {error && !dialog ? (
          <div className="settings-account-state is-error" role="alert">
            <span>{error}</span>
            {!loading ? (
              <button
                type="button"
                onClick={() => setReloadVersion((value) => value + 1)}
              >
                Retry
              </button>
            ) : null}
          </div>
        ) : null}
          {message ? (
            <p className="settings-account-state is-success" role="status">
              {message}
            </p>
          ) : null}
        </div>
      </section>

      {dialog ? (
        <div
          className="settings-security-dialog-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeDialog();
          }}
        >
          <section
            className={`settings-security-dialog settings-user-dialog ${
              dialog.kind === "delete"
              || (dialog.kind === "status" && dialog.user.is_active)
                ? "is-danger"
                : ""
            }`}
            role="dialog"
            aria-modal="true"
            aria-labelledby="settings-user-dialog-title"
          >
            <header>
              <span className="card-label">User administration</span>
              <h2 id="settings-user-dialog-title">
                {dialog.kind === "create"
                  ? "Add user"
                  : dialog.kind === "manage"
                    ? `Manage ${dialog.user.display_name}`
                    : dialog.kind === "status"
                      ? dialog.user.is_active ? "Disable user" : "Reactivate user"
                      : dialog.kind === "password"
                        ? "Force password reset"
                        : dialog.kind === "sessions"
                          ? "Revoke user sessions"
                          : "Delete user permanently"}
              </h2>
              {dialog.kind !== "create" ? (
                <p>Target: <strong>@{dialog.user.username}</strong></p>
              ) : null}
            </header>

            <div className="settings-security-dialog-content">
              {dialog.kind === "create" ? (
                <form
                  id="settings-user-create-form"
                  className="settings-user-create-dialog"
                  onSubmit={(event) => void submitCreate(event)}
                >
                  <div className="settings-user-create-grid">
                    <label>
                      <span>Display name</span>
                      <input
                        value={createDraft.displayName}
                        maxLength={160}
                        autoComplete="off"
                        disabled={createSaving}
                        required
                        onChange={(event) => setCreateDraft((draft) => ({
                          ...draft,
                          displayName: event.target.value
                        }))}
                      />
                    </label>
                    <label>
                      <span>Username</span>
                      <input
                        value={createDraft.username}
                        maxLength={80}
                        pattern="[a-z0-9._]+"
                        autoCapitalize="none"
                        autoComplete="off"
                        disabled={createSaving}
                        required
                        onChange={(event) => setCreateDraft((draft) => ({
                          ...draft,
                          username: event.target.value.toLowerCase()
                        }))}
                      />
                    </label>
                    <label>
                      <span>Temporary password</span>
                      <input
                        type="password"
                        value={createDraft.password}
                        minLength={8}
                        maxLength={256}
                        autoComplete="new-password"
                        disabled={createSaving}
                        required
                        onChange={(event) => setCreateDraft((draft) => ({
                          ...draft,
                          password: event.target.value
                        }))}
                      />
                    </label>
                    <label>
                      <span>Role</span>
                      <select
                        value={createDraft.role}
                        disabled={createSaving}
                        onChange={(event) => setCreateDraft((draft) => ({
                          ...draft,
                          role: event.target.value as AssignableUserRole
                        }))}
                      >
                        {allowedRoles.map((role) => (
                          <option key={role} value={role}>{roleLabel(role)}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <p className="settings-user-role-help">
                    {ROLE_DESCRIPTIONS[createDraft.role]}
                  </p>
                </form>
              ) : null}

              {dialog.kind === "manage" && manageTarget ? (
                <div className="settings-user-manage-layout">
                  <div className="settings-user-manage-summary">
                    <div>
                      <span className="settings-user-avatar" aria-hidden="true">
                        {userInitials(manageTarget)}
                      </span>
                      <div>
                        <strong>{manageTarget.display_name}</strong>
                        <span>@{manageTarget.username}</span>
                      </div>
                    </div>
                    <div className="settings-user-statuses">
                      <span className={`settings-user-role is-${manageTarget.role}`}>
                        {roleLabel(manageTarget.role)}
                      </span>
                      <span className={`settings-user-state ${
                        manageTarget.is_active ? "is-active" : "is-disabled"
                      }`}>
                        {manageTarget.is_active ? "Active" : "Disabled"}
                      </span>
                    </div>
                  </div>

                  <section className="settings-user-manage-block">
                    <div>
                      <strong>Access role</strong>
                      <span>Controls what this account can read or change.</span>
                    </div>
                    <div className="settings-user-role-control">
                      <select
                        value={manageRoleDraft}
                        disabled={dialogSaving}
                        onChange={(event) => setManageRoleDraft(
                          event.target.value as AssignableUserRole
                        )}
                      >
                        {allowedRoles.map((role) => (
                          <option key={role} value={role}>{roleLabel(role)}</option>
                        ))}
                      </select>
                      <button
                        type="button"
                        className="settings-action settings-action-primary"
                        disabled={dialogSaving || manageRoleDraft === manageTarget.role}
                        onClick={() => void applyRole(manageTarget)}
                      >
                        {dialogSaving ? "Saving..." : "Apply role"}
                      </button>
                    </div>
                    <small>{ROLE_DESCRIPTIONS[manageRoleDraft]}</small>
                  </section>

                  <section className="settings-user-manage-block">
                    <div>
                      <strong>Account status</strong>
                      <span>
                        {manageTarget.is_active
                          ? "This user can currently sign in."
                          : "This user is blocked from signing in."}
                      </span>
                    </div>
                    <button
                      type="button"
                      className={manageTarget.is_active
                        ? "settings-action settings-action-danger"
                        : "settings-action settings-action-secondary"}
                      onClick={() => openAction("status", manageTarget)}
                    >
                      {manageTarget.is_active ? "Disable account" : "Reactivate account"}
                    </button>
                  </section>

                  <section className="settings-user-manage-block">
                    <div>
                      <strong>Security</strong>
                      <span>Replace the password or invalidate active sessions.</span>
                    </div>
                    <div className="settings-user-manage-actions">
                      <button
                        type="button"
                        className="settings-action settings-action-secondary"
                        onClick={() => openAction("password", manageTarget)}
                      >
                        Reset password
                      </button>
                      <button
                        type="button"
                        className="settings-action settings-action-secondary"
                        onClick={() => openAction("sessions", manageTarget)}
                      >
                        Revoke sessions
                      </button>
                    </div>
                  </section>

                  <section className="settings-user-manage-block is-danger">
                    <div>
                      <strong>Permanent deletion</strong>
                      <span>Removes this account after exact username confirmation.</span>
                    </div>
                    <button
                      type="button"
                      className="settings-action settings-action-danger"
                      onClick={() => openAction("delete", manageTarget)}
                    >
                      Delete permanently
                    </button>
                  </section>
                </div>
              ) : null}

              {dialog.kind === "status" ? (
                <p>
                  {dialog.user.is_active
                    ? "Disabling this account also revokes its active sessions. The account can be reactivated later."
                    : "Reactivating restores sign-in eligibility but does not recreate revoked sessions."}
                </p>
              ) : null}

              {dialog.kind === "password" ? (
                <>
                  <p>
                    This replaces the password immediately and revokes every active
                    session for this user.
                  </p>
                  <label className="settings-user-dialog-field">
                    <span>New password</span>
                    <input
                      type="password"
                      minLength={8}
                      maxLength={256}
                      autoComplete="new-password"
                      value={passwordDraft}
                      onChange={(event) => setPasswordDraft(event.target.value)}
                      disabled={dialogSaving}
                    />
                  </label>
                  <label className="settings-user-dialog-field">
                    <span>Confirm new password</span>
                    <input
                      type="password"
                      minLength={8}
                      maxLength={256}
                      autoComplete="new-password"
                      value={passwordConfirm}
                      onChange={(event) => setPasswordConfirm(event.target.value)}
                      disabled={dialogSaving}
                    />
                  </label>
                </>
              ) : null}

              {dialog.kind === "sessions" ? (
                <p>
                  Revoke every active session for this account. The user can sign in
                  again later while the account remains active.
                </p>
              ) : null}

              {dialog.kind === "delete" ? (
                <>
                  <p>
                    Permanent deletion cannot be undone. Type the username exactly
                    to confirm this action.
                  </p>
                  <label className="settings-user-dialog-field">
                    <span>Confirmation username</span>
                    <input
                      type="text"
                      autoCapitalize="none"
                      autoComplete="off"
                      value={deleteConfirmation}
                      placeholder={dialog.user.username}
                      onChange={(event) => setDeleteConfirmation(event.target.value)}
                      disabled={dialogSaving}
                    />
                  </label>
                </>
              ) : null}

              {error ? (
                <p className="settings-account-state is-error" role="alert">{error}</p>
              ) : null}
            </div>

            <footer>
              <button
                type="button"
                className="settings-action settings-action-secondary"
                onClick={closeDialog}
                disabled={dialogSaving || createSaving}
              >
                Cancel
              </button>
              {dialog.kind === "create" ? (
                <button
                  type="submit"
                  form="settings-user-create-form"
                  className="settings-action settings-action-primary"
                  disabled={
                    createSaving
                    || !createDraft.displayName.trim()
                    || !createDraft.username.trim()
                    || createDraft.password.length < 8
                  }
                >
                  {createSaving ? "Creating..." : "Create user"}
                </button>
              ) : null}
              {dialog.kind === "status" ? (
                <button
                  type="button"
                  className={dialog.user.is_active
                    ? "settings-action settings-action-danger"
                    : "settings-action settings-action-primary"}
                  onClick={() => void confirmStatusChange()}
                  disabled={dialogSaving}
                >
                  {dialogSaving
                    ? "Saving..."
                    : dialog.user.is_active ? "Disable user" : "Reactivate user"}
                </button>
              ) : null}
              {dialog.kind === "password" ? (
                <button
                  type="button"
                  className="settings-action settings-action-primary"
                  onClick={() => void confirmPasswordReset()}
                  disabled={
                    dialogSaving
                    || passwordDraft.length < 8
                    || passwordDraft !== passwordConfirm
                  }
                >
                  {dialogSaving ? "Resetting..." : "Reset password"}
                </button>
              ) : null}
              {dialog.kind === "sessions" ? (
                <button
                  type="button"
                  className="settings-action settings-action-danger"
                  onClick={() => void confirmSessionRevocation()}
                  disabled={dialogSaving}
                >
                  {dialogSaving ? "Revoking..." : "Revoke all sessions"}
                </button>
              ) : null}
              {dialog.kind === "delete" ? (
                <button
                  type="button"
                  className="settings-action settings-action-danger"
                  onClick={() => void confirmDelete()}
                  disabled={
                    dialogSaving
                    || deleteConfirmation.trim().toLowerCase() !== dialog.user.username
                  }
                >
                  {dialogSaving ? "Deleting..." : "Delete permanently"}
                </button>
              ) : null}
            </footer>
          </section>
        </div>
      ) : null}
    </>
  );
}
