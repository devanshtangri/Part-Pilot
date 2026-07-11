import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./AppLayout";
import { AuthProvider, useAuth } from "../auth/AuthContext";
import { AuthScreen } from "../pages/AuthScreen";
import { Dashboard } from "../pages/Dashboard";
import { Inventory } from "../pages/Inventory";
import { PlaceholderPage } from "../pages/PlaceholderPage";

function AppRoutes() {
  const { user, setupComplete, isBooting } = useAuth();

  if (isBooting) {
    return (
      <main className="auth-shell auth-shell-loading">
        <section className="auth-form-card">
          <div className="brand-mark">P</div>
          <p className="eyebrow">Starting Part Pilot</p>
          <h2>Checking local session...</h2>
        </section>
      </main>
    );
  }

  if (!user || setupComplete === false) {
    return <AuthScreen />;
  }

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

export function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
