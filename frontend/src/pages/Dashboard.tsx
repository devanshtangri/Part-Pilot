import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { getHealth } from "../services/apiClient";
import { getLowStockParts } from "../services/partsClient";
import type { HealthResponse } from "../types/health";
import type { LowStockSummary, Part } from "../types/parts";
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

export function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const { token } = useAuth();
  const [lowStock, setLowStock] = useState<LowStockSummary | null>(null);
  const [lowStockLoading, setLowStockLoading] = useState(true);
  const [lowStockError, setLowStockError] = useState<string | null>(null);
  const [lowStockRefreshSequence, setLowStockRefreshSequence] = useState(0);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => {
        setHealth(null);
      });
  }, []);

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

  return (
    <section className="page-stack dashboard-page">
      <div className="page-header">
        <p className="eyebrow">Inventory overview</p>
        <h1>Dashboard</h1>
        <p>
          Review system status and parts that need attention without leaving
          the dashboard.
        </p>
      </div>

      <div className="search-card">
        <span>Search parts, values, tags, locations...</span>
        <kbd>Coming with universal search</kbd>
      </div>

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
