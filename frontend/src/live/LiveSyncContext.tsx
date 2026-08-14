import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useRef,
  useState
} from "react";

import { useAuth } from "../auth/AuthContext";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";
const STREAM_RECONNECT_BASE_MS = 750;
const STREAM_RECONNECT_MAX_MS = 15_000;
const POLL_INTERVAL_MS = 5_000;
const INVALIDATION_COALESCE_MS = 80;
const BROADCAST_CHANNEL_NAME = "partpilot.live-sync.v1";
const SEEN_EVENT_LIMIT = 512;

export const LIVE_SYNC_CLIENT_MARKER =
  "PARTPILOT:AUTHENTICATED_FETCH_SSE_CLIENT:V692";
const LIVE_SYNC_BROADCAST_MARKER =
  "PARTPILOT:LIVE_SYNC_BROADCAST_RELAY:V696";

const LIVE_SYNC_TOPICS = [
  "inventory",
  "catalogues",
  "projects",
  "reservations",
  "history",
  "preferences",
  "account",
  "integrations.api_keys",
  "integrations.mcp",
  "backups"
] as const;

export type LiveSyncTopic = (typeof LIVE_SYNC_TOPICS)[number];
type LiveSyncRevisions = Record<LiveSyncTopic, number>;

interface ParsedState {
  generation: string;
  revisions: LiveSyncRevisions;
}

interface ParsedSseEvent {
  id: string | null;
  event: string;
  data: string;
}

const LiveSyncContext = createContext<LiveSyncRevisions | null>(null);

function emptyRevisions(): LiveSyncRevisions {
  return {
    inventory: 0,
    catalogues: 0,
    projects: 0,
    reservations: 0,
    history: 0,
    preferences: 0,
    account: 0,
    "integrations.api_keys": 0,
    "integrations.mcp": 0,
    backups: 0
  };
}

function isLiveSyncTopic(value: string): value is LiveSyncTopic {
  return (LIVE_SYNC_TOPICS as readonly string[]).includes(value);
}

function parseState(value: unknown): ParsedState | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }

  const record = value as Record<string, unknown>;
  if (
    typeof record.generation !== "string"
    || !record.generation
    || typeof record.revisions !== "object"
    || record.revisions === null
  ) {
    return null;
  }

  const rawRevisions = record.revisions as Record<string, unknown>;
  const revisions = emptyRevisions();

  for (const topic of LIVE_SYNC_TOPICS) {
    const revision = rawRevisions[topic];
    if (
      typeof revision !== "number"
      || !Number.isInteger(revision)
      || revision < 0
    ) {
      return null;
    }
    revisions[topic] = revision;
  }

  return {
    generation: record.generation,
    revisions
  };
}

function parseInvalidationTopics(value: unknown): LiveSyncTopic[] {
  if (typeof value !== "object" || value === null) {
    return [];
  }
  const topics = (value as Record<string, unknown>).topics;
  if (!Array.isArray(topics)) {
    return [];
  }

  const unique = new Set<LiveSyncTopic>();
  for (const value of topics) {
    if (typeof value === "string" && isLiveSyncTopic(value)) {
      unique.add(value);
    }
  }
  return [...unique];
}

function parseSseBlock(block: string): ParsedSseEvent | null {
  let id: string | null = null;
  let event = "message";
  const data: string[] = [];

  for (const line of block.split(/\r?\n/)) {
    if (!line || line.startsWith(":")) {
      continue;
    }

    const separator = line.indexOf(":");
    const field = separator === -1 ? line : line.slice(0, separator);
    let value = separator === -1 ? "" : line.slice(separator + 1);
    if (value.startsWith(" ")) {
      value = value.slice(1);
    }

    if (field === "id") {
      id = value;
    } else if (field === "event") {
      event = value || "message";
    } else if (field === "data") {
      data.push(value);
    }
  }

  if (id === null && event === "message" && data.length === 0) {
    return null;
  }

  return {
    id,
    event,
    data: data.join("\n")
  };
}

async function consumeSse(
  response: Response,
  onEvent: (event: ParsedSseEvent) => void
): Promise<void> {
  if (!response.body) {
    throw new Error("Live-sync stream response has no body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const chunk = await reader.read();
    if (chunk.done) {
      break;
    }

    buffer += decoder.decode(chunk.value, { stream: true });
    while (true) {
      const boundary = /\r?\n\r?\n/.exec(buffer);
      if (!boundary || boundary.index === undefined) {
        break;
      }

      const block = buffer.slice(0, boundary.index);
      buffer = buffer.slice(boundary.index + boundary[0].length);
      const parsed = parseSseBlock(block);
      if (parsed) {
        onEvent(parsed);
      }
    }
  }

  buffer += decoder.decode();
}

function waitForReconnect(
  milliseconds: number,
  signal: AbortSignal
): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) {
      resolve();
      return;
    }

    const finish = () => {
      signal.removeEventListener("abort", abort);
      resolve();
    };
    const abort = () => {
      window.clearTimeout(timeoutId);
      finish();
    };
    const timeoutId = window.setTimeout(finish, milliseconds);
    signal.addEventListener("abort", abort, { once: true });
  });
}

