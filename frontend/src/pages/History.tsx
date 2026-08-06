// PARTPILOT:SYSTEM_HISTORY_WORKSPACE:V408

import {
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import type { ChangeEvent } from "react";

import { useAuth } from "../auth/AuthContext";
import {
  getHistory,
  getHistoryFilterOptions
} from "../services/historyClient";
import type {
  HistoryCollection,
  HistoryEntry,
  HistoryFilterOptions,
  HistoryJson,
  HistoryKind
} from "../types/history";

import "./History.css";

const PAGE_SIZE = 50;
const SEARCH_DELAY_MS = 280;

// PARTPILOT:HISTORY_TECHNICAL_ACRONYMS:V529
const TECHNICAL_ACRONYMS: Readonly<Record<string, string>> = {
  __partpilot_marker: "Part Pilot History Acronyms V529",
  api: "API",
  cidr: "CIDR",
  csv: "CSV",
  http: "HTTP",
  https: "HTTPS",
  id: "ID",
  ip: "IP",
  json: "JSON",
  mcp: "MCP",
  oauth: "OAuth",
  pkce: "PKCE",
  ui: "UI",
  uri: "URI",
  url: "URL"
};

const EMPTY_COLLECTION: HistoryCollection = {
  total: 0,
  limit: PAGE_SIZE,
  offset: 0,
  entries: []
};

const EMPTY_OPTIONS: HistoryFilterOptions = {
  kinds: [],
  entity_types: [],
  event_types: [],
  actor_types: [],
  movement_types: [],
  sources: [],
  actors: [],
  earliest_at: null,
  latest_at: null
};

const EVENT_TITLES: Record<string, string> = {
  "location.created": "Location created",
  "manufacturer.created": "Manufacturer created",
  "package.created": "Package created",
  "part.created": "Part created",
  "part.deleted": "Part deleted",
  "part.metadata_updated": "Part details updated",
  "part.quantity_adjusted": "Physical stock adjusted",
  "part.restored": "Part restored",
  "part_type.created": "Part type created",
  "part_type.deleted": "Part type deleted",
  "part_type.updated": "Part type updated",
  "project.created": "Project created",
  "project.updated": "Project updated",
  "project.reserved": "Project reserved",
  "project.consumed": "Project consumed",
  "project.cancelled": "Project cancelled",
  "reservation.created": "Reservation created",
  "reservation.updated": "Reservation updated",
  "reservation.consumed": "Reservation consumed",
  "reservation.cancelled": "Reservation cancelled",
  "reservation.expired": "Reservation expired",
  "stock.adjust": "Physical stock adjusted",
  "stock.consume": "Reserved stock consumed",
  "stock.release": "Reserved stock released",
  "stock.reserve": "Stock reserved",
  "stock.restock": "Stock restocked"
};

function messageFrom(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Unexpected request failure.";
}

function parseApiDateTime(value: string): Date {
  const normalised = value.trim().replace(" ", "T");
  const zoned = /(?:Z|[+-]\d{2}:\d{2})$/i.test(normalised)
    ? normalised
    : `${normalised}Z`;
  return new Date(zoned);
}

function formatDate(value: string | null): string {
  if (!value) {
    return "Not recorded";
  }
  const date = parseApiDateTime(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(date);
}

function formatCompactDate(value: string): string {
  const date = parseApiDateTime(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(date);
}

function localInputToIso(value: string): string | undefined {
  if (!value) {
    return undefined;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return undefined;
  }
  return date.toISOString();
}

function humanise(value: string | null): string {
  if (!value) {
    return "Not recorded";
  }

  return value
    .split(/[._-]+/)
    .filter(Boolean)
    .map((word) => {
      const normalised = word.toLowerCase();
      return (
        TECHNICAL_ACRONYMS[normalised] ??
        `${normalised.charAt(0).toUpperCase()}${normalised.slice(1)}`
      );
    })
    .join(" ");
}

// PARTPILOT:HISTORY_ENTITY_ACRONYM_NORMALIZATION:V543
function normaliseTechnicalLabel(value: string): string {
  return value.replace(
    /\b(api|cidr|csv|http|https|id|ip|json|mcp|oauth|pkce|ui|uri|url)\b/gi,
    (word) => TECHNICAL_ACRONYMS[word.toLowerCase()] ?? word
  );
}

function eventTitle(entry: HistoryEntry): string {
  return EVENT_TITLES[entry.event_type] ?? humanise(entry.event_type);
}

function kindLabel(kind: HistoryKind): string {
  return kind === "audit" ? "Audit" : "Stock";
}

function actorLabel(entry: HistoryEntry): string {
  if (entry.actor_display_name) {
    return entry.actor_display_name;
  }
  if (entry.actor_type) {
    return humanise(entry.actor_type);
  }
  return "Unknown actor";
}

function entityLabel(entry: HistoryEntry): string {
  if (entry.entity_label) {
    return normaliseTechnicalLabel(entry.entity_label);
  }
  if (entry.entity_type && entry.entity_id !== null) {
    return `${humanise(entry.entity_type)} #${entry.entity_id}`;
  }
  return humanise(entry.entity_type);
}

function jsonText(value: HistoryJson): string {
  if (value === null) {
    return "No data recorded";
  }
  return JSON.stringify(value, null, 2);
}

function hasJson(value: HistoryJson): boolean {
  if (value === null) {
    return false;
  }
  if (Array.isArray(value)) {
    return value.length > 0;
  }
  return Object.keys(value).length > 0;
}

function stockDelta(entry: HistoryEntry): number {
  if (
    entry.reserved_quantity_before !== null &&
    entry.reserved_quantity_after !== null
  ) {
    const reservedDelta =
      entry.reserved_quantity_after -
      entry.reserved_quantity_before;
    if (reservedDelta !== 0) {
      return reservedDelta;
    }
  }
  return entry.quantity_delta ?? 0;
}

function signedNumber(value: number): string {
  return value > 0 ? `+${value}` : String(value);
}

function countFacet(
  options: HistoryFilterOptions,
  kind: HistoryKind
): number {
  return options.kinds.find((option) => option.value === kind)?.count ?? 0;
}

export function History() {
  const { token } = useAuth();

  const [collection, setCollection] =
    useState<HistoryCollection>(EMPTY_COLLECTION);
  const [filterOptions, setFilterOptions] =
    useState<HistoryFilterOptions>(EMPTY_OPTIONS);

  const [queryInput, setQueryInput] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [kindFilter, setKindFilter] =
    useState<HistoryKind | "all">("all");
  const [entityFilter, setEntityFilter] = useState("");
  const [eventFilter, setEventFilter] = useState("");
  const [actorTypeFilter, setActorTypeFilter] = useState("");
  const [actorUserFilter, setActorUserFilter] = useState("");
  const [movementFilter, setMovementFilter] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [pageOffset, setPageOffset] = useState(0);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [reloadVersion, setReloadVersion] = useState(0);

  const [listLoading, setListLoading] = useState(true);
  const [optionsLoading, setOptionsLoading] = useState(true);
  const [listError, setListError] = useState("");
  const [optionsError, setOptionsError] = useState("");

  const listRequest = useRef(0);
  const optionsRequest = useRef(0);

  const dateRangeError = useMemo(() => {
    if (!fromDate || !toDate) {
      return "";
    }
    const from = new Date(fromDate);
    const to = new Date(toDate);
    if (
      Number.isNaN(from.getTime()) ||
      Number.isNaN(to.getTime())
    ) {
      return "Enter valid start and end dates.";
    }
    return from > to
      ? "The start date must not be after the end date."
      : "";
  }, [fromDate, toDate]);

  const activeFilterCount = useMemo(
    () =>
      [
        debouncedQuery.trim(),
        kindFilter === "all" ? "" : kindFilter,
        entityFilter,
        eventFilter,
        actorTypeFilter,
        actorUserFilter,
        movementFilter,
        fromDate,
        toDate
      ].filter(Boolean).length,
    [
      actorTypeFilter,
      actorUserFilter,
      debouncedQuery,
      entityFilter,
      eventFilter,
      fromDate,
      kindFilter,
      movementFilter,
      toDate
    ]
  );

  const selectedEntry = useMemo(
    () =>
      collection.entries.find((entry) => entry.key === selectedKey) ??
      null,
    [collection.entries, selectedKey]
  );

  const pageCount = Math.max(
    1,
    Math.ceil(collection.total / PAGE_SIZE)
  );
  const pageNumber = Math.floor(pageOffset / PAGE_SIZE) + 1;

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedQuery(queryInput.trim());
      setPageOffset(0);
    }, SEARCH_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [queryInput]);

  useEffect(() => {
    if (!token) {
      setFilterOptions(EMPTY_OPTIONS);
      setOptionsLoading(false);
      return;
    }

    const controller = new AbortController();
    const requestId = ++optionsRequest.current;
    setOptionsLoading(true);
    setOptionsError("");

    void getHistoryFilterOptions(token, controller.signal)
      .then((options) => {
        if (requestId === optionsRequest.current) {
          setFilterOptions(options);
        }
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          (error instanceof DOMException &&
            error.name === "AbortError")
        ) {
          return;
        }
        if (requestId === optionsRequest.current) {
          setOptionsError(messageFrom(error));
        }
      })
      .finally(() => {
        if (requestId === optionsRequest.current) {
          setOptionsLoading(false);
        }
      });

    return () => controller.abort();
  }, [reloadVersion, token]);

  useEffect(() => {
    if (!token) {
      setCollection(EMPTY_COLLECTION);
      setSelectedKey(null);
      setListLoading(false);
      return;
    }
    if (dateRangeError) {
      setListError(dateRangeError);
      setListLoading(false);
      return;
    }

    const controller = new AbortController();
    const requestId = ++listRequest.current;
    setListLoading(true);
    setListError("");

    void getHistory(token, {
      kind: kindFilter === "all" ? undefined : kindFilter,
      entityType: entityFilter || undefined,
      eventType: eventFilter || undefined,
      actorType: actorTypeFilter || undefined,
      actorUserId: actorUserFilter
        ? Number(actorUserFilter)
        : undefined,
      movementType: movementFilter || undefined,
      from: localInputToIso(fromDate),
      to: localInputToIso(toDate),
      query: debouncedQuery || undefined,
      limit: PAGE_SIZE,
      offset: pageOffset,
      signal: controller.signal
    })
      .then((nextCollection) => {
        if (requestId !== listRequest.current) {
          return;
        }
        setCollection(nextCollection);
        setSelectedKey((current) => {
          if (
            current !== null &&
            nextCollection.entries.some(
              (entry) => entry.key === current
            )
          ) {
            return current;
          }
          if (window.matchMedia("(max-width: 900px)").matches) {
            return null;
          }
          return nextCollection.entries[0]?.key ?? null;
        });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          (error instanceof DOMException &&
            error.name === "AbortError")
        ) {
          return;
        }
        if (requestId === listRequest.current) {
          setListError(messageFrom(error));
          setCollection({
            ...EMPTY_COLLECTION,
            offset: pageOffset
          });
          setSelectedKey(null);
        }
      })
      .finally(() => {
        if (requestId === listRequest.current) {
          setListLoading(false);
        }
      });

    return () => controller.abort();
  }, [
    actorTypeFilter,
    actorUserFilter,
    dateRangeError,
    debouncedQuery,
    entityFilter,
    eventFilter,
    fromDate,
    kindFilter,
    movementFilter,
    pageOffset,
    reloadVersion,
    toDate,
    token
  ]);

  function resetPage(): void {
    setPageOffset(0);
  }

  function chooseKind(value: HistoryKind | "all"): void {
    setKindFilter(value);
    if (value === "audit") {
      setMovementFilter("");
    }
    resetPage();
  }

  function clearFilters(): void {
    setQueryInput("");
    setDebouncedQuery("");
    setKindFilter("all");
    setEntityFilter("");
    setEventFilter("");
    setActorTypeFilter("");
    setActorUserFilter("");
    setMovementFilter("");
    setFromDate("");
    setToDate("");
    setPageOffset(0);
    setSelectedKey(null);
  }

  const auditTotal = countFacet(filterOptions, "audit");
  const movementTotal = countFacet(
    filterOptions,
    "stock_movement"
  );

  return (
    <section
      className="page-stack history-page"
      data-partpilot-history="PARTPILOT:SYSTEM_HISTORY_WORKSPACE:V408"
      data-partpilot-history-mobile="PARTPILOT:HISTORY_MOBILE_REGISTER_FIRST:V408"
      data-partpilot-history-entity-acronyms="PARTPILOT:HISTORY_ENTITY_ACRONYM_NORMALIZATION:V543"
    >
      <header className="history-header">
        <div className="page-header">
          <p className="eyebrow">System-wide operational record</p>
          <h1>History</h1>
          <p>
            Search inventory movements, Project and Reservation lifecycle
            events, catalogue changes, settings updates, actors, and exact
            before-and-after records from one chronological register.
          </p>
        </div>
        <button
          className="history-button"
          type="button"
          disabled={listLoading || optionsLoading}
          onClick={() => setReloadVersion((value) => value + 1)}
        >
          Refresh
        </button>
      </header>

      <div className="history-summary" aria-label="History summary">
        <article>
          <span>Matching events</span>
          <strong>{collection.total}</strong>
        </article>
        <article>
          <span>Audit records</span>
          <strong>{optionsLoading ? "—" : auditTotal}</strong>
        </article>
        <article>
          <span>Stock movements</span>
          <strong>{optionsLoading ? "—" : movementTotal}</strong>
        </article>
        <article>
          <span>Active filters</span>
          <strong>{activeFilterCount}</strong>
        </article>
      </div>

      <section className="history-controls" aria-label="History filters">
        <div className="history-primary-controls">
          <div
            className="history-kind-tabs"
            role="group"
            aria-label="Filter by record kind"
          >
            {[
              { value: "all", label: "All events" },
              { value: "audit", label: "Audit" },
              { value: "stock_movement", label: "Stock" }
            ].map((option) => (
              <button
                className={
                  kindFilter === option.value
                    ? "history-kind-tab is-active"
                    : "history-kind-tab"
                }
                key={option.value}
                type="button"
                onClick={() =>
                  chooseKind(
                    option.value as HistoryKind | "all"
                  )
                }
              >
                {option.label}
              </button>
            ))}
          </div>

          <label className="history-search">
            <span className="sr-only">Search system history</span>
            <input
              type="search"
              value={queryInput}
              maxLength={200}
              placeholder="Search event, part, Project, Reservation, actor, reason, or recorded data"
              onChange={(event: ChangeEvent<HTMLInputElement>) =>
                setQueryInput(event.currentTarget.value)
              }
            />
          </label>
        </div>

        <div className="history-filter-grid">
          <label>
            <span>Entity</span>
            <select
              value={entityFilter}
              onChange={(event) => {
                setEntityFilter(event.currentTarget.value);
                resetPage();
              }}
            >
              <option value="">All entities</option>
              {filterOptions.entity_types.map((option) => (
                <option value={option.value} key={option.value}>
                  {humanise(option.value)} ({option.count})
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Event</span>
            <select
              value={eventFilter}
              onChange={(event) => {
                setEventFilter(event.currentTarget.value);
                resetPage();
              }}
            >
              <option value="">All event types</option>
              {filterOptions.event_types.map((option) => (
                <option value={option.value} key={option.value}>
                  {EVENT_TITLES[option.value] ??
                    humanise(option.value)}{" "}
                  ({option.count})
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Actor type</span>
            <select
              value={actorTypeFilter}
              onChange={(event) => {
                setActorTypeFilter(event.currentTarget.value);
                resetPage();
              }}
            >
              <option value="">All actor types</option>
              {filterOptions.actor_types.map((option) => (
                <option value={option.value} key={option.value}>
                  {humanise(option.value)} ({option.count})
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>User</span>
            <select
              value={actorUserFilter}
              onChange={(event) => {
                setActorUserFilter(event.currentTarget.value);
                resetPage();
              }}
            >
              <option value="">All users</option>
              {filterOptions.actors.map((option) => (
                <option
                  value={option.user_id}
                  key={option.user_id}
                >
                  {option.display_name} ({option.count})
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Movement</span>
            <select
              value={movementFilter}
              disabled={kindFilter === "audit"}
              onChange={(event) => {
                setMovementFilter(event.currentTarget.value);
                resetPage();
              }}
            >
              <option value="">All movement types</option>
              {filterOptions.movement_types.map((option) => (
                <option value={option.value} key={option.value}>
                  {humanise(option.value)} ({option.count})
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>From</span>
            <input
              type="datetime-local"
              value={fromDate}
              onChange={(event) => {
                setFromDate(event.currentTarget.value);
                resetPage();
              }}
            />
          </label>

          <label>
            <span>To</span>
            <input
              type="datetime-local"
              value={toDate}
              onChange={(event) => {
                setToDate(event.currentTarget.value);
                resetPage();
              }}
            />
          </label>

          <div className="history-filter-actions">
            <span>
              {activeFilterCount === 0
                ? "Showing the full chronological register"
                : `${activeFilterCount} filter${
                    activeFilterCount === 1 ? "" : "s"
                  } applied`}
            </span>
            <button
              className="history-button"
              type="button"
              disabled={activeFilterCount === 0}
              onClick={clearFilters}
            >
              Clear filters
            </button>
          </div>
        </div>

        {optionsError ? (
          <div className="history-inline-error" role="alert">
            Filter counts could not be loaded: {optionsError}
          </div>
        ) : null}
        {dateRangeError ? (
          <div className="history-inline-error" role="alert">
            {dateRangeError}
          </div>
        ) : null}
      </section>

      {listError && !dateRangeError ? (
        <div className="history-notice is-error" role="alert">
          <strong>History could not be loaded.</strong>
          <span>{listError}</span>
        </div>
      ) : null}

      <div className="history-workspace">
        <section className="history-list-panel" aria-label="History register">
          <div className="history-list-heading">
            <div>
              <strong>Chronological register</strong>
              <span>
                Page {pageNumber} of {pageCount}
              </span>
            </div>
            <span>{collection.entries.length} shown</span>
          </div>

          <div className="history-list-columns" aria-hidden="true">
            <span>Event</span>
            <span>Kind</span>
            <span>Entity</span>
            <span>Actor</span>
            <span>Occurred</span>
          </div>

          <div className="history-list" aria-live="polite">
            {listLoading ? (
              <div className="history-list-state">
                Loading system history…
              </div>
            ) : collection.entries.length === 0 ? (
              <div className="history-list-state">
                <strong>No matching history</strong>
                <span>
                  Clear one or more filters, widen the date range, or
                  search for a different term.
                </span>
              </div>
            ) : (
              collection.entries.map((entry) => (
                <button
                  className={
                    selectedKey === entry.key
                      ? "history-row is-selected"
                      : "history-row"
                  }
                  key={entry.key}
                  type="button"
                  aria-pressed={selectedKey === entry.key}
                  onClick={() => setSelectedKey(entry.key)}
                >
                  <span className="history-row-main">
                    <strong>{eventTitle(entry)}</strong>
                    <small>
                      {entry.summary ?? entry.event_type}
                    </small>
                  </span>
                  <span
                    className={`history-kind is-${entry.kind}`}
                  >
                    {kindLabel(entry.kind)}
                  </span>
                  <span className="history-row-entity">
                    {entityLabel(entry)}
                  </span>
                  <span className="history-row-actor">
                    {actorLabel(entry)}
                  </span>
                  <time
                    className="history-row-date"
                    dateTime={entry.occurred_at}
                  >
                    {formatCompactDate(entry.occurred_at)}
                  </time>
                </button>
              ))
            )}
          </div>

          <footer className="history-pagination">
            <button
              className="history-button"
              type="button"
              disabled={pageOffset === 0 || listLoading}
              onClick={() =>
                setPageOffset((value) =>
                  Math.max(0, value - PAGE_SIZE)
                )
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
              className="history-button"
              type="button"
              disabled={
                pageOffset + PAGE_SIZE >= collection.total ||
                listLoading
              }
              onClick={() =>
                setPageOffset((value) => value + PAGE_SIZE)
              }
            >
              Next
            </button>
          </footer>
        </section>

        <aside className="history-detail-panel">
          {!selectedEntry ? (
            <div className="history-detail-empty">
              <div>
                <span>History detail</span>
                <h2>No event selected</h2>
                <p>
                  Choose a record to inspect its actor, entity,
                  relationships, inventory snapshots, and structured
                  before-and-after data.
                </p>
              </div>
              <dl>
                <div>
                  <dt>Audit</dt>
                  <dd>Lifecycle and configuration records</dd>
                </div>
                <div>
                  <dt>Stock</dt>
                  <dd>Physical, reserved, and available changes</dd>
                </div>
                <div>
                  <dt>Context</dt>
                  <dd>Part, Project, and Reservation relationships</dd>
                </div>
                <div>
                  <dt>Evidence</dt>
                  <dd>Before, after, metadata, reason, and notes</dd>
                </div>
              </dl>
            </div>
          ) : (
            <>
              <header className="history-detail-header">
                <div>
                  <span
                    className={`history-kind is-${selectedEntry.kind}`}
                  >
                    {kindLabel(selectedEntry.kind)}
                  </span>
                  <h2>{eventTitle(selectedEntry)}</h2>
                  <p>
                    {selectedEntry.summary ??
                      "No summary was recorded for this event."}
                  </p>
                </div>
                <button
                  className="history-button history-close-mobile"
                  type="button"
                  onClick={() => setSelectedKey(null)}
                >
                  Close
                </button>
              </header>

              <dl className="history-facts">
                <div>
                  <dt>Occurred</dt>
                  <dd>{formatDate(selectedEntry.occurred_at)}</dd>
                </div>
                <div>
                  <dt>Actor</dt>
                  <dd>{actorLabel(selectedEntry)}</dd>
                </div>
                <div>
                  <dt>Entity</dt>
                  <dd>{entityLabel(selectedEntry)}</dd>
                </div>
                <div>
                  <dt>Event code</dt>
                  <dd>{selectedEntry.event_type}</dd>
                </div>
                <div>
                  <dt>Source</dt>
                  <dd>
                    {humanise(
                      selectedEntry.source ??
                        selectedEntry.actor_type
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Record key</dt>
                  <dd>{selectedEntry.key}</dd>
                </div>
              </dl>

              {selectedEntry.part_id !== null ||
              selectedEntry.reservation_id !== null ||
              selectedEntry.project_id !== null ? (
                <section className="history-detail-section">
                  <div className="history-section-heading">
                    <strong>Related records</strong>
                    <span>Resolved at request time</span>
                  </div>
                  <dl className="history-related">
                    {selectedEntry.part_id !== null ? (
                      <div>
                        <dt>Part</dt>
                        <dd>
                          {selectedEntry.part_number ??
                            selectedEntry.part_name ??
                            `Part #${selectedEntry.part_id}`}
                        </dd>
                        {selectedEntry.part_number &&
                        selectedEntry.part_name ? (
                          <small>{selectedEntry.part_name}</small>
                        ) : null}
                      </div>
                    ) : null}
                    {selectedEntry.reservation_id !== null ? (
                      <div>
                        <dt>Reservation</dt>
                        <dd>
                          {selectedEntry.reservation_label ??
                            `Reservation #${selectedEntry.reservation_id}`}
                        </dd>
                        <small>
                          #{selectedEntry.reservation_id}
                        </small>
                      </div>
                    ) : null}
                    {selectedEntry.project_id !== null ? (
                      <div>
                        <dt>Project</dt>
                        <dd>
                          {selectedEntry.project_label ??
                            `Project #${selectedEntry.project_id}`}
                        </dd>
                        <small>#{selectedEntry.project_id}</small>
                      </div>
                    ) : null}
                  </dl>
                </section>
              ) : null}

              {selectedEntry.kind === "stock_movement" ? (
                <section className="history-detail-section">
                  <div className="history-section-heading">
                    <strong>Inventory impact</strong>
                    <span>
                      {selectedEntry.quantity !== null
                        ? `${selectedEntry.quantity} unit${
                            selectedEntry.quantity === 1 ? "" : "s"
                          }`
                        : humanise(selectedEntry.movement_type)}
                    </span>
                  </div>

                  <div className="history-stock-delta">
                    <span>Movement delta</span>
                    <strong
                      className={
                        stockDelta(selectedEntry) > 0
                          ? "is-positive"
                          : stockDelta(selectedEntry) < 0
                            ? "is-negative"
                            : ""
                      }
                    >
                      {signedNumber(stockDelta(selectedEntry))}
                    </strong>
                  </div>

                  <dl className="history-stock-snapshots">
                    <div>
                      <dt>Physical</dt>
                      <dd>
                        {selectedEntry.quantity_before ?? "—"}
                        {" → "}
                        {selectedEntry.quantity_after ?? "—"}
                      </dd>
                    </div>
                    <div>
                      <dt>Reserved</dt>
                      <dd>
                        {selectedEntry.reserved_quantity_before ?? "—"}
                        {" → "}
                        {selectedEntry.reserved_quantity_after ?? "—"}
                      </dd>
                    </div>
                    <div>
                      <dt>Available</dt>
                      <dd>
                        {selectedEntry.available_quantity_before ?? "—"}
                        {" → "}
                        {selectedEntry.available_quantity_after ?? "—"}
                      </dd>
                    </div>
                  </dl>

                  {selectedEntry.reason || selectedEntry.note ? (
                    <div className="history-recorded-copy">
                      {selectedEntry.reason ? (
                        <div>
                          <strong>Reason</strong>
                          <p>{selectedEntry.reason}</p>
                        </div>
                      ) : null}
                      {selectedEntry.note ? (
                        <div>
                          <strong>Note</strong>
                          <p>{selectedEntry.note}</p>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </section>
              ) : (
                <section className="history-detail-section">
                  <div className="history-section-heading">
                    <strong>Recorded change</strong>
                    <span>Structured audit snapshots</span>
                  </div>
                  <div className="history-json-grid">
                    <article>
                      <header>Before</header>
                      <pre>{jsonText(selectedEntry.before_json)}</pre>
                    </article>
                    <article>
                      <header>After</header>
                      <pre>{jsonText(selectedEntry.after_json)}</pre>
                    </article>
                  </div>
                </section>
              )}

              {hasJson(selectedEntry.metadata_json) ? (
                <details className="history-metadata">
                  <summary>Audit metadata</summary>
                  <pre>{jsonText(selectedEntry.metadata_json)}</pre>
                </details>
              ) : null}
            </>
          )}
        </aside>
      </div>
    </section>
  );
}
