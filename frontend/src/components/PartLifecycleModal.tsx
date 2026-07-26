// PATCH 153: focused recoverable part lifecycle modal
import {
  useEffect,
  useMemo,
  useState
} from "react";
import {
  deletePart,
  getDeletedParts,
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
  onRestored
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

  const visibleDeletedParts = useMemo(() => {
    if (!deletedCollection) {
      return [];
    }

    const normalized = deletedQuery.trim().toLowerCase();
    if (!normalized) {
      return deletedCollection.parts;
    }

    return deletedCollection.parts.filter((part) =>
      [
        part.name,
        part.part_number,
        part.part_type_name,
        part.manufacturer_name,
        part.package
      ].some((value) => value?.toLowerCase().includes(normalized))
    );
  }, [deletedCollection, deletedQuery]);

  useEffect(() => {
    if (!deleteTarget && !deletedPartsOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") {
        return;
      }

      if (deleteTarget && !deleteSaving) {
        onCloseDelete();
      } else if (deletedPartsOpen && restoringId === null) {
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
      return;
    }

    let cancelled = false;
    setDeletedLoading(true);
    setDeletedError(null);
    setRestoreError(null);

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
                <strong>No deleted parts match</strong>
                <span>Try a different search.</span>
              </div>
            ) : null}

          {restoreError ? (
            <div className="part-lifecycle-error" role="alert">
              {restoreError}
            </div>
          ) : null}

          {visibleDeletedParts.length > 0 ? (
            <div className="part-lifecycle-list">
              {visibleDeletedParts.map((part) => (
                <article key={part.id}>
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
