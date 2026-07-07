import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { label: "Dashboard", path: "/" },
  { label: "Inventory", path: "/inventory" },
  { label: "Projects", path: "/projects" },
  { label: "Reservations", path: "/reservations" },
  { label: "History", path: "/history" },
  { label: "Part Manager", path: "/part-manager" },
  { label: "Settings", path: "/settings" }
];

export function AppLayout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">P</div>
          <div>
            <strong>Part Pilot</strong>
            <span>Inventory OS</span>
          </div>
        </div>

        <nav className="nav-list">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
              end={item.path === "/"}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="main-panel">
        <Outlet />
      </main>
    </div>
  );
}
