import {
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { useLiveSyncRevision } from "../live/LiveSyncContext";
import { getHealth } from "../services/apiClient";
import {
  getLowStockParts,
  getParts
} from "../services/partsClient";
import { getSearchSettings } from "../services/settingsClient";
import type { HealthResponse } from "../types/health";
import type {
  LowStockSummary,
  Part,
  PartCollection
} from "../types/parts";
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

function stockStatusLabel(part: Part): string {
  return part.available_quantity <= 0 ? "Out of stock" : "Low stock";
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
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const { token } = useAuth();
  const inventoryLiveRevision = useLiveSyncRevision("inventory");
  const lastInventoryLiveRevision = useRef(inventoryLiveRevision);
  const [lowStock, setLowStock] = useState<LowStockSummary | null>(null);
  const [lowStockLoading, setLowStockLoading] = useState(true);
  const [lowStockError, setLowStockError] = useState<string | null>(null);
  const [lowStockRefreshSequence, setLowStockRefreshSequence] = useState(0);
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

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => {
        setHealth(null);
      });
  }, []);

  // PARTPILOT:DASHBOARD_INVENTORY_LIVE_SYNC:V703
  useEffect(() => {
    if (inventoryLiveRevision === lastInventoryLiveRevision.current) {
      return;
    }
    lastInventoryLiveRevision.current = inventoryLiveRevision;
    setLowStockRefreshSequence((current) => current + 1);
    setSearchRefreshSequence((current) => current + 1);
  }, [inventoryLiveRevision]);

  useEffect(() => {
    if (!token) {
      setLowStock(null);
      setLowStockError("Your session is unavailable. Sign in again.");
      setLowStockLoading(false);
      return;
    }

    let cancelled = false;

    setLowStockLoading(true);
    setLowStockError(null);

    getLowStockParts(token, { limit: 8 })
      .then((result) => {
        if (!cancelled) {
          setLowStock(result);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setLowStock(null);
          setLowStockError(
            caught instanceof Error
              ? caught.message
              : "Unable to load low-stock inventory"
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLowStockLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token, lowStockRefreshSequence]);

  function refreshLowStock(): void {
    setLowStockRefreshSequence((current) => current + 1);
  }

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
  }, [token]);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;

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
      document.body.style.overflow = "hidden";
      window.setTimeout(() => {
        searchInputRef.current?.focus();
      }, 0);
    }

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleSearchKeyboard);
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
      setSearchTerm("");
      setSearchResults(null);
      setSelectedSearchPart(null);
      setSearchError(null);
      setSearchLoading(false);
      return;
    }

    if (!token) {
      setSearchTerm(normalized);
      setSearchResults(null);
      setSelectedSearchPart(null);
      setSearchError("Your session is unavailable. Sign in again.");
      setSearchLoading(false);
      return;
    }

    setSearchTerm(normalized);
    setSearchError(null);
    setSearchLoading(true);

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
          setSearchResults(null);
          setSelectedSearchPart(null);
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

      <div className="card-grid dashboard-summary-grid">
        <article className="card">
          <span className="card-label">Backend</span>
          <strong>{health?.status === "ok" ? "Online" : "Checking..."}</strong>
          <p>{health ? `${health.app} / ${health.environment}` : "Waiting for API response."}</p>
        </article>

        <article className="card dashboard-stock-count-card">
          <span className="card-label">Stock alerts</span>
          <strong>{lowStockLoading ? "..." : lowStock?.total ?? 0}</strong>
          <p>
            {lowStockLoading
              ? "Checking inventory thresholds."
              : lowStockError
                ? "Current alert totals are unavailable."
                : `${lowStock?.low_stock_count ?? 0} low · ${
                    lowStock?.out_of_stock_count ?? 0
                  } out`}
          </p>
        </article>

        <article className="card dashboard-action-card">
          <span className="card-label">Inventory</span>
          <strong>Manage parts</strong>
          <p>Review stock, locations, quantities, and part details.</p>
          <Link to="/part-manager">Open Part Manager</Link>
        </article>
      </div>

      <article
        className="card dashboard-low-stock-card"
        data-dashboard-low-stock-version="dashboard-low-stock-v186"
        aria-labelledby="dashboard-low-stock-title"
        aria-busy={lowStockLoading}
      >
        <header className="dashboard-low-stock-header">
          <div>
            <p className="eyebrow">Attention required</p>
            <h2 id="dashboard-low-stock-title">Low-stock inventory</h2>
            <p>
              Alerts use available stock after reservations and each part's
              configured threshold.
            </p>
          </div>

          <div className="dashboard-low-stock-actions">
            <span>
              {lowStockLoading
                ? "Loading..."
                : `${lowStock?.total ?? 0} alert${
                    (lowStock?.total ?? 0) === 1 ? "" : "s"
                  }`}
            </span>
            <button
              type="button"
              onClick={refreshLowStock}
              disabled={lowStockLoading || !token}
            >
              {lowStockLoading ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </header>

        {lowStockLoading ? (
          <div
            className="dashboard-low-stock-state"
            role="status"
            aria-live="polite"
          >
            Loading low-stock inventory...
          </div>
        ) : null}

        {!lowStockLoading && lowStockError ? (
          <div className="dashboard-low-stock-state is-error" role="alert">
            <strong>Unable to load stock alerts</strong>
            <p>{lowStockError}</p>
            <button type="button" onClick={refreshLowStock}>
              Try again
            </button>
          </div>
        ) : null}

        {!lowStockLoading
          && !lowStockError
          && lowStock
          && lowStock.total === 0 ? (
            <div className="dashboard-low-stock-state is-empty">
              <strong>Stock levels look healthy</strong>
              <p>
                No enabled low-stock threshold is currently being reached.
              </p>
            </div>
          ) : null}

        {!lowStockLoading
          && !lowStockError
          && lowStock
          && lowStock.parts.length > 0 ? (
            <div className="dashboard-low-stock-list">
              {lowStock.parts.map((part) => (
                <div
                  className={
                    part.available_quantity <= 0
                      ? "dashboard-low-stock-row is-out"
                      : "dashboard-low-stock-row is-low"
                  }
                  key={part.id}
                >
                  <div className="dashboard-low-stock-identity">
                    <strong>{partDisplayName(part)}</strong>
                    <span>{partContext(part) || "Inventory part"}</span>
                  </div>

                  <div className="dashboard-low-stock-quantity">
                    <strong>{part.available_quantity}</strong>
                    <span>available</span>
                  </div>

                  <div className="dashboard-low-stock-threshold">
                    <span>Threshold</span>
                    <strong>{part.low_stock_threshold ?? "—"}</strong>
                  </div>

                  <span className="dashboard-low-stock-badge">
                    {stockStatusLabel(part)}
                  </span>
                </div>
              ))}
            </div>
          ) : null}

        {!lowStockLoading
          && !lowStockError
          && lowStock
          && lowStock.total > lowStock.parts.length ? (
            <footer className="dashboard-low-stock-footer">
              <span>
                Showing {lowStock.parts.length} of {lowStock.total} alerts.
              </span>
              <Link to="/part-manager">Review all inventory</Link>
            </footer>
          ) : null}
      </article>
    </section>
  );
}
