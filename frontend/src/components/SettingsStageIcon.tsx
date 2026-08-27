export type SettingsStageIconName =
  | "profile"
  | "password"
  | "sessions"
  | "users"
  | "theme"
  | "regional"
  | "inventory"
  | "reservation"
  | "api"
  | "server"
  | "capabilities"
  | "connections"
  | "advanced"
  | "backup"
  | "restore"
  | "reset";

interface SettingsStageIconProps {
  name: SettingsStageIconName;
}

const common = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true
};

// PARTPILOT:SETTINGS_SEMANTIC_STAGE_ICONS:V784
export function SettingsStageIcon({ name }: SettingsStageIconProps) {
  let icon = null;

  if (name === "profile") {
    icon = <><circle cx="12" cy="8" r="3.2" /><path d="M5.5 20c.7-4 3-6 6.5-6s5.8 2 6.5 6" /></>;
  } else if (name === "password") {
    icon = <><rect x="5" y="10" width="14" height="10" rx="2.3" /><path d="M8 10V7.5a4 4 0 0 1 8 0V10" /><circle cx="12" cy="15" r="1.2" /></>;
  } else if (name === "sessions") {
    icon = <><rect x="3.5" y="4.5" width="17" height="12" rx="2.2" /><path d="M8 20h8M12 16.5V20" /></>;
  } else if (name === "users") {
    icon = <><circle cx="9" cy="8" r="3" /><circle cx="17" cy="9" r="2.4" /><path d="M3.5 20c.5-4 2.5-6 5.5-6s5 2 5.5 6M14.5 14.5c2.8.2 4.7 2 5 5.5" /></>;
  } else if (name === "theme") {
    icon = <><circle cx="12" cy="12" r="3.2" /><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1" /></>;
  } else if (name === "regional") {
    icon = <><circle cx="12" cy="12" r="9" /><path d="M3.5 9h17M3.5 15h17M12 3c2 2.4 3 5.4 3 9s-1 6.6-3 9M12 3c-2 2.4-3 5.4-3 9s1 6.6 3 9" /></>;
  } else if (name === "inventory") {
    icon = <><path d="m4 7 8-4 8 4-8 4-8-4Z" /><path d="M4 7v10l8 4 8-4V7M12 11v10" /></>;
  } else if (name === "reservation") {
    icon = <><rect x="4" y="5" width="16" height="15" rx="2.3" /><path d="M8 3v4M16 3v4M4 9h16M8 14l2.2 2.2L16 12" /></>;
  } else if (name === "api") {
    icon = <><circle cx="8" cy="12" r="3.5" /><path d="M11.5 12H21M17 12v3M20 12v2" /></>;
  } else if (name === "server") {
    icon = <><rect x="4" y="4" width="16" height="6" rx="2" /><rect x="4" y="14" width="16" height="6" rx="2" /><path d="M8 7h.01M8 17h.01M12 7h5M12 17h5" /></>;
  } else if (name === "capabilities") {
    icon = <><path d="M4 7h7M15 7h5M4 17h4M12 17h8M4 12h11M19 12h1" /><circle cx="13" cy="7" r="2" /><circle cx="10" cy="17" r="2" /><circle cx="17" cy="12" r="2" /></>;
  } else if (name === "connections") {
    icon = <g transform="translate(0 1.5)"><path d="M8 12H5a3 3 0 0 1 0-6h4M16 12h3a3 3 0 1 0 0-6h-4" /><path d="M9 9h6M9 15h6M12 9v6" /></g>;
  } else if (name === "advanced") {
    icon = <><path d="M12 3 19 6v5c0 4.6-2.6 8-7 10-4.4-2-7-5.4-7-10V6l7-3Z" /><path d="M12 8v5M12 16h.01" /></>;
  } else if (name === "backup") {
    icon = <><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v6c0 1.7 3.1 3 7 3M19 6v5" /><path d="M12 12v9M8.5 17.5 12 21l3.5-3.5" /></>;
  } else if (name === "restore") {
    icon = <><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v6c0 1.7 3.1 3 7 3M19 6v5" /><path d="M12 21v-9M8.5 15.5 12 12l3.5 3.5" /></>;
  } else if (name === "reset") {
    icon = <><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v6c0 1.7 3.1 3 7 3M19 6v6" /><path d="m9 16 6 6M15 16l-6 6" /></>;
  }

  return (
    <span className="settings-stage-icon" data-settings-stage-icon={name} aria-hidden="true">
      <svg {...common}>{icon}</svg>
    </span>
  );
}
