// PARTPILOT:PROJECTS_CLIENT:V379

import type {
  Project,
  ProjectCollection,
  ProjectCreatePayload,
  ProjectStatus,
  ProjectUpdatePayload
} from "../types/projects";

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

async function requestJson<T>(
  path: string,
  token: string,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...init?.headers
    }
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return response.json() as Promise<T>;
}

export function getProjects(
  token: string,
  options?: {
    status?: ProjectStatus;
    limit?: number;
    offset?: number;
    signal?: AbortSignal;
  }
): Promise<ProjectCollection> {
  const parameters = new URLSearchParams();
  if (options?.status) {
    parameters.set("status", options.status);
  }
  if (options?.limit !== undefined) {
    parameters.set("limit", String(options.limit));
  }
  if (options?.offset !== undefined) {
    parameters.set("offset", String(options.offset));
  }

  const query = parameters.toString();
  return requestJson<ProjectCollection>(
    `/projects${query ? `?${query}` : ""}`,
    token,
    { signal: options?.signal }
  );
}

export function getProject(
  token: string,
  projectId: number,
  signal?: AbortSignal
): Promise<Project> {
  return requestJson<Project>(`/projects/${projectId}`, token, { signal });
}

export function createProject(
  token: string,
  payload: ProjectCreatePayload
): Promise<Project> {
  return requestJson<Project>("/projects", token, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateProject(
  token: string,
  projectId: number,
  payload: ProjectUpdatePayload
): Promise<Project> {
  return requestJson<Project>(`/projects/${projectId}`, token, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}
// PARTPILOT:PROJECT_RESERVE_CLIENT:V384
export function reserveProject(
  token: string,
  projectId: number
): Promise<Project> {
  return requestJson<Project>(`/projects/${projectId}/reserve`, token, {
    method: "POST"
  });
}

// PARTPILOT:PROJECT_TERMINAL_CLIENT:V398
export function consumeProject(
  token: string,
  projectId: number
): Promise<Project> {
  return requestJson<Project>(`/projects/${projectId}/consume`, token, {
    method: "POST"
  });
}

export function cancelProject(
  token: string,
  projectId: number
): Promise<Project> {
  return requestJson<Project>(`/projects/${projectId}/cancel`, token, {
    method: "POST"
  });
}
