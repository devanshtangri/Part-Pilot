import type {
  BackupDownloadResult,
  RestoreCommitResponse,
  RestoreValidationResponse
} from "../types/backups";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

interface ValidationDetail {
  msg?: string;
}

async function parseApiError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as {
      detail?: string | ValidationDetail[];
    };
    if (typeof body.detail === "string") {
      return body.detail;
    }
    if (Array.isArray(body.detail)) {
      const messages = body.detail
        .map((item) => item.msg)
        .filter((message): message is string => Boolean(message));
      if (messages.length > 0) {
        return messages.join("; ");
      }
    }
  } catch {
    // Fall through to the generic response message.
  }
  return `Request failed with status ${response.status}`;
}

function contentDispositionFilename(response: Response): string {
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }
  const quotedMatch = disposition.match(/filename="([^"]+)"/i);
  if (quotedMatch?.[1]) {
    return quotedMatch[1];
  }
  const plainMatch = disposition.match(/filename=([^;]+)/i);
  return plainMatch?.[1]?.trim() || "part-pilot-backup.ppbackup";
}

// PARTPILOT:BACKUP_RESTORE_CLIENT:V442
export async function downloadBackup(
  token: string
): Promise<BackupDownloadResult> {
  const response = await fetch(`${API_BASE_URL}/backups/download`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return {
    blob: await response.blob(),
    filename: contentDispositionFilename(response)
  };
}

export async function validateRestoreBackup(
  token: string,
  backup: File
): Promise<RestoreValidationResponse> {
  const form = new FormData();
  form.append("backup", backup, backup.name);
  const response = await fetch(`${API_BASE_URL}/restores/validate`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    },
    body: form
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return response.json() as Promise<RestoreValidationResponse>;
}

export async function commitRestoreBackup(
  token: string,
  validationToken: string
): Promise<RestoreCommitResponse> {
  const response = await fetch(
    `${API_BASE_URL}/restores/${encodeURIComponent(validationToken)}/commit`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        confirmation: "RESTORE"
      })
    }
  );
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return response.json() as Promise<RestoreCommitResponse>;
}

export async function waitForPartPilotReady(
  timeoutMs = 120_000
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${API_BASE_URL}/ready`, {
        cache: "no-store"
      });
      if (response.ok) {
        const payload = (await response.json()) as {
          status?: string;
          phase?: string;
        };
        if (payload.status === "ready" && payload.phase === "ready") {
          return;
        }
      }
    } catch {
      // Connection failures are expected while the container restarts.
    }
    await new Promise((resolve) => window.setTimeout(resolve, 1500));
  }
  throw new Error(
    "Part Pilot did not become ready within two minutes. Reload after the server is healthy."
  );
}
