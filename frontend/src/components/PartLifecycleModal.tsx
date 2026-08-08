// PATCH 153: focused recoverable part lifecycle modal
import {
  useEffect,
  useMemo,
  useState
} from "react";
import {
  deletePart,
  getDeletedParts,
  purgeDeletedParts,
  restorePart
} from "../services/partsClient";
import type {
  DeletedPart,
  DeletedPartCollection,
  Part
} from "../types/parts";
import "./PartLifecycleModal.css";


interface PartLifecycleModalProps {
  token: string;
  deleteTarget: Part | null;
  deletedPartsOpen: boolean;
  onCloseDelete: () => void;
  onDeleted: (partId: number) => void;
  onCloseDeletedParts: () => void;
  onRestored: (part: Part) => void;
  partTypeFilter: { id: number; name: string } | null;
  onClearPartTypeFilter: () => void;
}


function partName(part: Part): string {
  return part.name || part.part_number || `Part ${part.id}`;
}


function dateLabel(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString();
}


export function PartLifecycleModal({
  token,
  deleteTarget,
  deletedPartsOpen,
  onCloseDelete,
  onDeleted,
  onCloseDeletedParts,
  onRestored,
  partTypeFilter,
  onClearPartTypeFilter
}: PartLifecycleModalProps) {
  const [deleteSaving, setDeleteSaving] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deletedCollection, setDeletedCollection] =
    useState<DeletedPartCollection | null>(null);
  const [deletedLoading, setDeletedLoading] = useState(false);
  const [deletedError, setDeletedError] = useState<string | null>(null);
  const [deletedQuery, setDeletedQuery] = useState("");
  const [restoringId, setRestoringId] = useState<number | null>(null);
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const [selectedDeletedIds, setSelectedDeletedIds] = useState<Set<number>>(
    () => new Set()
  );
  const [purgeIds, setPurgeIds] = useState<number[] | null>(null);
  const [purgeConfirmation, setPurgeConfirmation] = useState("");
  const [purging, setPurging] = useState(false);
  const [purgeError, setPurgeError] = useState<string | null>(null);
  const [purgeNotice, setPurgeNotice] = useState<string | null>(null);

  const visibleDeletedParts = useMemo(() => {
    if (!deletedCollection) {
      return [];
    }

    const typeFiltered = partTypeFilter
      ? deletedCollection.parts.filter(
          (part) => part.part_type_id === partTypeFilter.id
        )
      : deletedCollection.parts;
    const normalized = deletedQuery.trim().toLowerCase();
    if (!normalized) {
      return typeFiltered;
    }

    return typeFiltered.filter((part) =>
      [
        part.name,
        part.part_number,
        part.part_type_name,
        part.manufacturer_name,
        part.package
      ].some((value) => value?.toLowerCase().includes(normalized))
    );
  }, [deletedCollection, deletedQuery, partTypeFilter]);

  const allVisibleSelected =
    visibleDeletedParts.length > 0
    && visibleDeletedParts.every((part) => selectedDeletedIds.has(part.id));
  const purgeParts = purgeIds && deletedCollection
    ? deletedCollection.parts.filter((part) => purgeIds.includes(part.id))
    : [];

  useEffect(() => {
    if (!deleteTarget && !deletedPartsOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") {
        return;
      }

      if (purgeIds && !purging) {
        setPurgeIds(null);
        setPurgeConfirmation("");
        setPurgeError(null);
      } else if (deleteTarget && !deleteSaving) {
        onCloseDelete();
      } else if (
        deletedPartsOpen
        && restoringId === null
        && !purging
      ) {
        onCloseDeletedParts();
      }
    }

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [
    deleteTarget,
    deletedPartsOpen,
    deleteSaving,
    restoringId,
    purgeIds,
    purging,
    onCloseDelete,
    onCloseDeletedParts
  ]);

  useEffect(() => {
    if (!deleteTarget) {
      setDeleteSaving(false);
      setDeleteError(null);
    }
  }, [deleteTarget]);

  useEffect(() => {
    if (!deletedPartsOpen) {
      setDeletedCollection(null);
      setDeletedLoading(false);
      setDeletedError(null);
      setDeletedQuery("");
      setRestoringId(null);
      setRestoreError(null);
      setSelectedDeletedIds(new Set());
      setPurgeIds(null);
      setPurgeConfirmation("");
      setPurging(false);
      setPurgeError(null);
      setPurgeNotice(null);
      return;
    }

    let cancelled = false;
    setDeletedLoading(true);
    setDeletedError(null);
    setRestoreError(null);
    setPurgeError(null);

    getDeletedParts(token, { limit: 250, offset: 0 })
      .then((result) => {
        if (!cancelled) {
          setDeletedCollection(result);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setDeletedError(
            caught instanceof Error
              ? caught.message
              : "Unable to load deleted parts"
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setDeletedLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [deletedPartsOpen, token]);

  async function handleDelete() {
    if (!deleteTarget || deleteSaving) {
      return;
    }

    setDeleteSaving(true);
    setDeleteError(null);
    try {
      const deleted = await deletePart(token, deleteTarget.id);
      onDeleted(deleted.id);
    } catch (caught) {
      setDeleteError(
        caught instanceof Error
          ? caught.message
          : "Unable to delete this part"
      );
    } finally {
      setDeleteSaving(false);
    }
  }

  async function handleRestore(part: DeletedPart) {
    if (restoringId !== null) {
      return;
    }

    setRestoringId(part.id);
    setRestoreError(null);
    try {
      const restored = await restorePart(token, part.id);
      setDeletedCollection((current) =>
        current
          ? {
              ...current,
              total: Math.max(0, current.total - 1),
              parts: current.parts.filter(
                (item) => item.id !== restored.id
              )
            }
          : current
      );
      setSelectedDeletedIds((current) => {
        const next = new Set(current);
        next.delete(restored.id);
        return next;
      });
      onRestored(restored);
    } catch (caught) {
      setRestoreError(
        caught instanceof Error
          ? caught.message
          : "Unable to restore this part"
      );
    } finally {
      setRestoringId(null);
    }
  }



  function toggleDeletedSelection(partId: number) {
    setSelectedDeletedIds((current) => {
      const next = new Set(current);
      if (next.has(partId)) {
        next.delete(partId);
      } else {
        next.add(partId);
      }
      return next;
    });
    setPurgeNotice(null);
  }

  function toggleVisibleSelection() {
    setSelectedDeletedIds((current) => {
      const next = new Set(current);
      if (allVisibleSelected) {
        visibleDeletedParts.forEach((part) => next.delete(part.id));
      } else {
        visibleDeletedParts.forEach((part) => next.add(part.id));
      }
      return next;
    });
    setPurgeNotice(null);
  }

  function openPurgeConfirmation() {
    const ids = Array.from(selectedDeletedIds).sort((a, b) => a - b);
    if (ids.length === 0) {
      return;
    }
    setPurgeIds(ids);
    setPurgeConfirmation("");
    setPurgeError(null);
  }

  function closePurgeConfirmation() {
    if (purging) {
      return;
    }
    setPurgeIds(null);
    setPurgeConfirmation("");
    setPurgeError(null);
  }

  async function handlePermanentDelete() {
    if (
      !purgeIds
      || purgeIds.length === 0
      || purgeConfirmation !== "DELETE"
      || purging
    ) {
      return;
    }

    setPurging(true);
    setPurgeError(null);
    try {
      const result = await purgeDeletedParts(token, purgeIds);
      const purged = new Set(result.purged_ids);
      setDeletedCollection((current) =>
        current
          ? {
              ...current,
              total: Math.max(0, current.total - result.purged_count),
              parts: current.parts.filter((part) => !purged.has(part.id))
            }
          : current
      );
      setSelectedDeletedIds((current) => {
        const next = new Set(current);
        result.purged_ids.forEach((partId) => next.delete(partId));
        return next;
      });
      setPurgeNotice(
        `Permanently deleted ${result.purged_count} ${
          result.purged_count === 1 ? "part" : "parts"
        }.`
      );
      setPurgeIds(null);
      setPurgeConfirmation("");
    } catch (caught) {
      setPurgeError(
        caught instanceof Error
          ? caught.message
          : "Unable to permanently delete the selected parts"
      );
    } finally {
      setPurging(false);
    }
  }

  if (purgeIds) {
    return (
      <div
        className="part-lifecycle-backdrop"
        data-part-lifecycle-purge="PARTPILOT:PERMANENT_PART_PURGE_UI:V607"
        role="presentation"
        onMouseDown={(event) => {
          if (event.target === event.currentTarget && !purging) {
            closePurgeConfirmation();
          }
        }}
      >
        <section
          className="part-lifecycle-dialog is-delete is-purge"
          role="dialog"
          aria-modal="true"
          aria-labelledby="part-purge-title"
          aria-describedby="part-purge-description"
        >
          <header>
            <div>
              <p className="eyebrow">Permanent action</p>
              <h2 id="part-purge-title">Delete permanently?</h2>
            </div>
            <button
              type="button"
              className="part-lifecycle-close"
              onClick={closePurgeConfirmation}
              disabled={purging}
              aria-label="Close permanent deletion confirmation"
              title="Close"
              autoFocus
            >
              ×
            </button>
          </header>
          <div className="part-lifecycle-content">
            <p id="part-purge-description">
              This permanently removes {purgeIds.length}{" "}
              {purgeIds.length === 1 ? "part" : "parts"} from Deleted
              items. This cannot be undone.
            </p>
            <div className="part-lifecycle-purge-warning">
              <strong>Data that will be removed</strong>
              <span>
                The part record, aliases, tags and custom field values are
                deleted. Historical movements and terminal Project/Reservation
                rows are retained but detached. Active work blocks this action.
              </span>
            </div>
            <div className="part-lifecycle-purge-list">
              {purgeParts.slice(0, 6).map((part) => (
                <span key={part.id}>{partName(part)}</span>
              ))}
              {purgeParts.length > 6 ? (
                <span>+{purgeParts.length - 6} more</span>
              ) : null}
            </div>
            <label className="part-lifecycle-confirmation">
              <span>Type <code>DELETE</code> to continue</span>
              <input
                type="text"
                value={purgeConfirmation}
                onChange={(event) => {
                  setPurgeConfirmation(event.target.value);
                  setPurgeError(null);
                }}
                placeholder="DELETE"
                autoComplete="off"
                disabled={purging}
                aria-invalid={Boolean(purgeError)}
              />
            </label>
            {purgeError ? (
              <div className="part-lifecycle-error" role="alert">
                {purgeError}
              </div>
            ) : null}
          </div>
          <footer>
            <button
              type="button"
              className="part-lifecycle-secondary"
              onClick={closePurgeConfirmation}
              disabled={purging}
            >
              Cancel
            </button>
            <button
              type="button"
              className="part-lifecycle-danger"
              onClick={() => void handlePermanentDelete()}
              disabled={purging || purgeConfirmation !== "DELETE"}
            >
              {purging ? "Deleting permanently..." : "Delete permanently"}
            </button>
          </footer>
        </section>
      </div>
    );
  }

  if (deleteTarget) {
    return (
      <div
        className="part-lifecycle-backdrop"
        data-part-lifecycle-version="part-lifecycle-v153"
        role="presentation"
        onMouseDown={(event) => {
          if (
            event.target === event.currentTarget
            && !deleteSaving
          ) {
            onCloseDelete();
          }
        }}
      >
        <section
          className="part-lifecycle-dialog is-delete"
          role="dialog"
          aria-modal="true"
          aria-labelledby="part-delete-title"
          aria-describedby="part-delete-description"
        >
          <header>
            <div>
              <p className="eyebrow">Recoverable action</p>
              <h2 id="part-delete-title">Delete this part?</h2>
            </div>
            <button
              type="button"
              className="part-lifecycle-close"
              onClick={onCloseDelete}
              disabled={deleteSaving}
              aria-label="Close deletion confirmation"
              title="Close"
              autoFocus
            >
              ×
            </button>
          </header>

          <div className="part-lifecycle-content">
            <p id="part-delete-description">
              <strong>{partName(deleteTarget)}</strong> will leave Stored
              Parts and move to Deleted items.
            </p>
            <div className="part-lifecycle-preservation">
              <strong>This is reversible.</strong>
              <span>
                Stock quantities, template values, metadata, and movement
                history will be preserved.
              </span>
            </div>
            <dl className="part-lifecycle-summary">
              <div>
                <dt>Part number</dt>
                <dd>{deleteTarget.part_number || "Not specified"}</dd>
              </div>
              <div>
                <dt>Total stock</dt>
                <dd>{deleteTarget.total_quantity}</dd>
              </div>
              <div>
                <dt>Reserved</dt>
                <dd>{deleteTarget.reserved_quantity}</dd>
              </div>
            </dl>
            {deleteError ? (
              <div className="part-lifecycle-error" role="alert">
                {deleteError}
              </div>
            ) : null}
          </div>

          <footer>
            <button
              type="button"
              className="part-lifecycle-secondary"
              onClick={onCloseDelete}
              disabled={deleteSaving}
            >
              Cancel
            </button>
            <button
              type="button"
              className="part-lifecycle-danger"
              onClick={handleDelete}
              disabled={deleteSaving}
            >
              {deleteSaving ? "Deleting..." : "Delete part"}
            </button>
          </footer>
        </section>
      </div>
    );
  }

  if (!deletedPartsOpen) {
    return null;
  }

  return (
    <div
      className="part-lifecycle-backdrop"
      data-part-lifecycle-version="part-lifecycle-v153"
      data-part-lifecycle-purge="PARTPILOT:PERMANENT_PART_PURGE_UI:V607"
      role="presentation"
      onMouseDown={(event) => {
        if (
          event.target === event.currentTarget
          && restoringId === null
        ) {
          onCloseDeletedParts();
        }
      }}
    >
      <section
        className="part-lifecycle-dialog is-recovery"
        role="dialog"
        aria-modal="true"
        aria-labelledby="deleted-parts-title"
      >
        <header>
          <div>
            <p className="eyebrow">Inventory recovery</p>
            <h2 id="deleted-parts-title">Deleted items</h2>
            <p>
              Restore parts without losing their stock or history.
            </p>
          </div>
          <button
            type="button"
            className="part-lifecycle-close"
            onClick={onCloseDeletedParts}
            disabled={restoringId !== null}
            aria-label="Close deleted items"
            title="Close"
            autoFocus
          >
            ×
          </button>
        </header>

        <div className="part-lifecycle-content">
          <label className="part-lifecycle-search">
            <span className="sr-only">Search deleted parts</span>
            <input
              type="search"
              value={deletedQuery}
              onChange={(event) => setDeletedQuery(event.target.value)}
              placeholder="Search deleted parts..."
              disabled={deletedLoading || !deletedCollection}
            />
          </label>

          {partTypeFilter ? (
            <div className="part-lifecycle-filter-chip">
              <span>Type: {partTypeFilter.name}</span>
              <button
                type="button"
                onClick={onClearPartTypeFilter}
                disabled={purging || restoringId !== null}
                aria-label={`Clear ${partTypeFilter.name} filter`}
                title="Clear Part Type filter"
              >
                ×
              </button>
            </div>
          ) : null}

          {!deletedLoading && deletedCollection?.parts.length ? (
            <div className="part-lifecycle-selection-bar">
              <label className="part-lifecycle-select-visible">
                <input
                  type="checkbox"
                  checked={allVisibleSelected}
                  onChange={toggleVisibleSelection}
                  disabled={visibleDeletedParts.length === 0 || purging}
                />
                <span>Select visible</span>
              </label>
              <span>{selectedDeletedIds.size} selected</span>
              <button
                type="button"
                className="part-lifecycle-danger is-compact"
                onClick={openPurgeConfirmation}
                disabled={selectedDeletedIds.size === 0 || purging}
              >
                Delete permanently
              </button>
            </div>
          ) : null}

          {deletedLoading ? (
            <div className="part-lifecycle-state">
              Loading deleted parts...
            </div>
          ) : null}

          {deletedError ? (
            <div className="part-lifecycle-error" role="alert">
              {deletedError}
            </div>
          ) : null}

          {!deletedLoading
            && !deletedError
            && deletedCollection
            && deletedCollection.parts.length === 0 ? (
              <div className="part-lifecycle-state">
                <strong>No deleted parts</strong>
                <span>Deleted inventory records will appear here.</span>
              </div>
            ) : null}

          {!deletedLoading
            && !deletedError
            && deletedCollection
            && deletedCollection.parts.length > 0
            && visibleDeletedParts.length === 0 ? (
              <div className="part-lifecycle-state">
                <strong>
                  {partTypeFilter
                    ? `No deleted parts use ${partTypeFilter.name}`
                    : "No deleted parts match"}
                </strong>
                <span>
                  {partTypeFilter
                    ? "This Part Type no longer has recoverable dependencies."
                    : "Try a different search."}
                </span>
              </div>
            ) : null}

          {restoreError ? (
            <div className="part-lifecycle-error" role="alert">
              {restoreError}
            </div>
          ) : null}

          {purgeNotice ? (
            <div className="part-lifecycle-notice" role="status">
              {purgeNotice}
            </div>
          ) : null}

          {visibleDeletedParts.length > 0 ? (
            <div className="part-lifecycle-list">
              {visibleDeletedParts.map((part) => (
                <article key={part.id}>
                  <label className="part-lifecycle-row-select">
                    <input
                      type="checkbox"
                      checked={selectedDeletedIds.has(part.id)}
                      onChange={() => toggleDeletedSelection(part.id)}
                      disabled={restoringId !== null || purging}
                    />
                    <span className="sr-only">
                      Select {partName(part)} for permanent deletion
                    </span>
                  </label>
                  <div className="part-lifecycle-part-copy">
                    <strong>{partName(part)}</strong>
                    <span>
                      {part.part_number || "No part number"}
                      {" · "}
                      {part.part_type_name}
                    </span>
                    <small>
                      Deleted {dateLabel(part.deleted_at)}
                      {" · "}
                      Total stock {part.total_quantity}
                    </small>
                  </div>
                  <button
                    type="button"
                    className="part-lifecycle-restore"
                    onClick={() => handleRestore(part)}
                    disabled={restoringId !== null}
                  >
                    {restoringId === part.id
                      ? "Restoring..."
                      : "Restore"}
                  </button>
                </article>
              ))}
            </div>
          ) : null}
        </div>

        <footer>
          <span>
            {deletedCollection
              ? `${deletedCollection.total} deleted ${
                  deletedCollection.total === 1 ? "part" : "parts"
                }`
              : ""}
          </span>
          <button
            type="button"
            className="part-lifecycle-secondary"
            onClick={onCloseDeletedParts}
            disabled={restoringId !== null}
          >
            Close
          </button>
        </footer>
      </section>
    </div>
  );
}
