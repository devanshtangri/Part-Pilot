import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

const navItems = [
  { label: "Dashboard", path: "/" },
  { label: "Inventory", path: "/inventory" },
  { label: "Projects", path: "/projects" },
  { label: "Reservations", path: "/reservations" },
  { label: "History", path: "/history" },
  { label: "Part Manager", path: "/part-manager" },
  { label: "Settings", path: "/settings" }
];

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand ${compact ? "brand-compact" : ""}`}>
      <div className="brand-mark" aria-hidden="true">
        P
      </div>
      <div className="brand-copy">
        <strong>Part Pilot</strong>
        <span>Inventory OS</span>
      </div>
    </div>
  );
}

export function AppLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [isDrawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!isDrawerOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setDrawerOpen(false);
      }
    }

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isDrawerOpen]);

  function handleLogout() {
    setDrawerOpen(false);
    logout();
  }

  return (
    <div className={`app-shell ${isDrawerOpen ? "drawer-open" : ""}`}>
      <header className="mobile-topbar">
        <button
          className="mobile-menu-button"
          type="button"
          aria-label="Open navigation"
          aria-controls="primary-navigation"
          aria-expanded={isDrawerOpen}
          onClick={() => setDrawerOpen(true)}
        >
          <span aria-hidden="true" />
          <span aria-hidden="true" />
          <span aria-hidden="true" />
        </button>

        <Brand compact />
      </header>

      <button
        className={`drawer-backdrop ${isDrawerOpen ? "is-visible" : ""}`}
        type="button"
        aria-label="Close navigation"
        tabIndex={isDrawerOpen ? 0 : -1}
        onClick={() => setDrawerOpen(false)}
      />

      <aside
        id="primary-navigation"
        className={`sidebar ${isDrawerOpen ? "is-open" : ""}`}
      >
        <div className="sidebar-header">
          <Brand />
          <button
            className="sidebar-close"
            type="button"
            aria-label="Close navigation"
            onClick={() => setDrawerOpen(false)}
          >
            <span aria-hidden="true" />
            <span aria-hidden="true" />
          </button>
        </div>

        <nav className="nav-list" aria-label="Primary navigation">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `nav-item ${isActive ? "active" : ""}`
              }
              end={item.path === "/"}
              onClick={() => setDrawerOpen(false)}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-account">
          <div className="sidebar-account-details">
            <strong className="sidebar-account-name">
              {user?.display_name ?? "Local user"}
            </strong>
            <span className="sidebar-account-username">
              @{user?.username ?? "user"}
            </span>
          </div>

          <button
            className="sidebar-logout"
            type="button"
            onClick={handleLogout}
          >
            Log out
          </button>
        </div>
      </aside>

      <main className="main-panel">
        <Outlet />
      </main>
    </div>
  );
}
