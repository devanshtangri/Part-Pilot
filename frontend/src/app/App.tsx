import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./AppLayout";
import { Dashboard } from "../pages/Dashboard";
import { Inventory } from "../pages/Inventory";
import { PlaceholderPage } from "../pages/PlaceholderPage";

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/inventory" element={<Inventory />} />
        <Route path="/projects" element={<PlaceholderPage title="Projects" />} />
        <Route path="/reservations" element={<PlaceholderPage title="Reservations" />} />
        <Route path="/history" element={<PlaceholderPage title="History" />} />
        <Route path="/part-manager" element={<PlaceholderPage title="Part Manager" />} />
        <Route path="/settings" element={<PlaceholderPage title="Settings" />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
