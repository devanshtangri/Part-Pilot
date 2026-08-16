import { useEffect, useRef } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./AppLayout";
import { AppearanceProvider } from "../appearance/AppearanceContext";
import { AuthProvider, useAuth } from "../auth/AuthContext";
import {
  LiveSyncProvider,
  useLiveSyncRevision
} from "../live/LiveSyncContext";
import {
  getCurrencySettings,
  getTimezoneSettings
} from "../services/settingsClient";
import { AuthScreen } from "../pages/AuthScreen";
import { Dashboard } from "../pages/Dashboard";
import { Inventory } from "../pages/Inventory";
import { History } from "../pages/History";
import { PartManager } from "../pages/PartManager";
import { Projects } from "../pages/Projects";
import { SetupPreferencesScreen } from "../pages/SetupPreferencesScreen";
import { Settings } from "../pages/Settings";
import { Reservations } from "../pages/Reservations";

const SETTINGS_ACCOUNT_LIVE_SYNC_MARKER =
  "PARTPILOT:SETTINGS_ACCOUNT_PREFERENCES_LIVE_SYNC:V705";

function SettingsAccountLiveSyncBridge() {
  const {
    token,
    user,
    refreshUser,
    syncDefaultCurrency,
    syncTimezone
  } = useAuth();
  const accountLiveRevision = useLiveSyncRevision("account");
  const preferencesLiveRevision = useLiveSyncRevision("preferences");
  const lastAccountRevision = useRef(accountLiveRevision);
  const lastPreferencesRevision = useRef(preferencesLiveRevision);
  const preferenceRequestId = useRef(0);

  useEffect(() => {
    document.documentElement.dataset.partpilotSettingsAccountLiveSync =
      SETTINGS_ACCOUNT_LIVE_SYNC_MARKER;
    return () => {
      delete document.documentElement.dataset.partpilotSettingsAccountLiveSync;
    };
  }, []);

  useEffect(() => {
    if (accountLiveRevision === lastAccountRevision.current) {
      return;
    }
    lastAccountRevision.current = accountLiveRevision;
    if (!user) {
      return;
    }
    void refreshUser().catch(() => {
      // The normal auth flow remains authoritative for session failure.
    });
  }, [accountLiveRevision, refreshUser, user]);

  useEffect(() => {
    if (preferencesLiveRevision === lastPreferencesRevision.current) {
      return;
    }
    lastPreferencesRevision.current = preferencesLiveRevision;
    const requestId = preferenceRequestId.current + 1;
    preferenceRequestId.current = requestId;
    if (!token || !user) {
      return;
    }

    void Promise.all([
      getCurrencySettings(token),
      getTimezoneSettings(token)
    ])
      .then(([currency, timezone]) => {
        if (preferenceRequestId.current !== requestId) {
          return;
        }
        syncDefaultCurrency(currency.currency);
        syncTimezone(timezone.timezone);
      })
      .catch(() => {
        // Existing Settings retry/error surfaces remain authoritative.
      });
  }, [
    preferencesLiveRevision,
    syncDefaultCurrency,
    syncTimezone,
    token,
    user
  ]);

  return null;
}


function AppRoutes() {
  const {
    user,
    accountExists,
    setupComplete,
    isBooting
  } = useAuth();

  if (isBooting) {
    return (
      <main className="auth-page">
        <div className="auth-window">
          <section className="auth-form-panel">
            <div className="brand-mark">P</div>
            <p className="eyebrow">Starting Part Pilot</p>
            <h2>Checking local session...</h2>
          </section>
        </div>
      </main>
    );
  }

  if (accountExists === false || !user) {
    return <AuthScreen />;
  }

  if (setupComplete === false) {
    return <SetupPreferencesScreen />;
  }

  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/inventory" element={<Inventory />} />
        <Route path="/projects" element={<Projects />} />
        <Route path="/reservations" element={<Reservations />} />
        <Route path="/history" element={<History />} />
        <Route path="/part-manager" element={<PartManager />} />
        <Route path="/settings" element={<Settings />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export function App() {
  return (
    <AuthProvider>
      <LiveSyncProvider>
        <SettingsAccountLiveSyncBridge />
        <AppearanceProvider>
          <AppRoutes />
        </AppearanceProvider>
      </LiveSyncProvider>
    </AuthProvider>
  );
}
