// PARTPILOT:RESERVATIONS_WORKSPACE:V322

import {
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import type {
  ChangeEvent,
  FormEvent,
  MouseEvent
} from "react";

import { useAuth } from "../auth/AuthContext";
import {
  cancelReservation,
  consumeReservation,
  createReservation,
  expireReservation,
  getReservation,
  getReservations,
  searchReservableParts
} from "../services/reservationsClient";
import type {
  ReservablePart,
  Reservation,
  ReservationCollection,
  ReservationCreatePayload,
  ReservationStatus
} from "../types/reservations";

import "./Reservations.css";

const PAGE_SIZE = 25;

const STATUS_OPTIONS: Array<{
  value: ReservationStatus | "all";
  label: string;
}> = [
  { value: "all", label: "All" },
  { value: "active", label: "Active" },
  { value: "consumed", label: "Consumed" },
  { value: "cancelled", label: "Cancelled" },
  { value: "expired", label: "Expired" }
];

interface DraftItem {
  part: ReservablePart;
  quantity: number;
  note: string;
}

function formatDate(value: string | null): string {
  if (!value) {
    return "No expiry";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(date);
}

function formatMoney(
  value: number | string | null,
  currency: string | null
): string {
  if (value === null || value === undefined) {
    return "Not available";
  }
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    return String(value);
  }
  if (!currency) {
    return numberValue.toLocaleString();
  }
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency
    }).format(numberValue);
  } catch {
    return `${currency} ${numberValue.toLocaleString()}`;
  }
}

function statusLabel(status: ReservationStatus): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function reservationUnits(reservation: Reservation): number {
  return reservation.items.reduce(
    (total, item) => total + Number(item.quantity || 0),
    0
  );
}

function isDue(reservation: Reservation): boolean {
  if (!reservation.expiry_at) {
    return false;
  }
  const expiry = Date.parse(reservation.expiry_at);
  return Number.isFinite(expiry) && expiry <= Date.now();
}

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : "Unexpected request failure.";
}

