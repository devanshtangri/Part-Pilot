import { useEffect, useState } from "react";

import { getHealth } from "../services/apiClient";
import type { HealthResponse } from "../types/health";

export function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => {
        setHealth(null);
      });
  }, []);

  return (
    <section className="page-stack">
      <div className="page-header">
        <p className="eyebrow">Phase 1 skeleton</p>
        <h1>Dashboard</h1>
        <p>
          The core shell is ready. Next we verify backend, frontend, and Docker
          before moving into database foundations.
        </p>
      </div>

      <div className="search-card">
        <span>Search parts, values, tags, locations...</span>
        <kbd>Coming in Phase 8</kbd>
      </div>

      <div className="card-grid">
        <article className="card">
          <span className="card-label">Backend</span>
          <strong>{health?.status === "ok" ? "Online" : "Checking..."}</strong>
          <p>{health ? `${health.app} / ${health.environment}` : "Waiting for API response."}</p>
        </article>

        <article className="card">
          <span className="card-label">Inventory</span>
          <strong>Not started</strong>
          <p>Parts and stock models begin after Phase 1 is verified.</p>
        </article>

        <article className="card">
          <span className="card-label">Next action</span>
          <strong>Finish Phase 1</strong>
          <p>Confirm Docker Compose, frontend load, and /health route.</p>
        </article>
      </div>
    </section>
  );
}