// PARTPILOT:AUTHENTICATED_FETCH_SSE_PROVIDER:V692
export function LiveSyncProvider({ children }: { children: ReactNode }) {
  const { token, user } = useAuth();
  const hasUser = user !== null;
  const [revisions, setRevisions] =
    useState<LiveSyncRevisions>(() => emptyRevisions());
  const lastEventIdRef = useRef<string | null>(null);
  const generationRef = useRef<string | null>(null);
  const pendingTopicsRef = useRef<Set<LiveSyncTopic>>(new Set());
  const coalesceTimerRef = useRef<number | null>(null);
  const seenEventIdsRef = useRef<Set<string>>(new Set());
  const seenEventOrderRef = useRef<string[]>([]);

  useEffect(() => {
    document.documentElement.dataset.partpilotLiveSync =
      LIVE_SYNC_CLIENT_MARKER;
    document.documentElement.dataset.partpilotLiveSyncRelay =
      LIVE_SYNC_BROADCAST_MARKER;
    return () => {
      delete document.documentElement.dataset.partpilotLiveSync;
      delete document.documentElement.dataset.partpilotLiveSyncRelay;
    };
  }, []);

  useEffect(() => {
    if (!token || !hasUser) {
      lastEventIdRef.current = null;
      generationRef.current = null;
      pendingTopicsRef.current.clear();
      seenEventIdsRef.current.clear();
      seenEventOrderRef.current = [];
      if (coalesceTimerRef.current !== null) {
        window.clearTimeout(coalesceTimerRef.current);
        coalesceTimerRef.current = null;
      }
      setRevisions(emptyRevisions());
      return;
    }

    const controller = new AbortController();
    let stopped = false;
    let pollTimer: number | null = null;
    let pollingInFlight = false;
    let broadcast: BroadcastChannel | null = null;
    try {
      if (typeof BroadcastChannel !== "undefined") {
        broadcast = new BroadcastChannel(BROADCAST_CHANNEL_NAME);
      }
    } catch {
      broadcast = null;
    }

    const clearQueuedInvalidations = () => {
      pendingTopicsRef.current.clear();
      if (coalesceTimerRef.current !== null) {
        window.clearTimeout(coalesceTimerRef.current);
        coalesceTimerRef.current = null;
      }
    };

    const applyAuthoritativeState = (value: unknown) => {
      const parsed = parseState(value);
      if (!parsed) {
        throw new Error("Live-sync state payload is invalid");
      }
      if (
        generationRef.current !== null
        && generationRef.current !== parsed.generation
      ) {
        lastEventIdRef.current = null;
        seenEventIdsRef.current.clear();
        seenEventOrderRef.current = [];
      }
      generationRef.current = parsed.generation;
      clearQueuedInvalidations();
      setRevisions(parsed.revisions);
    };

    const queueInvalidations = (topics: LiveSyncTopic[]) => {
      for (const topic of topics) {
        pendingTopicsRef.current.add(topic);
      }
      if (
        pendingTopicsRef.current.size === 0
        || coalesceTimerRef.current !== null
      ) {
        return;
      }

      coalesceTimerRef.current = window.setTimeout(() => {
        coalesceTimerRef.current = null;
        const pending = [...pendingTopicsRef.current];
        pendingTopicsRef.current.clear();
        if (pending.length === 0) {
          return;
        }

        setRevisions((current) => {
          const next = { ...current };
          for (const topic of pending) {
            next[topic] += 1;
          }
          return next;
        });
      }, INVALIDATION_COALESCE_MS);
    };

    const rememberEventId = (eventId: string): boolean => {
      if (seenEventIdsRef.current.has(eventId)) {
        return false;
      }
      seenEventIdsRef.current.add(eventId);
      seenEventOrderRef.current.push(eventId);
      while (seenEventOrderRef.current.length > SEEN_EVENT_LIMIT) {
        const oldest = seenEventOrderRef.current.shift();
        if (oldest) {
          seenEventIdsRef.current.delete(oldest);
        }
      }
      return true;
    };

    const acceptInvalidation = (
      eventId: string | null,
      topics: LiveSyncTopic[],
      relay: boolean
    ) => {
      if (topics.length === 0) {
        return;
      }
      if (eventId && !rememberEventId(eventId)) {
        return;
      }
      queueInvalidations(topics);
      if (relay && eventId && broadcast) {
        broadcast.postMessage({
          kind: "invalidate",
          eventId,
          topics
        });
      }
    };

    if (broadcast) {
      broadcast.onmessage = (message: MessageEvent<unknown>) => {
        if (typeof message.data !== "object" || message.data === null) {
          return;
        }
        const record = message.data as Record<string, unknown>;
        if (
          record.kind !== "invalidate"
          || typeof record.eventId !== "string"
          || !record.eventId
          || !Array.isArray(record.topics)
        ) {
          return;
        }
        acceptInvalidation(
          record.eventId,
          parseInvalidationTopics({ topics: record.topics }),
          false
        );
      };
    }

    const fetchState = async () => {
      if (pollingInFlight || controller.signal.aborted) {
        return;
      }
      pollingInFlight = true;
      try {
        const response = await fetch(`${API_BASE_URL}/live/state`, {
          headers: {
            Authorization: `Bearer ${token}`
          },
          cache: "no-store",
          signal: controller.signal
        });
        if (!response.ok) {
          throw new Error(`Live-sync state request failed (${response.status})`);
        }
        applyAuthoritativeState(await response.json());
      } finally {
        pollingInFlight = false;
      }
    };

    const stopPolling = () => {
      if (pollTimer !== null) {
        window.clearInterval(pollTimer);
        pollTimer = null;
      }
    };

    const startPolling = () => {
      if (pollTimer !== null || controller.signal.aborted) {
        return;
      }
      void fetchState().catch(() => {
        // Reconnect loop remains authoritative for transport recovery.
      });
      pollTimer = window.setInterval(() => {
        void fetchState().catch(() => {
          // Keep degraded polling alive until streaming recovers.
        });
      }, POLL_INTERVAL_MS);
    };

    const handleEvent = (event: ParsedSseEvent) => {
      if (event.id) {
        lastEventIdRef.current = event.id;
      }
      if (!event.data) {
        return;
      }

      let payload: unknown;
      try {
        payload = JSON.parse(event.data);
      } catch {
        throw new Error("Live-sync SSE payload is invalid JSON");
      }

      if (event.event === "ready" || event.event === "resync") {
        applyAuthoritativeState(payload);
        return;
      }
      if (event.event === "invalidate") {
        acceptInvalidation(
          event.id,
          parseInvalidationTopics(payload),
          true
        );
      }
    };

    const connectStream = async () => {
      const headers: Record<string, string> = {
        Accept: "text/event-stream",
        Authorization: `Bearer ${token}`
      };
      if (lastEventIdRef.current) {
        headers["Last-Event-ID"] = lastEventIdRef.current;
      }

      const response = await fetch(`${API_BASE_URL}/live/events`, {
        headers,
        cache: "no-store",
        signal: controller.signal
      });
      if (!response.ok) {
        throw new Error(`Live-sync stream failed (${response.status})`);
      }

      stopPolling();
      await consumeSse(response, handleEvent);
      if (!controller.signal.aborted) {
        throw new Error("Live-sync stream ended");
      }
    };

    const run = async () => {
      let attempt = 0;

      while (!stopped && !controller.signal.aborted) {
        try {
          await connectStream();
          attempt = 0;
        } catch {
          if (stopped || controller.signal.aborted) {
            break;
          }
          startPolling();
          const exponent = Math.min(attempt, 5);
          const baseDelay = Math.min(
            STREAM_RECONNECT_MAX_MS,
            STREAM_RECONNECT_BASE_MS * 2 ** exponent
          );
          const jitter = Math.floor(baseDelay * 0.25 * Math.random());
          attempt += 1;
          await waitForReconnect(
            Math.min(STREAM_RECONNECT_MAX_MS, baseDelay + jitter),
            controller.signal
          );
        }
      }
    };

    void run();

    return () => {
      stopped = true;
      controller.abort();
      stopPolling();
      clearQueuedInvalidations();
      broadcast?.close();
    };
  }, [hasUser, token]);

  return (
    <LiveSyncContext.Provider value={revisions}>
      {children}
    </LiveSyncContext.Provider>
  );
}

export function useLiveSyncRevision(topic: LiveSyncTopic): number {
  const revisions = useContext(LiveSyncContext);
  if (revisions === null) {
    throw new Error("useLiveSyncRevision requires LiveSyncProvider");
  }
  return revisions[topic];
}