export function Reservations() {
  const { token } = useAuth();

  const [collection, setCollection] = useState<ReservationCollection>({
    total: 0,
    limit: PAGE_SIZE,
    offset: 0,
    reservations: []
  });
  const [statusFilter, setStatusFilter] =
    useState<ReservationStatus | "all">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [pageOffset, setPageOffset] = useState(0);
  const [reloadVersion, setReloadVersion] = useState(0);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedReservation, setSelectedReservation] =
    useState<Reservation | null>(null);

  const [listLoading, setListLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [listError, setListError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [actionName, setActionName] = useState<
    "cancel" | "consume" | "expire" | null
  >(null);
  const [actionError, setActionError] = useState("");

  const [createOpen, setCreateOpen] = useState(false);
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState("");
  const [draftLabel, setDraftLabel] = useState("");
  const [draftNotes, setDraftNotes] = useState("");
  const [draftExpiry, setDraftExpiry] = useState("");
  const [draftItems, setDraftItems] = useState<DraftItem[]>([]);
  const [partQuery, setPartQuery] = useState("");
  const [partOptions, setPartOptions] = useState<ReservablePart[]>([]);
  const [partSearchLoading, setPartSearchLoading] = useState(false);
  const [partSearchError, setPartSearchError] = useState("");

  const listRequest = useRef(0);
  const detailRequest = useRef(0);

  useEffect(() => {
    if (!token) {
      setCollection({
        total: 0,
        limit: PAGE_SIZE,
        offset: 0,
        reservations: []
      });
      setSelectedId(null);
      setSelectedReservation(null);
      setListLoading(false);
      return;
    }

    const controller = new AbortController();
    const requestId = ++listRequest.current;
    setListLoading(true);
    setListError("");

    void getReservations(token, {
      status: statusFilter === "all" ? undefined : statusFilter,
      limit: PAGE_SIZE,
      offset: pageOffset,
      signal: controller.signal
    })
      .then((nextCollection) => {
        if (requestId !== listRequest.current) {
          return;
        }
        setCollection(nextCollection);
        setSelectedId((current) => {
          if (
            current !== null &&
            nextCollection.reservations.some(
              (reservation) => reservation.id === current
            )
          ) {
            return current;
          }
          return nextCollection.reservations[0]?.id ?? null;
        });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          (error instanceof DOMException && error.name === "AbortError")
        ) {
          return;
        }
        if (requestId === listRequest.current) {
          setListError(messageFrom(error));
        }
      })
      .finally(() => {
        if (requestId === listRequest.current) {
          setListLoading(false);
        }
      });

    return () => controller.abort();
  }, [pageOffset, reloadVersion, statusFilter, token]);

  useEffect(() => {
    if (!token || selectedId === null) {
      setSelectedReservation(null);
      setDetailLoading(false);
      return;
    }

    const controller = new AbortController();
    const requestId = ++detailRequest.current;
    setDetailLoading(true);
    setDetailError("");
    setActionError("");

    void getReservation(token, selectedId, controller.signal)
      .then((reservation) => {
        if (requestId === detailRequest.current) {
          setSelectedReservation(reservation);
        }
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          (error instanceof DOMException && error.name === "AbortError")
        ) {
          return;
        }
        if (requestId === detailRequest.current) {
          setDetailError(messageFrom(error));
          setSelectedReservation(null);
        }
      })
      .finally(() => {
        if (requestId === detailRequest.current) {
          setDetailLoading(false);
        }
      });

    return () => controller.abort();
  }, [selectedId, token]);

  useEffect(() => {
    if (!createOpen || !token) {
      return;
    }
    const query = partQuery.trim();
    if (query.length < 2) {
      setPartOptions([]);
      setPartSearchLoading(false);
      setPartSearchError("");
      return;
    }

    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      setPartSearchLoading(true);
      setPartSearchError("");
      void searchReservableParts(token, query, controller.signal)
        .then(setPartOptions)
        .catch((error: unknown) => {
          if (
            controller.signal.aborted ||
            (error instanceof DOMException && error.name === "AbortError")
          ) {
            return;
          }
          setPartSearchError(messageFrom(error));
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setPartSearchLoading(false);
          }
        });
    }, 280);

    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [createOpen, partQuery, token]);

  useEffect(() => {
    if (!createOpen) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !createSubmitting) {
        setCreateOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [createOpen, createSubmitting]);

  const visibleReservations = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) {
      return collection.reservations;
    }
    return collection.reservations.filter((reservation) => {
      const partText = reservation.items
        .map((item) => `${item.part_number ?? ""} ${item.part_name ?? ""}`)
        .join(" ");
      return [
        reservation.label,
        reservation.notes ?? "",
        reservation.created_by,
        partText
      ]
        .join(" ")
        .toLowerCase()
        .includes(query);
    });
  }, [collection.reservations, searchQuery]);

  const pageNumber = Math.floor(pageOffset / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(collection.total / PAGE_SIZE));
  const pageActiveCount = collection.reservations.filter(
    (reservation) => reservation.status === "active"
  ).length;
  const pageDueCount = collection.reservations.filter(
    (reservation) =>
      reservation.status === "active" && isDue(reservation)
  ).length;
  const pageReservedUnits = collection.reservations
    .filter((reservation) => reservation.status === "active")
    .reduce((total, reservation) => total + reservationUnits(reservation), 0);

  const resetCreateForm = () => {
    setDraftLabel("");
    setDraftNotes("");
    setDraftExpiry("");
    setDraftItems([]);
    setPartQuery("");
    setPartOptions([]);
    setPartSearchError("");
    setCreateError("");
  };

  const openCreate = () => {
    resetCreateForm();
    setCreateOpen(true);
  };

  const closeCreate = () => {
    if (!createSubmitting) {
      setCreateOpen(false);
    }
  };

  const addDraftItem = (part: ReservablePart) => {
    setDraftItems((current) => {
      if (current.some((item) => item.part.id === part.id)) {
        return current;
      }
      return [...current, { part, quantity: 1, note: "" }];
    });
    setPartQuery("");
    setPartOptions([]);
  };

  const updateDraftQuantity = (partId: number, quantity: number) => {
    setDraftItems((current) =>
      current.map((item) =>
        item.part.id === partId
          ? {
              ...item,
              quantity: Math.max(
                1,
                Math.min(
                  Number.isFinite(quantity) ? quantity : 1,
                  item.part.available_quantity
                )
              )
            }
          : item
      )
    );
  };

  const updateDraftNote = (partId: number, note: string) => {
    setDraftItems((current) =>
      current.map((item) =>
        item.part.id === partId ? { ...item, note } : item
      )
    );
  };

  const removeDraftItem = (partId: number) => {
    setDraftItems((current) =>
      current.filter((item) => item.part.id !== partId)
    );
  };

  const submitReservation = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || createSubmitting) {
      return;
    }
    if (!draftLabel.trim()) {
      setCreateError("A reservation label is required.");
      return;
    }
    if (draftItems.length === 0) {
      setCreateError("Add at least one available part.");
      return;
    }

    let expiryAt: string | null = null;
    if (draftExpiry) {
      const parsed = new Date(draftExpiry);
      if (Number.isNaN(parsed.getTime())) {
        setCreateError("Enter a valid expiry date and time.");
        return;
      }
      if (parsed.getTime() <= Date.now()) {
        setCreateError("Expiry must be in the future.");
        return;
      }
      expiryAt = parsed.toISOString();
    }

    const payload: ReservationCreatePayload = {
      label: draftLabel.trim(),
      notes: draftNotes.trim() || null,
      expiry_at: expiryAt,
      items: draftItems.map((item) => ({
        part_id: item.part.id,
        quantity: item.quantity,
        note: item.note.trim() || null
      }))
    };

    setCreateSubmitting(true);
    setCreateError("");
    try {
      const created = await createReservation(token, payload);
      setCreateOpen(false);
      resetCreateForm();
      setStatusFilter("active");
      setPageOffset(0);
      setSelectedId(created.id);
      setSelectedReservation(created);
      setReloadVersion((value) => value + 1);
    } catch (error: unknown) {
      setCreateError(messageFrom(error));
    } finally {
      setCreateSubmitting(false);
    }
  };

  const runAction = async (
    action: "cancel" | "consume" | "expire"
  ) => {
    if (!token || !selectedReservation || actionName) {
      return;
    }

    const verbs = {
      cancel: "Cancel",
      consume: "Consume",
      expire: "Expire"
    } as const;
    const confirmed = window.confirm(
      `${verbs[action]} reservation "${selectedReservation.label}"?`
    );
    if (!confirmed) {
      return;
    }

    setActionName(action);
    setActionError("");
    try {
      const updated =
        action === "cancel"
          ? await cancelReservation(token, selectedReservation.id)
          : action === "consume"
            ? await consumeReservation(token, selectedReservation.id)
            : await expireReservation(token, selectedReservation.id);
      setSelectedReservation(updated);
      setReloadVersion((value) => value + 1);
    } catch (error: unknown) {
      setActionError(messageFrom(error));
    } finally {
      setActionName(null);
    }
  };

  return (
    <section
      className="page-stack reservations-page"
      data-partpilot-marker="PARTPILOT:RESERVATIONS_WORKSPACE:V322"
    >
      <header className="reservations-header">
        <div className="page-header">
          <p className="eyebrow">Inventory commitments</p>
          <h1>Reservations</h1>
          <p>
            Review reserved stock, inspect item-level availability, and move
            active reservations through cancellation, consumption, or expiry.
          </p>
        </div>
        <button
          className="reservations-button reservations-button-primary"
          type="button"
          onClick={openCreate}
        >
          New reservation
        </button>
      </header>

      <div className="reservations-summary" aria-label="Reservation summary">
        <article>
          <span>Total results</span>
          <strong>{collection.total}</strong>
        </article>
        <article>
          <span>Active on page</span>
          <strong>{pageActiveCount}</strong>
        </article>
        <article>
          <span>Due on page</span>
          <strong>{pageDueCount}</strong>
        </article>
        <article>
          <span>Reserved units on page</span>
          <strong>{pageReservedUnits}</strong>
        </article>
      </div>

      <div className="reservations-toolbar">
        <div
          className="reservations-status-tabs"
          role="group"
          aria-label="Filter reservations by status"
        >
          {STATUS_OPTIONS.map((option) => (
            <button
              className={
                statusFilter === option.value
                  ? "reservations-status-tab is-active"
                  : "reservations-status-tab"
              }
              key={option.value}
              type="button"
              onClick={() => {
                setStatusFilter(option.value);
                setPageOffset(0);
                setSelectedId(null);
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
        <label className="reservations-search">
          <span className="sr-only">Search loaded reservations</span>
          <input
            type="search"
            value={searchQuery}
            onChange={(event: ChangeEvent<HTMLInputElement>) =>
              setSearchQuery(event.currentTarget.value)
            }
            placeholder="Search this page"
          />
        </label>
        <button
          className="reservations-button"
          type="button"
          onClick={() => setReloadVersion((value) => value + 1)}
          disabled={listLoading}
        >
          Refresh
        </button>
      </div>

      {listError ? (
        <div className="reservations-notice is-error" role="alert">
          <strong>Reservations could not be loaded.</strong>
          <span>{listError}</span>
        </div>
      ) : null}

      <div className="reservations-workspace">
        <section className="reservations-list-panel" aria-label="Reservations">
          <div className="reservations-list-heading">
            <div>
              <strong>Reservation register</strong>
              <span>
                Page {pageNumber} of {pageCount}
              </span>
            </div>
            <span>
              {visibleReservations.length} shown
            </span>
          </div>

          <div className="reservations-list-columns" aria-hidden="true">
            <span>Reservation</span>
            <span>Status</span>
            <span>Units</span>
            <span>Updated</span>
          </div>

          <div className="reservations-list" aria-live="polite">
            {listLoading ? (
              <div className="reservations-list-state">
                Loading reservations…
              </div>
            ) : visibleReservations.length === 0 ? (
              <div className="reservations-list-state">
                <strong>No matching reservations</strong>
                <span>
                  Change the status filter, clear the page search, or create a
                  reservation.
                </span>
              </div>
            ) : (
              visibleReservations.map((reservation) => (
                <button
                  className={
                    selectedId === reservation.id
                      ? "reservation-row is-selected"
                      : "reservation-row"
                  }
                  key={reservation.id}
                  type="button"
                  aria-pressed={selectedId === reservation.id}
                  onClick={() => setSelectedId(reservation.id)}
                >
                  <span className="reservation-row-main">
                    <strong>{reservation.label}</strong>
                    <small>
                      {reservation.items.length} part
                      {reservation.items.length === 1 ? "" : "s"}
                      {" · "}
                      {reservation.expiry_at
                        ? `Expires ${formatDate(reservation.expiry_at)}`
                        : "No expiry"}
                    </small>
                  </span>
                  <span
                    className={`reservation-status is-${reservation.status}`}
                  >
                    {statusLabel(reservation.status)}
                  </span>
                  <span className="reservation-row-number">
                    {reservationUnits(reservation)}
                  </span>
                  <span className="reservation-row-date">
                    {formatDate(reservation.updated_at)}
                  </span>
                </button>
              ))
            )}
          </div>

          <footer className="reservations-pagination">
            <button
              className="reservations-button"
              type="button"
              disabled={pageOffset === 0 || listLoading}
              onClick={() =>
                setPageOffset((value) => Math.max(0, value - PAGE_SIZE))
              }
            >
              Previous
            </button>
            <span>
              {collection.total === 0
                ? "0 results"
                : `${pageOffset + 1}–${Math.min(
                    pageOffset + PAGE_SIZE,
                    collection.total
                  )} of ${collection.total}`}
            </span>
            <button
              className="reservations-button"
              type="button"
              disabled={
                pageOffset + PAGE_SIZE >= collection.total || listLoading
              }
              onClick={() => setPageOffset((value) => value + PAGE_SIZE)}
            >
              Next
            </button>
          </footer>
        </section>

        <aside className="reservation-detail-panel">
          {detailLoading ? (
            <div className="reservation-detail-state">
              Loading reservation details…
            </div>
          ) : detailError ? (
            <div className="reservation-detail-state is-error" role="alert">
              <strong>Reservation details could not be loaded.</strong>
              <span>{detailError}</span>
            </div>
          ) : !selectedReservation ? (
            <div className="reservation-detail-state">
              <strong>Select a reservation</strong>
              <span>
                Item quantities, expiry, value, notes, and lifecycle actions
                will appear here.
              </span>
            </div>
          ) : (
            <>
              <div className="reservation-detail-header">
                <div>
                  <span
                    className={`reservation-status is-${selectedReservation.status}`}
                  >
                    {statusLabel(selectedReservation.status)}
                  </span>
                  <h2>{selectedReservation.label}</h2>
                  <p>
                    Reservation #{selectedReservation.id}
                    {" · "}
                    Created {formatDate(selectedReservation.created_at)}
                  </p>
                </div>
                <button
                  className="reservations-button reservations-close-mobile"
                  type="button"
                  onClick={() => setSelectedId(null)}
                >
                  Close
                </button>
              </div>

              <dl className="reservation-facts">
                <div>
                  <dt>Expiry</dt>
                  <dd>{formatDate(selectedReservation.expiry_at)}</dd>
                </div>
                <div>
                  <dt>Reserved value</dt>
                  <dd>
                    {formatMoney(
                      selectedReservation.estimated_reserved_value,
                      selectedReservation.currency_snapshot
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Created by</dt>
                  <dd>{selectedReservation.created_by}</dd>
                </div>
                <div>
                  <dt>Linked project</dt>
                  <dd>
                    {selectedReservation.project_id
                      ? `#${selectedReservation.project_id}`
                      : "Not linked"}
                  </dd>
                </div>
              </dl>

              {selectedReservation.notes ? (
                <div className="reservation-notes">
                  <span>Notes</span>
                  <p>{selectedReservation.notes}</p>
                </div>
              ) : null}

              <div className="reservation-items-heading">
                <div>
                  <strong>Reserved parts</strong>
                  <span>{reservationUnits(selectedReservation)} units</span>
                </div>
              </div>

              <div className="reservation-items">
                {selectedReservation.items.map((item) => (
                  <article className="reservation-item" key={item.id}>
                    <div className="reservation-item-main">
                      <strong>{item.part_number ?? "Deleted part"}</strong>
                      <span>{item.part_name ?? "Part no longer available"}</span>
                    </div>
                    <dl>
                      <div>
                        <dt>Reserved</dt>
                        <dd>{item.quantity}</dd>
                      </div>
                      <div>
                        <dt>Physical</dt>
                        <dd>{item.total_quantity ?? "—"}</dd>
                      </div>
                      <div>
                        <dt>Available</dt>
                        <dd>{item.available_quantity ?? "—"}</dd>
                      </div>
                    </dl>
                    {item.note ? <p>{item.note}</p> : null}
                  </article>
                ))}
              </div>

              {actionError ? (
                <div className="reservations-notice is-error" role="alert">
                  <span>{actionError}</span>
                </div>
              ) : null}

              {selectedReservation.status === "active" ? (
                <div className="reservation-actions">
                  <button
                    className="reservations-button reservations-button-primary"
                    type="button"
                    disabled={actionName !== null}
                    onClick={() => void runAction("consume")}
                  >
                    {actionName === "consume"
                      ? "Consuming…"
                      : "Consume reservation"}
                  </button>
                  <button
                    className="reservations-button"
                    type="button"
                    disabled={actionName !== null}
                    onClick={() => void runAction("cancel")}
                  >
                    {actionName === "cancel" ? "Cancelling…" : "Cancel"}
                  </button>
                  {isDue(selectedReservation) ? (
                    <button
                      className="reservations-button"
                      type="button"
                      disabled={actionName !== null}
                      onClick={() => void runAction("expire")}
                    >
                      {actionName === "expire" ? "Expiring…" : "Mark expired"}
                    </button>
                  ) : null}
                </div>
              ) : null}
            </>
          )}
        </aside>
      </div>

      {createOpen ? (
        <div
          className="reservation-modal-backdrop"
          role="presentation"
          onMouseDown={(event: MouseEvent<HTMLDivElement>) => {
            if (event.target === event.currentTarget) {
              closeCreate();
            }
          }}
        >
          <section
            className="reservation-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="reservation-create-title"
          >
            <header>
              <div>
                <p className="eyebrow">Reserve inventory</p>
                <h2 id="reservation-create-title">New reservation</h2>
                <p>
                  Select available parts and reserve quantities without changing
                  physical stock.
                </p>
              </div>
              <button
                className="reservations-button"
                type="button"
                onClick={closeCreate}
                disabled={createSubmitting}
              >
                Close
              </button>
            </header>

            <form
              onSubmit={(event: FormEvent<HTMLFormElement>) =>
                void submitReservation(event)
              }
            >
              <div className="reservation-form-grid">
                <label>
                  <span>Label</span>
                  <input
                    required
                    maxLength={180}
                    value={draftLabel}
                    onChange={(event: ChangeEvent<HTMLInputElement>) =>
                      setDraftLabel(event.currentTarget.value)
                    }
                    placeholder="Prototype controller build"
                  />
                </label>
                <label>
                  <span>Expiry</span>
                  <input
                    type="datetime-local"
                    value={draftExpiry}
                    onChange={(event: ChangeEvent<HTMLInputElement>) =>
                      setDraftExpiry(event.currentTarget.value)
                    }
                  />
                </label>
                <label className="reservation-form-wide">
                  <span>Notes</span>
                  <textarea
                    rows={3}
                    maxLength={10000}
                    value={draftNotes}
                    onChange={(event: ChangeEvent<HTMLTextAreaElement>) =>
                      setDraftNotes(event.currentTarget.value)
                    }
                    placeholder="Optional context for this reservation"
                  />
                </label>
              </div>

              <div className="reservation-part-picker">
                <label>
                  <span>Find parts</span>
                  <input
                    type="search"
                    value={partQuery}
                    onChange={(event: ChangeEvent<HTMLInputElement>) =>
                      setPartQuery(event.currentTarget.value)
                    }
                    placeholder="Search part number, name, tag, or metadata"
                    autoComplete="off"
                  />
                </label>
                <div className="reservation-part-results" aria-live="polite">
                  {partSearchLoading ? (
                    <span>Searching inventory…</span>
                  ) : partSearchError ? (
                    <span className="is-error">{partSearchError}</span>
                  ) : partQuery.trim().length < 2 ? (
                    <span>Enter at least two characters.</span>
                  ) : partOptions.length === 0 ? (
                    <span>No available matching parts.</span>
                  ) : (
                    partOptions.map((part) => (
                      <button
                        key={part.id}
                        type="button"
                        onClick={() => addDraftItem(part)}
                        disabled={draftItems.some(
                          (item) => item.part.id === part.id
                        )}
                      >
                        <span>
                          <strong>{part.part_number}</strong>
                          <small>{part.name}</small>
                        </span>
                        <span>
                          {part.available_quantity} available
                        </span>
                      </button>
                    ))
                  )}
                </div>
              </div>

              <div className="reservation-draft-items">
                <div className="reservation-draft-heading">
                  <strong>Reservation items</strong>
                  <span>{draftItems.length} selected</span>
                </div>
                {draftItems.length === 0 ? (
                  <div className="reservation-draft-empty">
                    Search and add one or more available parts.
                  </div>
                ) : (
                  draftItems.map((item) => (
                    <article key={item.part.id}>
                      <div>
                        <strong>{item.part.part_number}</strong>
                        <span>{item.part.name}</span>
                        <small>
                          {item.part.available_quantity} available
                        </small>
                      </div>
                      <label>
                        <span>Quantity</span>
                        <input
                          type="number"
                          min={1}
                          max={item.part.available_quantity}
                          value={item.quantity}
                          onChange={(event: ChangeEvent<HTMLInputElement>) =>
                            updateDraftQuantity(
                              item.part.id,
                              Number(event.currentTarget.value)
                            )
                          }
                        />
                      </label>
                      <label className="reservation-draft-note">
                        <span>Item note</span>
                        <input
                          maxLength={5000}
                          value={item.note}
                          onChange={(event: ChangeEvent<HTMLInputElement>) =>
                            updateDraftNote(
                              item.part.id,
                              event.currentTarget.value
                            )
                          }
                          placeholder="Optional"
                        />
                      </label>
                      <button
                        className="reservations-button"
                        type="button"
                        onClick={() => removeDraftItem(item.part.id)}
                      >
                        Remove
                      </button>
                    </article>
                  ))
                )}
              </div>

              {createError ? (
                <div className="reservations-notice is-error" role="alert">
                  <span>{createError}</span>
                </div>
              ) : null}

              <footer>
                <button
                  className="reservations-button"
                  type="button"
                  onClick={closeCreate}
                  disabled={createSubmitting}
                >
                  Cancel
                </button>
                <button
                  className="reservations-button reservations-button-primary"
                  type="submit"
                  disabled={createSubmitting || draftItems.length === 0}
                >
                  {createSubmitting ? "Creating…" : "Create reservation"}
                </button>
              </footer>
            </form>
          </section>
        </div>
      ) : null}
    </section>
  );
}
