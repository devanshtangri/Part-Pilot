import {
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { useLiveSyncRevision } from "../live/LiveSyncContext";
import { getParts } from "../services/partsClient";
import { getSearchSettings } from "../services/settingsClient";
import type { Part, PartCollection } from "../types/parts";
import "./Dashboard.css";

function partDisplayName(part: Part): string {
  return part.name || part.part_number || `Part ${part.id}`;
}

function partContext(part: Part): string {
  return [
    part.part_type_name,
    part.manufacturer_name,
    part.location_name
  ]
    .filter(Boolean)
    .join(" · ");
}


// PATCH 217: Dashboard universal-search presentation helpers
function universalSearchStockLabel(part: Part): string {
  if (part.available_quantity <= 0) {
    return "Out of stock";
  }
  if (part.is_low_stock) {
    return "Low stock";
  }
  return "In stock";
}

function universalSearchStockClass(part: Part): string {
  if (part.available_quantity <= 0) {
    return "is-out";
  }
  if (part.is_low_stock) {
    return "is-low";
  }
  return "is-in";
}

function universalSearchFieldValue(
  field: Part["field_values"][number]
): string | null {
  if (field.value_bool !== null) {
    return field.value_bool ? "Yes" : "No";
  }
  if (field.value_number !== null) {
    return `${field.value_number.replace(/(?:\.0+|(?<=\.[0-9]*?)0+)$/, "")}${
      field.unit ? ` ${field.unit}` : ""
    }`;
  }
  return field.value_text;
}

export function Dashboard() {
  const { token } = useAuth();
  const inventoryLiveRevision = useLiveSyncRevision("inventory");
  const preferencesLiveRevision = useLiveSyncRevision("preferences");
  const lastInventoryLiveRevision = useRef(inventoryLiveRevision);
  const searchLoadedKeyRef = useRef<string | null>(null);
  const [searchRefreshSequence, setSearchRefreshSequence] = useState(0);
  // PATCH 217: Dashboard universal-search state
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchInput, setSearchInput] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] =
    useState<PartCollection | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchShowOutOfStock, setSearchShowOutOfStock] = useState(true);
  const [searchSettingsError, setSearchSettingsError] =
    useState<string | null>(null);
  const [selectedSearchPart, setSelectedSearchPart] =
    useState<Part | null>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  // PATCH 219: invalidate stale live-search responses
  const searchRequestSequenceRef = useRef(0);

  // PARTPILOT:DASHBOARD_INVENTORY_LIVE_SYNC:V703
  useEffect(() => {
    if (inventoryLiveRevision === lastInventoryLiveRevision.current) {
      return;
    }
    lastInventoryLiveRevision.current = inventoryLiveRevision;
    setSearchRefreshSequence((current) => current + 1);
  }, [inventoryLiveRevision]);


  useEffect(() => {
    if (!token) {
      setSearchShowOutOfStock(true);
      setSearchSettingsError(
        "Search preferences are unavailable without an active session."
      );
      return;
    }

    let cancelled = false;
    setSearchSettingsError(null);
    getSearchSettings(token)
      .then((settings) => {
        if (!cancelled) {
          setSearchShowOutOfStock(settings.show_out_of_stock_section);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setSearchShowOutOfStock(true);
          setSearchSettingsError(
            caught instanceof Error
              ? caught.message
              : "Unable to load search preferences"
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [preferencesLiveRevision, token]);

  useEffect(() => {
    function handleSearchKeyboard(event: KeyboardEvent): void {
      const target = event.target as HTMLElement | null;
      const isTypingTarget = Boolean(
        target
        && (
          target.tagName === "INPUT"
          || target.tagName === "TEXTAREA"
          || target.tagName === "SELECT"
          || target.isContentEditable
        )
      );

      if (
        event.key === "/"
        && !searchOpen
        && !isTypingTarget
        && !event.metaKey
        && !event.ctrlKey
        && !event.altKey
      ) {
        event.preventDefault();
        setSearchOpen(true);
      }

      if (event.key === "Escape" && searchOpen) {
        event.preventDefault();
        setSearchOpen(false);
      }
    }

    window.addEventListener("keydown", handleSearchKeyboard);

    if (searchOpen) {
      window.setTimeout(() => {
        searchInputRef.current?.focus();
      }, 0);
    }

    return () => {
      window.removeEventListener("keydown", handleSearchKeyboard);
    };
  }, [searchOpen]);

  // PARTPILOT:DASHBOARD_DIALOG_SCROLL_LOCK:V729
  useEffect(() => {
    if (!searchOpen) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [searchOpen]);

  const availableSearchResults = useMemo(
    () =>
      (searchResults?.parts ?? []).filter(
        (part) => part.available_quantity > 0
      ),
    [searchResults]
  );
  const allOutOfStockSearchResults = useMemo(
    () =>
      (searchResults?.parts ?? []).filter(
        (part) => part.available_quantity <= 0
      ),
    [searchResults]
  );
  const visibleOutOfStockSearchResults = searchShowOutOfStock
    ? allOutOfStockSearchResults
    : [];

  function openSearchDialog(): void {
    setSearchOpen(true);
  }

  function closeSearchDialog(): void {
    setSearchOpen(false);
    setSearchError(null);
  }

  // PATCH 219: race-safe debounced Dashboard live search
  useEffect(() => {
    const requestSequence = ++searchRequestSequenceRef.current;

    if (!searchOpen) {
      setSearchLoading(false);
      return;
    }

    const normalized = searchInput.trim().replace(/\s+/g, " ");
    if (!normalized) {
      searchLoadedKeyRef.current = null;
      setSearchTerm("");
      setSearchResults(null);
      setSelectedSearchPart(null);
      setSearchError(null);
      setSearchLoading(false);
      return;
    }

    if (!token) {
      searchLoadedKeyRef.current = null;
      setSearchTerm(normalized);
      setSearchResults(null);
      setSelectedSearchPart(null);
      setSearchError("Your session is unavailable. Sign in again.");
      setSearchLoading(false);
      return;
    }

    const loadKey = `${token}:${normalized}`;
    const hasCachedSearch = searchLoadedKeyRef.current === loadKey;
    setSearchTerm(normalized);
    setSearchError(null);
    setSearchLoading(!hasCachedSearch);

    const timeoutId = window.setTimeout(() => {
      getParts(token, {
        search: normalized,
        limit: 60,
        offset: 0
      })
        .then((result) => {
          if (requestSequence !== searchRequestSequenceRef.current) {
            return;
          }
          searchLoadedKeyRef.current = loadKey;
          setSearchResults(result);
          setSelectedSearchPart((current) =>
            result.parts.find((part) => part.id === current?.id)
            ?? result.parts.find((part) => part.available_quantity > 0)
            ?? result.parts[0]
            ?? null
          );
        })
        .catch((caught) => {
          if (requestSequence !== searchRequestSequenceRef.current) {
            return;
          }
          if (!hasCachedSearch) {
            setSearchResults(null);
            setSelectedSearchPart(null);
          }
          setSearchError(
            caught instanceof Error
              ? caught.message
              : "Unable to search inventory"
          );
        })
        .finally(() => {
          if (requestSequence === searchRequestSequenceRef.current) {
            setSearchLoading(false);
          }
        });
    }, 280);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [searchInput, searchOpen, searchRefreshSequence, token]);

  return (
    <section
      className="page-stack dashboard-page"
      data-partpilot-live-sync="PARTPILOT:DASHBOARD_INVENTORY_LIVE_SYNC:V703"
      data-partpilot-background-refresh="PARTPILOT:STABLE_BACKGROUND_REFRESH:V718"
    >
      <div className="page-header">
        <p className="eyebrow">Inventory overview</p>
        <h1>Dashboard</h1>
        <p>
          Review system status and parts that need attention without leaving
          the dashboard.
        </p>
      </div>

      <button
        className="search-card dashboard-search-launcher"
        type="button"
        onClick={openSearchDialog}
        aria-haspopup="dialog"
      >
        <span>
          <strong>Search your inventory</strong>
          <small>Parts, values, tags, locations, notes, and custom fields</small>
        </span>
        <kbd aria-label="Keyboard shortcut slash">/</kbd>
      </button>

      {searchOpen ? (
        <div
          className="dashboard-search-backdrop"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target) {
              closeSearchDialog();
            }
          }}
        >
          <section
            className="dashboard-search-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="dashboard-search-title"
            data-dashboard-universal-search-version="dashboard-universal-search-v217"
          >
            <header className="dashboard-search-dialog-header">
              <div>
                <p className="eyebrow">Universal inventory search</p>
                <h2 id="dashboard-search-title">Find any stored part</h2>
                <p>
                  Search identifiers, specifications, locations, tags, notes,
                  and custom field values.
                </p>
              </div>
              <button
                className="dashboard-search-close"
                type="button"
                onClick={closeSearchDialog}
                aria-label="Close universal search"
              >
                {/* PATCH 222: geometry-centred search close icon */}
                <svg
                  data-dashboard-search-close-icon=
                    "dashboard-search-close-icon-v222"
                  viewBox="0 0 16 16"
                  aria-hidden="true"
                  focusable="false"
                >
                  <path d="M4 4L12 12M12 4L4 12" />
                </svg>
              </button>
            </header>

            <div className="dashboard-search-form">
              <label htmlFor="dashboard-universal-search-input">
                Search inventory
              </label>
              <div className="dashboard-search-input-row">
                <input
                  id="dashboard-universal-search-input"
                  ref={searchInputRef}
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  placeholder="Try IRFZ44N, TO-220, Drawer 2, 56 V..."
                  maxLength={180}
                  autoComplete="off"
                  aria-describedby="dashboard-live-search-note"
                />
                <button
                  className="dashboard-search-clear"
                  type="button"
                  onClick={() => {
                    setSearchInput("");
                    searchInputRef.current?.focus();
                  }}
                  disabled={!searchInput}
                >
                  Clear
                </button>
              </div>
              <span
                id="dashboard-live-search-note"
                className="dashboard-search-live-note"
                aria-live="polite"
              >
                {searchLoading
                  ? "Searching as you type..."
                  : "Results update automatically after a brief pause."}
              </span>
            </div>

            {searchSettingsError ? (
              <div className="dashboard-search-preference-note" role="status">
                Out-of-stock preference could not be loaded. Results are
                temporarily shown using the safe default.
              </div>
            ) : null}

            <div
              className="dashboard-search-workspace"
              aria-busy={searchLoading}
            >
              <div className="dashboard-search-results">
                {!searchTerm && !searchLoading && !searchError ? (
                  <div className="dashboard-search-state is-initial">
                    <strong>Search the complete inventory record</strong>
                    <p>
                      Matching includes aliases, tags, notes, packages,
                      locations, manufacturers, and typed custom values.
                    </p>
                  </div>
                ) : null}

                {searchLoading ? (
                  <div
                    className="dashboard-search-state"
                    role="status"
                    aria-live="polite"
                  >
                    <strong>Searching inventory</strong>
                    <p>Checking all searchable part attributes...</p>
                  </div>
                ) : null}

                {!searchLoading && searchError ? (
                  <div
                    className="dashboard-search-state is-error"
                    role="alert"
                  >
                    <strong>Search could not be completed</strong>
                    <p>{searchError}</p>
                  </div>
                ) : null}

                {!searchLoading
                  && !searchError
                  && searchResults
                  && searchResults.total === 0 ? (
                    <div className="dashboard-search-state is-empty">
                      <strong>No matching parts</strong>
                      <p>
                        Nothing matched “{searchTerm}”. Try a shorter term,
                        another identifier, or a specification value.
                      </p>
                      <Link to="/inventory" onClick={closeSearchDialog}>
                        Browse Inventory
                      </Link>
                    </div>
                  ) : null}

                {!searchLoading
                  && !searchError
                  && searchResults
                  && searchResults.total > 0 ? (
                    <>
                      {/* PATCH 221: render only populated search sections */}
                      {availableSearchResults.length > 0 ? (
                        <section
                          className="dashboard-search-section"
                          data-dashboard-available-match-only=
                            "dashboard-populated-sections-v221"
                        >
                          <header>
                            {/* PATCH 223: concise separated stock sections */}
                            <h3>Available</h3>
                            <span>{availableSearchResults.length}</span>
                          </header>

                          <div className="dashboard-search-result-list">
                            {availableSearchResults.map((part) => (
                              <button
                                className={`dashboard-search-result ${universalSearchStockClass(
                                  part
                                )}${
                                  selectedSearchPart?.id === part.id
                                    ? " is-selected"
                                    : ""
                                }`}
                                type="button"
                                key={part.id}
                                onClick={() => setSelectedSearchPart(part)}
                              >
                                <span className="dashboard-search-result-main">
                                  <strong>{partDisplayName(part)}</strong>
                                  <small>
                                    {partContext(part) || "Inventory part"}
                                  </small>
                                </span>
                                <span className="dashboard-search-result-stock">
                                  <strong>{part.available_quantity}</strong>
                                  <small>available</small>
                                </span>
                                <span className="dashboard-search-result-badge">
                                  {universalSearchStockLabel(part)}
                                </span>
                              </button>
                            ))}
                          </div>
                        </section>
                      ) : null}

                      {/* PATCH 220: render restocking UI only for matching parts */}
                      {searchShowOutOfStock
                        && visibleOutOfStockSearchResults.length > 0 ? (
                        <section
                          className="dashboard-search-section is-out"
                          data-dashboard-restocking-match-only=
                            "dashboard-restocking-match-only-v220"
                        >
                          <header>
                            <h3>Out of stock</h3>
                            <span>{visibleOutOfStockSearchResults.length}</span>
                          </header>

                          <div className="dashboard-search-result-list">
                            {visibleOutOfStockSearchResults.map((part) => (
                              <button
                                className={`dashboard-search-result is-out${
                                  selectedSearchPart?.id === part.id
                                    ? " is-selected"
                                    : ""
                                }`}
                                type="button"
                                key={part.id}
                                onClick={() => setSelectedSearchPart(part)}
                              >
                                <span className="dashboard-search-result-main">
                                  <strong>{partDisplayName(part)}</strong>
                                  <small>
                                    {partContext(part) || "Inventory part"}
                                  </small>
                                </span>
                                <span className="dashboard-search-result-stock">
                                  <strong>0</strong>
                                  <small>available</small>
                                </span>
                                <span className="dashboard-search-result-badge">
                                  Out of stock
                                </span>
                              </button>
                            ))}
                          </div>
                        </section>
                      ) : !searchShowOutOfStock
                        && allOutOfStockSearchResults.length > 0 ? (
                        <div className="dashboard-search-hidden-state">
                          {allOutOfStockSearchResults.length} out-of-stock
                          match{allOutOfStockSearchResults.length === 1 ? "" : "es"}
                          {" "}hidden by your Search settings.
                          <Link to="/settings" onClick={closeSearchDialog}>
                            Change setting
                          </Link>
                        </div>
                      ) : null}

                      <footer className="dashboard-search-results-footer">
                        <span>
                          Showing {searchResults.parts.length} of{" "}
                          {searchResults.total} match
                          {searchResults.total === 1 ? "" : "es"}.
                        </span>
                        <Link to="/inventory" onClick={closeSearchDialog}>
                          Open Inventory
                        </Link>
                      </footer>
                    </>
                  ) : null}
              </div>

              <aside className="dashboard-search-details">
                {selectedSearchPart ? (
                  <>
                    <header>
                      <p className="eyebrow">Selected result</p>
                      <h3>{partDisplayName(selectedSearchPart)}</h3>
                      <p>
                        {partContext(selectedSearchPart) || "Inventory part"}
                      </p>
                    </header>

                    <dl className="dashboard-search-detail-grid">
                      <div>
                        <dt>Part number</dt>
                        <dd>{selectedSearchPart.part_number || "—"}</dd>
                      </div>
                      <div>
                        <dt>Package</dt>
                        <dd>{selectedSearchPart.package || "—"}</dd>
                      </div>
                      <div>
                        <dt>Available</dt>
                        <dd>{selectedSearchPart.available_quantity}</dd>
                      </div>
                      <div>
                        <dt>Reserved</dt>
                        <dd>{selectedSearchPart.reserved_quantity}</dd>
                      </div>
                      <div>
                        <dt>Total</dt>
                        <dd>{selectedSearchPart.total_quantity}</dd>
                      </div>
                      <div>
                        <dt>Location</dt>
                        <dd>{selectedSearchPart.location_name || "Unassigned"}</dd>
                      </div>
                    </dl>

                    {selectedSearchPart.description ? (
                      <div className="dashboard-search-detail-copy">
                        <span>Description</span>
                        <p>{selectedSearchPart.description}</p>
                      </div>
                    ) : null}

                    {selectedSearchPart.notes ? (
                      <div className="dashboard-search-detail-copy">
                        <span>Notes</span>
                        <p>{selectedSearchPart.notes}</p>
                      </div>
                    ) : null}

                    {selectedSearchPart.field_values.length > 0 ? (
                      <div className="dashboard-search-fields">
                        <span>Custom fields</span>
                        <dl>
                          {selectedSearchPart.field_values.map((field) => {
                            const value = universalSearchFieldValue(field);
                            return value ? (
                              <div key={field.id}>
                                <dt>{field.label}</dt>
                                <dd>{value}</dd>
                              </div>
                            ) : null;
                          })}
                        </dl>
                      </div>
                    ) : null}

                    <Link
                      className="dashboard-search-details-link"
                      to="/inventory"
                      onClick={closeSearchDialog}
                    >
                      Continue in Inventory
                    </Link>
                  </>
                ) : (
                  <div className="dashboard-search-state is-initial">
                    <strong>Select a result</strong>
                    <p>
                      Part identity, quantities, location, notes, and custom
                      fields will appear here.
                    </p>
                  </div>
                )}
              </aside>
            </div>
          </section>
        </div>
      ) : null}

      {/* PARTPILOT:DASHBOARD_STOCK_ALERT_REMOVED:V778 */}
      <section
        className="dashboard-quick-actions"
        aria-labelledby="dashboard-quick-actions-title"
        data-partpilot-stock-alert-removed="PARTPILOT:DASHBOARD_STOCK_ALERT_REMOVED:V778"
        data-dashboard-quick-actions="PARTPILOT:DASHBOARD_QUICK_ACTIONS:V730"
      >
        <header className="dashboard-quick-actions-header">
          <div>
            <p className="eyebrow">Quick actions</p>
            <h2 id="dashboard-quick-actions-title">Jump into your workspace</h2>
          </div>
          <p>Common inventory and planning tasks without extra navigation.</p>
        </header>

        <div className="dashboard-quick-action-grid">
          <Link className="card dashboard-quick-action" to="/inventory?add=1">
            <span>Inventory</span>
            <strong>Add part</strong>
            <small>Create a new stored inventory record.</small>
            <span className="dashboard-quick-action-arrow" aria-hidden="true">→</span>
          </Link>
          <Link className="card dashboard-quick-action" to="/projects?create=1">
            <span>Planning</span>
            <strong>New project</strong>
            <small>Start a Draft Project and plan required parts.</small>
            <span className="dashboard-quick-action-arrow" aria-hidden="true">→</span>
          </Link>
          <Link className="card dashboard-quick-action" to="/inventory">
            <span>Inventory</span>
            <strong>Stored parts</strong>
            <small>Search stock, quantities, locations, and details.</small>
            <span className="dashboard-quick-action-arrow" aria-hidden="true">→</span>
          </Link>
          <Link className="card dashboard-quick-action" to="/reservations">
            <span>Operations</span>
            <strong>Reservations</strong>
            <small>Review active holds and Project commitments.</small>
            <span className="dashboard-quick-action-arrow" aria-hidden="true">→</span>
          </Link>
          <Link className="card dashboard-quick-action" to="/part-manager">
            <span>Catalogue</span>
            <strong>Part Manager</strong>
            <small>Manage part types, templates, and custom fields.</small>
            <span className="dashboard-quick-action-arrow" aria-hidden="true">→</span>
          </Link>
          <Link className="card dashboard-quick-action" to="/history">
            <span>Audit</span>
            <strong>History</strong>
            <small>Inspect stock movements and system activity.</small>
            <span className="dashboard-quick-action-arrow" aria-hidden="true">→</span>
          </Link>
        </div>
      </section>

    </section>
  );
}
