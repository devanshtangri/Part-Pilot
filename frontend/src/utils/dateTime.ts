// PARTPILOT:WORKSPACE_TIMEZONE_FORMATTING:V676

export function parseApiDateTime(value: string): Date {
  const normalised = value.trim().replace(" ", "T");
  const zoned = /(?:Z|[+-]\d{2}:\d{2})$/i.test(normalised)
    ? normalised
    : `${normalised}Z`;
  return new Date(zoned);
}

export function formatWorkspaceDateTime(
  value: string | null,
  timezone: string | null,
  emptyLabel = "Not recorded"
): string {
  if (!value) return emptyLabel;
  const parsed = parseApiDateTime(value);
  if (Number.isNaN(parsed.getTime())) return value;
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
      ...(timezone ? { timeZone: timezone } : {})
    }).format(parsed);
  } catch {
    return parsed.toLocaleString();
  }
}

export function formatWorkspaceCompactDateTime(
  value: string,
  timezone: string | null
): string {
  const parsed = parseApiDateTime(value);
  if (Number.isNaN(parsed.getTime())) return value;
  try {
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      ...(timezone ? { timeZone: timezone } : {})
    }).format(parsed);
  } catch {
    return parsed.toLocaleString();
  }
}
