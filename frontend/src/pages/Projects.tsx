// PARTPILOT:PROJECTS_WORKSPACE:V381

import {
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import type {
  ChangeEvent,
  FormEvent,
  MouseEvent
} from "react";
import { useSearchParams } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { useLiveSyncRevision } from "../live/LiveSyncContext";
import { formatWorkspaceDateTime } from "../utils/dateTime";
import { getParts } from "../services/partsClient";
import {
  cancelProject,
  consumeProject,
  createProject,
  getProject,
  getProjects,
  reserveProject,
  updateProject
} from "../services/projectsClient";
import type { Part } from "../types/parts";
import type {
  Project,
  ProjectCollection,
  ProjectCreatePayload,
  ProjectStatus,
  ProjectUpdatePayload
} from "../types/projects";

import "./Projects.css";

const PAGE_SIZE = 25;
const PROJECT_STATUS_STORAGE_KEY = "partpilot.projects.status-filter";

const STATUS_OPTIONS: Array<{
  value: ProjectStatus | "all";
  label: string;
}> = [
  { value: "all", label: "All" },
  { value: "draft", label: "Draft" },
  { value: "reserved", label: "Reserved" },
  { value: "consumed", label: "Consumed" },
  { value: "cancelled", label: "Cancelled" }
];

interface DraftItem {
  key: string;
  partId: number | null;
  partNumber: string | null;
  partName: string | null;
  partTypeName: string | null;
  manufacturerName: string | null;
  locationName: string | null;
  availableQuantity: number | null;
  originalQuantity: number;
  partIsDeleted: boolean;
  quantity: number;
  note: string;
}

// PARTPILOT:PROJECT_TERMINAL_TYPES:V398
type ProjectLifecycleAction = "consume" | "cancel";

interface ProjectLifecycleNotice {
  projectId: number;
  message: string;
}

function readProjectStatusPreference(): ProjectStatus | "all" {
  if (typeof window === "undefined") {
    return "all";
  }

  try {
    const stored = window.localStorage.getItem(PROJECT_STATUS_STORAGE_KEY);
    if (STATUS_OPTIONS.some((option) => option.value === stored)) {
      return stored as ProjectStatus | "all";
    }
    if (stored !== null) {
      window.localStorage.removeItem(PROJECT_STATUS_STORAGE_KEY);
    }
  } catch {
    // A blocked preference store must not prevent Projects from loading.
  }

  return "all";
}

function writeProjectStatusPreference(value: ProjectStatus | "all"): void {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(PROJECT_STATUS_STORAGE_KEY, value);
  } catch {
    // The selected filter still works for the current session.
  }
}

function formatDate(value: string, timezone: string | null): string {
  return formatWorkspaceDateTime(value, timezone);
}

function formatMoney(
  value: number | string | null,
  currency: string | null
): string {
  if (value === null || value === undefined) {
    return "Not available";
  }
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    return String(value);
  }
  if (!currency) {
    return numberValue.toLocaleString();
  }
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency
    }).format(numberValue);
  } catch {
    return `${currency} ${numberValue.toLocaleString()}`;
  }
}

function statusLabel(status: ProjectStatus): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function partPrimaryLabel(part: Pick<Part, "part_number" | "name">): string {
  return part.part_number?.trim() || part.name?.trim() || "Unnamed part";
}

function partSecondaryLabel(part: Part): string {
  const values = [
    part.name?.trim() && part.name.trim() !== partPrimaryLabel(part)
      ? part.name.trim()
      : null,
    part.part_type_name,
    part.manufacturer_name,
    part.location_name
  ].filter((value): value is string => Boolean(value));
  return values.join(" · ") || "No additional metadata";
}

function draftPartPrimaryLabel(item: DraftItem): string {
  return item.partNumber?.trim() || item.partName?.trim() || "Unlinked part";
}

function draftPartSecondaryLabel(item: DraftItem): string {
  const primary = draftPartPrimaryLabel(item);
  const values = [
    item.partName?.trim() && item.partName.trim() !== primary
      ? item.partName.trim()
      : null,
    item.partTypeName,
    item.manufacturerName,
    item.locationName
  ].filter((value): value is string => Boolean(value));
  return values.join(" · ") || "No additional metadata";
}

function draftItemFromPart(part: Part): DraftItem {
  return {
    key: `part-${part.id}`,
    partId: part.id,
    partNumber: part.part_number,
    partName: part.name,
    partTypeName: part.part_type_name,
    manufacturerName: part.manufacturer_name,
    locationName: part.location_name,
    availableQuantity: part.available_quantity,
    originalQuantity: 0,
    partIsDeleted: false,
    quantity: 1,
    note: ""
  };
}

function draftItemFromProjectItem(item: Project["items"][number]): DraftItem {
  return {
    key: `project-item-${item.id}`,
    partId: item.part_id,
    partNumber: item.part_number,
    partName: item.part_name,
    partTypeName: null,
    manufacturerName: null,
    locationName: null,
    availableQuantity: item.available_quantity,
    originalQuantity: item.quantity,
    partIsDeleted: Boolean(item.part_is_deleted),
    quantity: item.quantity,
    note: item.note ?? ""
  };
}

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : "Unexpected request failure.";
}

// PARTPILOT:PROJECT_RESERVE_UI:V384
function projectReservationBlocker(project: Project): string | null {
  if (project.items.length === 0) {
    return "Add at least one part before reserving this Project.";
  }

  for (const item of project.items) {
    const label =
      item.part_number?.trim() ||
      item.part_name?.trim() ||
      `Project item ${item.id}`;

    if (item.part_id === null || item.part_is_deleted) {
      return `${label} is no longer linked to an active inventory part.`;
    }
    if (item.available_quantity === null) {
      return `${label} does not have a current availability value.`;
    }
    if (item.quantity > item.available_quantity) {
      return `${label} needs ${item.quantity} units, but only ${item.available_quantity} are currently available.`;
    }
  }

  return null;
}

function emptyCollection(offset = 0): ProjectCollection {
  return {
    total: 0,
    limit: PAGE_SIZE,
    offset,
    projects: []
  };
}

export function Projects() {
  const { token, timezone } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const projectsLiveRevision = useLiveSyncRevision("projects");
  const lastProjectsLiveRevision = useRef(projectsLiveRevision);
  const listRequestId = useRef(0);
  const detailRequestId = useRef(0);
  const partSearchRequestId = useRef(0);
  const listLoadedKeyRef = useRef<string | null>(null);
  const detailLoadedKeyRef = useRef<string | null>(null);

  const [collection, setCollection] = useState<ProjectCollection>(() =>
    emptyCollection()
  );
  const [statusFilter, setStatusFilter] =
    useState<ProjectStatus | "all">(readProjectStatusPreference);
  const [pageOffset, setPageOffset] = useState(0);
  const [reloadVersion, setReloadVersion] = useState(0);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [listLoading, setListLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [listError, setListError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [reserveProjectId, setReserveProjectId] = useState<number | null>(null);
  const [reserveSubmitting, setReserveSubmitting] = useState(false);
  const [reserveError, setReserveError] = useState("");

const [lifecycleAction, setLifecycleAction] =
  useState<ProjectLifecycleAction | null>(null);
const [lifecycleProjectId, setLifecycleProjectId] =
  useState<number | null>(null);
const [lifecycleSubmitting, setLifecycleSubmitting] = useState(false);
const [lifecycleError, setLifecycleError] = useState("");
const [lifecycleNotice, setLifecycleNotice] =
  useState<ProjectLifecycleNotice | null>(null);

  const [formMode, setFormMode] = useState<"create" | "edit" | null>(null);
  const [editingProjectId, setEditingProjectId] = useState<number | null>(null);
  const [editingProjectStatus, setEditingProjectStatus] =
    useState<ProjectStatus | null>(null);
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [draftName, setDraftName] = useState("");
  const [draftDescription, setDraftDescription] = useState("");
  const [draftNotes, setDraftNotes] = useState("");
  const [draftItems, setDraftItems] = useState<DraftItem[]>([]);
  const [partQuery, setPartQuery] = useState("");
  const [partOptions, setPartOptions] = useState<Part[]>([]);
  const [partSearchLoading, setPartSearchLoading] = useState(false);
  const [partSearchError, setPartSearchError] = useState("");

  // PARTPILOT:PROJECTS_LIVE_INVALIDATION:V700
  useEffect(() => {
    if (projectsLiveRevision === lastProjectsLiveRevision.current) {
      return;
    }
    lastProjectsLiveRevision.current = projectsLiveRevision;
    setReloadVersion((current) => current + 1);
  }, [projectsLiveRevision]);

  useEffect(() => {
    writeProjectStatusPreference(statusFilter);
  }, [statusFilter]);

  // PARTPILOT:DASHBOARD_QUICK_ACTION_INTENT:V730
  useEffect(() => {
    if (searchParams.get("create") !== "1") return;
    openCreate();
    const next = new URLSearchParams(searchParams);
    next.delete("create");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    if (!token) {
      listLoadedKeyRef.current = null;
      setCollection(emptyCollection(pageOffset));
      setListLoading(false);
      setListError("Sign in to view Projects.");
      return;
    }

    const requestId = ++listRequestId.current;
    const controller = new AbortController();
    const loadKey = `${token}:${statusFilter}:${pageOffset}`;
    const hasCachedList = listLoadedKeyRef.current === loadKey;
    setListLoading(!hasCachedList);
    setListError("");

    getProjects(token, {
      status: statusFilter === "all" ? undefined : statusFilter,
      limit: PAGE_SIZE,
      offset: pageOffset,
      signal: controller.signal
    })
      .then((response) => {
        if (requestId !== listRequestId.current) {
          return;
        }
        listLoadedKeyRef.current = loadKey;
        setCollection(response);
        setSelectedId((current) => {
          if (current !== null && response.projects.some((item) => item.id === current)) {
            return current;
          }
          if (window.matchMedia("(max-width: 900px)").matches) {
            return null;
          }
          return response.projects[0]?.id ?? null;
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || requestId !== listRequestId.current) {
          return;
        }
        if (!hasCachedList) {
          setCollection(emptyCollection(pageOffset));
          setSelectedId(null);
        }
        setListError(messageFrom(error));
      })
      .finally(() => {
        if (requestId === listRequestId.current) {
          setListLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [pageOffset, reloadVersion, statusFilter, token]);

  useEffect(() => {
    if (!token || selectedId === null) {
      detailLoadedKeyRef.current = null;
      setSelectedProject(null);
      setDetailLoading(false);
      setDetailError("");
      return;
    }

    const requestId = ++detailRequestId.current;
    const controller = new AbortController();
    const loadKey = `${token}:${selectedId}`;
    const hasCachedDetail = detailLoadedKeyRef.current === loadKey;
    setDetailLoading(!hasCachedDetail);
    if (!hasCachedDetail) setSelectedProject(null);
    setDetailError("");

    getProject(token, selectedId, controller.signal)
      .then((project) => {
        if (requestId === detailRequestId.current) {
          detailLoadedKeyRef.current = loadKey;
          setSelectedProject(project);
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || requestId !== detailRequestId.current) {
          return;
        }
        if (!hasCachedDetail) setSelectedProject(null);
        setDetailError(messageFrom(error));
      })
      .finally(() => {
        if (requestId === detailRequestId.current) {
          setDetailLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [reloadVersion, selectedId, token]);

  useEffect(() => {
    if (formMode === null) {
      partSearchRequestId.current += 1;
      setPartOptions([]);
      setPartSearchLoading(false);
      setPartSearchError("");
      return;
    }

    const query = partQuery.trim();
    if (!token || query.length < 2) {
      partSearchRequestId.current += 1;
      setPartOptions([]);
      setPartSearchLoading(false);
      setPartSearchError("");
      return;
    }

    const requestId = ++partSearchRequestId.current;
    const timer = window.setTimeout(() => {
      setPartSearchLoading(true);
      setPartSearchError("");
      getParts(token, {
        search: query,
        limit: 50,
        offset: 0
      })
        .then((response) => {
          if (requestId !== partSearchRequestId.current) {
            return;
          }
          const selectedPartIds = new Set(
            draftItems
              .map((item) => item.partId)
              .filter((partId): partId is number => partId !== null)
          );
          setPartOptions(
            response.parts.filter((part) => !selectedPartIds.has(part.id))
          );
        })
        .catch((error: unknown) => {
          if (requestId !== partSearchRequestId.current) {
            return;
          }
          setPartOptions([]);
          setPartSearchError(messageFrom(error));
        })
        .finally(() => {
          if (requestId === partSearchRequestId.current) {
            setPartSearchLoading(false);
          }
        });
    }, 280);

    return () => window.clearTimeout(timer);
  }, [draftItems, formMode, partQuery, token]);

  useEffect(() => {
    if (formMode === null) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !formSubmitting) {
        setFormMode(null);
        setEditingProjectId(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [formMode, formSubmitting]);


  useEffect(() => {
    if (reserveProjectId === null) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !reserveSubmitting) {
        setReserveProjectId(null);
        setReserveError("");
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [reserveProjectId, reserveSubmitting]);


useEffect(() => {
  if (lifecycleAction === null) {
    return;
  }

  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === "Escape" && !lifecycleSubmitting) {
      setLifecycleAction(null);
      setLifecycleProjectId(null);
      setLifecycleError("");
    }
  };

  window.addEventListener("keydown", handleKeyDown);
  return () => window.removeEventListener("keydown", handleKeyDown);
}, [lifecycleAction, lifecycleSubmitting]);

  const currentPage = Math.floor(pageOffset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(collection.total / PAGE_SIZE));
  const currentPageUnits = useMemo(
    () => collection.projects.reduce((total, project) => total + project.total_units, 0),
    [collection.projects]
  );
  const selectedStatusLabel =
    STATUS_OPTIONS.find((option) => option.value === statusFilter)?.label ?? "All";
  const reserveCandidate =
    reserveProjectId !== null && selectedProject?.id === reserveProjectId
      ? selectedProject
      : null;
  const reserveBlocker = reserveCandidate
    ? projectReservationBlocker(reserveCandidate)
    : null;

  const lifecycleCandidate =
    lifecycleAction !== null &&
    lifecycleProjectId !== null &&
    selectedProject?.id === lifecycleProjectId
      ? selectedProject
      : null;
  const isReservedEdit =
    formMode === "edit" && editingProjectStatus === "reserved";

  function changeStatus(nextStatus: ProjectStatus | "all") {
    setStatusFilter(nextStatus);
    setPageOffset(0);
    setSelectedId(null);
    setSelectedProject(null);
    setLifecycleNotice(null);
  }

  function resetFormSearch() {
    setPartQuery("");
    setPartOptions([]);
    setPartSearchError("");
  }

  function openCreate() {
    setDraftName("");
    setDraftDescription("");
    setDraftNotes("");
    setDraftItems([]);
    resetFormSearch();
    setFormError("");
    setEditingProjectId(null);
    setEditingProjectStatus(null);
    setFormMode("create");
  }

  function openEdit() {
    if (
      !selectedProject ||
      !["draft", "reserved"].includes(selectedProject.status)
    ) {
      return;
    }
    setDraftName(selectedProject.name);
    setDraftDescription(selectedProject.description ?? "");
    setDraftNotes(selectedProject.notes ?? "");
    setDraftItems(selectedProject.items.map(draftItemFromProjectItem));
    resetFormSearch();
    setFormError("");
    setEditingProjectId(selectedProject.id);
    setEditingProjectStatus(selectedProject.status);
    setFormMode("edit");
  }


  function openReserveProject() {
    if (!selectedProject || selectedProject.status !== "draft") {
      return;
    }
    setReserveError("");
    setReserveProjectId(selectedProject.id);
  }

  function closeReserveProject() {
    if (!reserveSubmitting) {
      setReserveProjectId(null);
      setReserveError("");
    }
  }

  async function submitReserveProject() {
    if (!token || reserveProjectId === null) {
      setReserveError("Sign in and select a Draft Project before reserving.");
      return;
    }

    const project =
      selectedProject?.id === reserveProjectId ? selectedProject : null;
    if (!project || project.status !== "draft") {
      setReserveError("The selected Project is no longer an editable Draft.");
      return;
    }

    const blocker = projectReservationBlocker(project);
    if (blocker) {
      setReserveError(blocker);
      return;
    }

    setReserveSubmitting(true);
    setReserveError("");
    try {
      const reserved = await reserveProject(token, reserveProjectId);
      setReserveProjectId(null);
      setStatusFilter("reserved");
      setPageOffset(0);
      setSelectedId(reserved.id);
      setSelectedProject(reserved);
      setReloadVersion((value) => value + 1);
    } catch (error: unknown) {
      setReserveError(messageFrom(error));
    } finally {
      setReserveSubmitting(false);
    }
  }

function openProjectLifecycle(action: ProjectLifecycleAction) {
  if (
    !selectedProject ||
    selectedProject.status !== "reserved" ||
    lifecycleSubmitting
  ) {
    return;
  }
  setLifecycleNotice(null);
  setLifecycleError("");
  setLifecycleProjectId(selectedProject.id);
  setLifecycleAction(action);
}

function closeProjectLifecycle() {
  if (!lifecycleSubmitting) {
    setLifecycleAction(null);
    setLifecycleProjectId(null);
    setLifecycleError("");
  }
}

async function submitProjectLifecycle() {
  if (
    !token ||
    lifecycleAction === null ||
    lifecycleProjectId === null ||
    lifecycleSubmitting
  ) {
    return;
  }

  const project =
    selectedProject?.id === lifecycleProjectId ? selectedProject : null;
  if (!project || project.status !== "reserved") {
    setLifecycleError(
      "The selected Project is no longer Reserved. Review its current status."
    );
    return;
  }

  const action = lifecycleAction;
  setLifecycleSubmitting(true);
  setLifecycleError("");
  try {
    const updated =
      action === "consume"
        ? await consumeProject(token, lifecycleProjectId)
        : await cancelProject(token, lifecycleProjectId);
    setLifecycleAction(null);
    setLifecycleProjectId(null);
    setLifecycleNotice({
      projectId: updated.id,
      message:
        action === "consume"
          ? `"${updated.name}" was consumed. Physical and reserved stock were reduced together.`
          : `"${updated.name}" was cancelled. Reserved stock was released back to available inventory.`
    });
    setStatusFilter(updated.status);
    setPageOffset(0);
    setSelectedId(updated.id);
    setSelectedProject(updated);
    setReloadVersion((value) => value + 1);
  } catch (error: unknown) {
    setLifecycleError(messageFrom(error));
  } finally {
    setLifecycleSubmitting(false);
  }
}

  function closeForm() {
    if (!formSubmitting) {
      setFormMode(null);
      setEditingProjectId(null);
      setEditingProjectStatus(null);
    }
  }

  function addDraftPart(part: Part) {
    setDraftItems((current) => {
      if (current.some((item) => item.partId === part.id)) {
        return current;
      }
      return [...current, draftItemFromPart(part)];
    });
    setPartOptions((current) => current.filter((option) => option.id !== part.id));
  }

  function removeDraftPart(key: string) {
    setDraftItems((current) => current.filter((item) => item.key !== key));
  }

  function updateDraftQuantity(key: string, quantity: number) {
    const normalised = Number.isFinite(quantity)
      ? Math.min(999999, Math.max(1, Math.trunc(quantity)))
      : 1;
    setDraftItems((current) =>
      current.map((item) =>
        item.key === key ? { ...item, quantity: normalised } : item
      )
    );
  }

  function updateDraftNote(key: string, note: string) {
    setDraftItems((current) =>
      current.map((item) => (item.key === key ? { ...item, note } : item))
    );
  }

  function buildProjectPayload(): ProjectUpdatePayload | null {
    const name = draftName.trim();
    if (!name) {
      setFormError("Project name is required.");
      return null;
    }
    if (draftItems.length === 0) {
      setFormError("Add at least one part to the Project.");
      return null;
    }
    const unavailableItem = draftItems.find(
      (item) => item.partId === null || item.partIsDeleted
    );
    if (unavailableItem) {
      setFormError(
        `Remove ${draftPartPrimaryLabel(unavailableItem)} before saving because its inventory link is unavailable.`
      );
      return null;
    }

    return {
      name,
      description: draftDescription.trim() || null,
      notes: draftNotes.trim() || null,
      items: draftItems.map((item) => ({
        part_id: item.partId as number,
        quantity: item.quantity,
        note: item.note.trim() || null
      }))
    };
  }

  async function submitProjectForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      setFormError("Sign in before saving a Project.");
      return;
    }
    if (formMode === null) {
      return;
    }
    if (formMode === "edit" && editingProjectId === null) {
      setFormError("The Project selection is no longer available.");
      return;
    }
    const payload = buildProjectPayload();
    if (!payload) {
      return;
    }

    setFormSubmitting(true);
    setFormError("");
    try {
      const saved = formMode === "create"
        ? await createProject(token, payload as ProjectCreatePayload)
        : await updateProject(token, editingProjectId as number, payload);
      setFormMode(null);
      setEditingProjectId(null);
      setEditingProjectStatus(null);
      if (formMode === "create") {
        setStatusFilter("draft");
        setPageOffset(0);
      }
      setSelectedId(saved.id);
      setSelectedProject(saved);
      setReloadVersion((value) => value + 1);
    } catch (error: unknown) {
      setFormError(messageFrom(error));
    } finally {
      setFormSubmitting(false);
    }
  }

  return (
    <section
      className="projects-page page-stack"
      data-partpilot-marker="PARTPILOT:PROJECTS_WORKSPACE:V381"
      data-partpilot-live-sync="PARTPILOT:PROJECTS_LIVE_INVALIDATION:V700"
      data-partpilot-background-refresh="PARTPILOT:STABLE_BACKGROUND_REFRESH:V718"
      data-partpilot-project-lifecycle="PARTPILOT:PROJECT_TERMINAL_ACTIONS:V398"
      data-partpilot-project-mobile-landing="PARTPILOT:PROJECT_MOBILE_LANDING:V399"
      data-partpilot-compact-summary="PARTPILOT:COMPACT_MOBILE_SUMMARY:V399"
      data-partpilot-reserved-edit="PARTPILOT:PROJECT_RESERVED_EDIT_UI:V400"
      data-partpilot-lifecycle-information="PARTPILOT:LIFECYCLE_INFORMATION_HIERARCHY:V402"
    >
      <header className="projects-header">
        <div className="page-header">
          <p className="eyebrow">Planning workspace</p>
          <h1>Projects</h1>
          <p>
            Plan parts and quantities before reserving or consuming stock. Draft
            Projects capture price snapshots without changing inventory.
          </p>
        </div>
        <button
          className="projects-button projects-button-primary"
          type="button"
          onClick={openCreate}
        >
          New Project
        </button>
      </header>

      <div className="projects-summary" aria-label="Project summary">
        <article>
          <span>Total results</span>
          <strong>{collection.total}</strong>
        </article>
        <article>
          <span>Current page</span>
          <strong>{collection.projects.length}</strong>
        </article>
        <article>
          <span>Planned units</span>
          <strong>{currentPageUnits}</strong>
        </article>
        <article>
          <span>Status filter</span>
          <strong>{selectedStatusLabel}</strong>
        </article>
      </div>

      <div className="projects-toolbar">
        <div className="projects-status-tabs" aria-label="Filter Projects by status">
          {STATUS_OPTIONS.map((option) => (
            <button
              key={option.value}
              className={`projects-status-tab${
                statusFilter === option.value ? " is-active" : ""
              }`}
              type="button"
              aria-pressed={statusFilter === option.value}
              onClick={() => changeStatus(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="projects-workspace">
        <section className="projects-list-panel" aria-label="Project register">
          <div className="projects-list-heading">
            <div>
              <strong>Project register</strong>
              <span>Newest Projects first</span>
            </div>
            <span>{collection.total} records</span>
          </div>
          <div className="projects-list-columns" aria-hidden="true">
            <span>Project</span>
            <span>Status</span>
            <span>Items</span>
            <span>Updated</span>
          </div>

          <div className="projects-list">
            {listLoading ? (
              <div className="projects-list-state">Loading Projects…</div>
            ) : listError ? (
              <div className="projects-list-state is-error">
                <strong>Unable to load Projects</strong>
                <span>{listError}</span>
              </div>
            ) : collection.projects.length === 0 ? (
              <div className="projects-list-state">
                <strong>No Projects found</strong>
                <span>Create a Draft or choose another status filter.</span>
              </div>
            ) : (
              collection.projects.map((project) => (
                <button
                  key={project.id}
                  className={`project-row${
                    selectedId === project.id ? " is-selected" : ""
                  }`}
                  type="button"
                  aria-pressed={selectedId === project.id}
                  onClick={() => setSelectedId(project.id)}
                >
                  <span className="project-row-main">
                    <strong>{project.name}</strong>
                    <small>{project.description || "No description"}</small>
                  </span>
                  <span className={`project-status is-${project.status}`}>
                    {statusLabel(project.status)}
                  </span>
                  <span className="project-row-number">
                    {project.item_count} / {project.total_units}
                  </span>
                  <span className="project-row-date">
                    {formatDate(project.updated_at, timezone)}
                  </span>
                </button>
              ))
            )}
          </div>

          <footer className="projects-pagination">
            <span>
              Page {currentPage} of {totalPages}
            </span>
            <div>
              <button
                className="projects-button"
                type="button"
                disabled={pageOffset === 0 || listLoading}
                onClick={() => setPageOffset((value) => Math.max(0, value - PAGE_SIZE))}
              >
                Previous
              </button>
              <button
                className="projects-button"
                type="button"
                disabled={pageOffset + PAGE_SIZE >= collection.total || listLoading}
                onClick={() => setPageOffset((value) => value + PAGE_SIZE)}
              >
                Next
              </button>
            </div>
          </footer>
        </section>

        <aside className="project-detail-panel" aria-label="Project details">
          {selectedId === null ? (
            <div className="project-detail-empty">
              <strong>Select a Project</strong>
              <span>Choose a register row to inspect its planned parts.</span>
            </div>
          ) : detailLoading ? (
            <div className="project-detail-state">Loading Project details…</div>
          ) : detailError ? (
            <div className="project-detail-state is-error">
              <strong>Unable to load Project</strong>
              <span>{detailError}</span>
            </div>
          ) : selectedProject ? (
            <>
              <header className="project-detail-header">
                <div>
                  <p className="eyebrow">Project #{selectedProject.id}</p>
                  <h2>{selectedProject.name}</h2>
                  <p>{selectedProject.description || "No description provided."}</p>
                </div>
                <div className="project-detail-actions">
                  {selectedProject.status === "draft" ? (
                    <>
                      <button
                        className="projects-button projects-button-primary"
                        type="button"
                        onClick={openReserveProject}
                      >
                        Reserve Project
                      </button>
                      <button
                        className="projects-button"
                        type="button"
                        onClick={openEdit}
                      >
                        Edit Draft
                      </button>
                    </>
                  ) : null}
                  {selectedProject.status === "reserved" ? (
                    <>
                      <button
                        className="projects-button"
                        type="button"
                        disabled={lifecycleSubmitting}
                        onClick={openEdit}
                      >
                        Edit Reserved
                      </button>
                      <button
                        className="projects-button projects-button-primary"
                        type="button"
                        disabled={lifecycleSubmitting}
                        onClick={() => openProjectLifecycle("consume")}
                      >
                        Consume Project
                      </button>
                      <button
                        className="projects-button projects-button-danger"
                        type="button"
                        disabled={lifecycleSubmitting}
                        onClick={() => openProjectLifecycle("cancel")}
                      >
                        Cancel Project
                      </button>
                    </>
                  ) : null}
                  <button
                    className="projects-button projects-close-mobile"
                    type="button"
                    aria-label="Close Project details"
                    onClick={() => setSelectedId(null)}
                  >
                    Close
                  </button>
                </div>
              </header>

              {lifecycleNotice?.projectId === selectedProject.id ? (
                <div
                  className="project-lifecycle-notice"
                  role="status"
                  aria-live="polite"
                >
                  <strong>Lifecycle updated</strong>
                  <span>{lifecycleNotice.message}</span>
                </div>
              ) : null}

              <div className="project-facts">
                <article>
                  <span>Status</span>
                  <strong className={`project-status is-${selectedProject.status}`}>
                    {statusLabel(selectedProject.status)}
                  </strong>
                </article>
                <article>
                  <span>Items</span>
                  <strong>{selectedProject.item_count}</strong>
                </article>
                <article>
                  <span>Planned units</span>
                  <strong>{selectedProject.total_units}</strong>
                </article>
                <article>
                  <span>Estimated value</span>
                  <strong>
                    {formatMoney(
                      selectedProject.estimated_total_value,
                      selectedProject.currency_snapshot
                    )}
                  </strong>
                </article>
              </div>

              <section className="project-detail-section">
                <div className="project-items-heading">
                  <div>
                    <strong>Planned parts</strong>
                    <span>Snapshots remain fixed; availability is current.</span>
                  </div>
                  <span>{selectedProject.items.length}</span>
                </div>
                <div className="project-items-list">
                  {selectedProject.items.map((item) => {
                    const exceedsAvailability =
                      item.available_quantity !== null &&
                      item.quantity > item.available_quantity;
                    return (
                      <article
                        key={item.id}
                        className={exceedsAvailability ? "is-short" : undefined}
                      >
                        <div className="project-item-main">
                          <strong>
                            {item.part_number || item.part_name || "Deleted part"}
                          </strong>
                          <span>{item.part_name || "Part name unavailable"}</span>
                        </div>
                        <dl>
                          <div>
                            <dt>Planned</dt>
                            <dd>{item.quantity}</dd>
                          </div>
                          <div>
                            <dt>Available now</dt>
                            <dd>{item.available_quantity ?? "Unavailable"}</dd>
                          </div>
                          <div>
                            <dt>Unit snapshot</dt>
                            <dd>
                              {formatMoney(
                                item.unit_price_snapshot,
                                item.currency_snapshot
                              )}
                            </dd>
                          </div>
                        </dl>
                        {item.note ? <p>{item.note}</p> : null}
                        {item.part_is_deleted ? (
                          <small className="project-item-warning">
                            This inventory part has been deleted.
                          </small>
                        ) : exceedsAvailability ? (
                          <small className="project-item-warning">
                            Planned quantity exceeds current availability.
                          </small>
                        ) : null}
                      </article>
                    );
                  })}
                </div>
              </section>

              <section className="project-detail-section project-notes">
                <strong>Project notes</strong>
                <p>{selectedProject.notes || "No Project notes."}</p>
              </section>

              <footer className="project-detail-footer">
                <span>Created {formatDate(selectedProject.created_at, timezone)}</span>
                <span>Updated {formatDate(selectedProject.updated_at, timezone)}</span>
              </footer>
            </>
          ) : null}
        </aside>
      </div>


      {reserveCandidate ? (
        <div
          className="project-modal-backdrop"
          role="presentation"
          onMouseDown={(event: MouseEvent<HTMLDivElement>) => {
            if (event.target === event.currentTarget) {
              closeReserveProject();
            }
          }}
        >
          <section
            className="project-reserve-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="project-reserve-title"
            data-partpilot-marker="PARTPILOT:PROJECT_RESERVE_DIALOG:V384"
          >
            <header>
              <div>
                <p className="eyebrow">Inventory commitment</p>
                <h2 id="project-reserve-title">Reserve Project</h2>
                <p>
                  This creates one active Reservation and commits the planned
                  quantities against current availability.
                </p>
              </div>
              <button
                className="projects-button"
                type="button"
                aria-label="Close Reserve Project confirmation"
                disabled={reserveSubmitting}
                onClick={closeReserveProject}
              >
                Close
              </button>
            </header>

            <div className="project-reserve-body">
              <div className="project-reserve-summary">
                <article>
                  <span>Project</span>
                  <strong>{reserveCandidate.name}</strong>
                </article>
                <article>
                  <span>Parts</span>
                  <strong>{reserveCandidate.item_count}</strong>
                </article>
                <article>
                  <span>Units to reserve</span>
                  <strong>{reserveCandidate.total_units}</strong>
                </article>
              </div>

              <div className="project-reserve-impact">
                <strong>What will change</strong>
                <p>
                  Reserved quantities will increase and matching reserve
                  movements will be recorded. Physical stock totals will not
                  change. The Project will move from Draft to Reserved.
                </p>
              </div>

              {reserveBlocker ? (
                <div className="project-reserve-warning" role="alert">
                  <strong>Reservation cannot continue</strong>
                  <span>{reserveBlocker}</span>
                </div>
              ) : null}

              {reserveError ? (
                <div className="project-form-error" role="alert">
                  {reserveError}
                </div>
              ) : null}
            </div>

            <footer>
              <span>
                Availability is checked again atomically when you confirm.
              </span>
              <button
                className="projects-button projects-button-primary"
                type="button"
                disabled={reserveSubmitting || Boolean(reserveBlocker)}
                onClick={submitReserveProject}
              >
                {reserveSubmitting ? "Reserving…" : "Reserve this Project"}
              </button>
            </footer>
          </section>
        </div>
      ) : null}


{lifecycleCandidate && lifecycleAction ? (
  <div
    className="project-modal-backdrop"
    role="presentation"
    onMouseDown={(event: MouseEvent<HTMLDivElement>) => {
      if (event.target === event.currentTarget) {
        closeProjectLifecycle();
      }
    }}
  >
    <section
      className={`project-reserve-dialog project-lifecycle-dialog is-${lifecycleAction}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="project-lifecycle-title"
      aria-describedby="project-lifecycle-description"
      aria-busy={lifecycleSubmitting}
      data-partpilot-marker="PARTPILOT:PROJECT_TERMINAL_DIALOG:V398"
    >
      <header>
        <div>
          <p className="eyebrow">
            {lifecycleAction === "consume"
              ? "Permanent stock movement"
              : "Release inventory commitment"}
          </p>
          <h2 id="project-lifecycle-title">
            {lifecycleAction === "consume"
              ? "Consume Project"
              : "Cancel Project"}
          </h2>
          <p id="project-lifecycle-description">
            {lifecycleAction === "consume"
              ? "Confirm the permanent removal of the reserved physical stock assigned to this Project."
              : "Confirm that the reserved stock should be released without changing physical inventory totals."}
          </p>
        </div>
        <button
          className="projects-button"
          type="button"
          aria-label={`Close ${
            lifecycleAction === "consume" ? "Consume" : "Cancel"
          } Project confirmation`}
          disabled={lifecycleSubmitting}
          onClick={closeProjectLifecycle}
        >
          Close
        </button>
      </header>

      <div className="project-reserve-body">
        <div className="project-reserve-summary">
          <article>
            <span>Project</span>
            <strong>{lifecycleCandidate.name}</strong>
          </article>
          <article>
            <span>Parts</span>
            <strong>{lifecycleCandidate.item_count}</strong>
          </article>
          <article>
            <span>
              {lifecycleAction === "consume"
                ? "Units to remove"
                : "Units to release"}
            </span>
            <strong>{lifecycleCandidate.total_units}</strong>
          </article>
        </div>

        <div
          className={`project-reserve-impact project-lifecycle-impact is-${lifecycleAction}`}
        >
          <strong>Stock impact</strong>
          <p>
            {lifecycleAction === "consume"
              ? `Confirming permanently removes ${lifecycleCandidate.total_units} physical units and clears the same reserved units. Available quantity remains unchanged because physical and reserved stock decrease together.`
              : `Confirming releases ${lifecycleCandidate.total_units} reserved units back to available inventory. Physical stock totals do not change.`}
          </p>
        </div>

        <div className="project-lifecycle-terminal-note">
          <strong>
            {lifecycleAction === "consume"
              ? "This stock removal cannot be undone from this Project."
              : "This closes the Project without consuming stock."}
          </strong>
          <span>
            {lifecycleAction === "consume"
              ? "The Project and its linked Reservation will both become Consumed."
              : "The Project and its linked Reservation will both become Cancelled."}
          </span>
        </div>

        {lifecycleError ? (
          <div className="project-form-error" role="alert">
            {lifecycleError}
          </div>
        ) : null}
      </div>

      <footer>
        <span>
          Current status and inventory are checked atomically. Any
          conflict rejects the complete action without partial changes.
        </span>
        <button
          autoFocus
          className={`projects-button ${
            lifecycleAction === "consume"
              ? "projects-button-danger"
              : "projects-button-primary"
          }`}
          type="button"
          disabled={lifecycleSubmitting}
          onClick={() => void submitProjectLifecycle()}
        >
          {lifecycleSubmitting
            ? lifecycleAction === "consume"
              ? "Consuming…"
              : "Cancelling…"
            : lifecycleAction === "consume"
              ? "Consume physical stock"
              : "Release reserved stock"}
        </button>
      </footer>
    </section>
  </div>
) : null}

      {formMode !== null ? (
        <div
          className="project-modal-backdrop"
          role="presentation"
          onMouseDown={(event: MouseEvent<HTMLDivElement>) => {
            if (event.target === event.currentTarget) {
              closeForm();
            }
          }}
        >
          <section
            className="project-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="project-form-title"
            data-partpilot-marker={
              formMode === "edit"
                ? "PARTPILOT:PROJECT_EDIT_MODAL:V381"
                : "PARTPILOT:PROJECT_CREATE_MODAL:V381"
            }
          >
            <header>
              <div>
                <p className="eyebrow">
                  {isReservedEdit
                    ? "Atomic reservation adjustment"
                    : "Inventory-neutral planning"}
                </p>
                <h2 id="project-form-title">
                  {formMode === "edit"
                    ? isReservedEdit
                      ? "Edit Reserved Project"
                      : "Edit Draft Project"
                    : "New Project"}
                </h2>
                <p>
                  {formMode === "edit"
                    ? isReservedEdit
                      ? "Update the Project and linked Reservation together. Quantity increases reserve only the additional units; decreases release only the removed units."
                      : "Update the Draft plan and refresh price snapshots without reserving, consuming, or otherwise changing stock."
                    : "Add active inventory parts and planned quantities. This Draft does not reserve, consume, or otherwise change stock."}
                </p>
              </div>
              <button
                className="projects-button"
                type="button"
                aria-label={
                  formMode === "edit"
                    ? isReservedEdit
                      ? "Close Edit Reserved Project form"
                      : "Close Edit Draft Project form"
                    : "Close new Project form"
                }
                disabled={formSubmitting}
                onClick={closeForm}
              >
                Close
              </button>
            </header>

            <form onSubmit={submitProjectForm}>
              <div className="project-form-grid">
                <label>
                  <span>Project name</span>
                  <input
                    autoFocus
                    required
                    maxLength={180}
                    value={draftName}
                    onChange={(event: ChangeEvent<HTMLInputElement>) =>
                      setDraftName(event.currentTarget.value)
                    }
                    placeholder="Weather monitoring node"
                  />
                </label>
                <label>
                  <span>Description</span>
                  <input
                    maxLength={5000}
                    value={draftDescription}
                    onChange={(event: ChangeEvent<HTMLInputElement>) =>
                      setDraftDescription(event.currentTarget.value)
                    }
                    placeholder="Optional one-line purpose"
                  />
                </label>
                <label className="project-form-wide">
                  <span>Notes</span>
                  <textarea
                    maxLength={10000}
                    rows={3}
                    value={draftNotes}
                    onChange={(event: ChangeEvent<HTMLTextAreaElement>) =>
                      setDraftNotes(event.currentTarget.value)
                    }
                    placeholder="Optional planning context"
                  />
                </label>
              </div>

              <div
                className="project-part-picker"
                data-partpilot-marker="PARTPILOT:PROJECT_PART_SEARCH_LAYOUT:V385"
              >
                <label>
                  <span>Find inventory parts</span>
                  <input
                    type="search"
                    value={partQuery}
                    onChange={(event: ChangeEvent<HTMLInputElement>) =>
                      setPartQuery(event.currentTarget.value)
                    }
                    placeholder="Search by part, type, manufacturer, location or metadata"
                  />
                </label>
                {partQuery.trim().length >= 2 ? (
                  <div
                    className="project-part-results"
                    aria-live="polite"
                    aria-label="Matching inventory parts"
                  >
                    {partSearchLoading ? (
                      <span>Searching inventory…</span>
                    ) : partSearchError ? (
                      <span className="is-error">{partSearchError}</span>
                    ) : partOptions.length === 0 ? (
                      <span>No additional matching parts.</span>
                    ) : (
                      <>
                        <div className="project-part-results-summary">
                          <strong>
                            {partOptions.length} matching{" "}
                            {partOptions.length === 1 ? "part" : "parts"}
                          </strong>
                          <small>Showing up to 50 results</small>
                        </div>
                        {partOptions.map((part) => (
                          <button
                            key={part.id}
                            type="button"
                            onClick={() => addDraftPart(part)}
                          >
                            <span>
                              <strong>{partPrimaryLabel(part)}</strong>
                              <small>{partSecondaryLabel(part)}</small>
                            </span>
                            <span
                              className={
                                part.available_quantity <= 0
                                  ? "is-short"
                                  : undefined
                              }
                            >
                              {part.available_quantity} available
                            </span>
                          </button>
                        ))}
                      </>
                    )}
                  </div>
                ) : (
                  <small className="project-part-search-hint">
                    Enter at least two characters to search inventory.
                  </small>
                )}
              </div>

              <div className="project-draft-items">
                <div className="project-draft-heading">
                  <strong>Planned items</strong>
                  <span>{draftItems.length} selected</span>
                </div>
                {draftItems.length === 0 ? (
                  <div className="project-draft-empty">
                    Search and add one or more active inventory parts.
                  </div>
                ) : (
                  draftItems.map((item) => {
                    const supportedQuantity =
                      item.availableQuantity === null
                        ? null
                        : item.availableQuantity +
                          (isReservedEdit ? item.originalQuantity : 0);
                    const exceedsAvailability =
                      supportedQuantity !== null &&
                      item.quantity > supportedQuantity;
                    const inventoryLinkUnavailable =
                      item.partId === null || item.partIsDeleted;
                    return (
                      <article
                        key={item.key}
                        className={inventoryLinkUnavailable ? "is-unavailable" : undefined}
                      >
                        <div className="project-draft-part">
                          <strong>{draftPartPrimaryLabel(item)}</strong>
                          <span>{draftPartSecondaryLabel(item)}</span>
                          <small
                            className={
                              inventoryLinkUnavailable
                                ? "is-unavailable"
                                : exceedsAvailability
                                  ? "is-short"
                                  : undefined
                            }
                          >
                            {inventoryLinkUnavailable
                              ? "Inventory link unavailable · remove before saving"
                              : isReservedEdit
                                ? `${supportedQuantity ?? "Unknown"} supported for this edit (${item.availableQuantity ?? "Unknown"} currently available + ${item.originalQuantity} already reserved)${
                                    exceedsAvailability
                                      ? " · exceeds supported quantity"
                                      : ""
                                  }`
                                : `${item.availableQuantity ?? "Unknown"} currently available${
                                    exceedsAvailability
                                      ? " · planning beyond availability"
                                      : ""
                                  }`}
                          </small>
                        </div>
                        <label>
                          <span>Quantity</span>
                          <input
                            type="number"
                            min={1}
                            max={999999}
                            value={item.quantity}
                            onChange={(event: ChangeEvent<HTMLInputElement>) =>
                              updateDraftQuantity(
                                item.key,
                                Number(event.currentTarget.value)
                              )
                            }
                          />
                        </label>
                        <label className="project-draft-note">
                          <span>Item note</span>
                          <input
                            maxLength={5000}
                            value={item.note}
                            onChange={(event: ChangeEvent<HTMLInputElement>) =>
                              updateDraftNote(item.key, event.currentTarget.value)
                            }
                            placeholder="Optional"
                          />
                        </label>
                        <button
                          className="projects-button"
                          type="button"
                          aria-label={`Remove ${draftPartPrimaryLabel(item)}`}
                          onClick={() => removeDraftPart(item.key)}
                        >
                          Remove
                        </button>
                      </article>
                    );
                  })
                )}
              </div>

              {formError ? (
                <div className="project-form-error" role="alert">
                  {formError}
                </div>
              ) : null}

              <footer>
                <span>
                  {formMode === "edit"
                    ? isReservedEdit
                      ? "Saving synchronises the linked Reservation and changes only reserved and available quantities; physical totals remain unchanged."
                      : "Saving replaces the Draft plan and refreshes snapshots; inventory remains unchanged."
                    : "Creating a Draft records snapshots only; inventory remains unchanged."}
                </span>
                <button
                  className="projects-button projects-button-primary"
                  type="submit"
                  disabled={formSubmitting || draftItems.length === 0}
                >
                  {formSubmitting
                    ? formMode === "edit"
                      ? "Saving…"
                      : "Creating…"
                    : formMode === "edit"
                      ? isReservedEdit
                        ? "Save Reserved Changes"
                        : "Save Draft Changes"
                      : "Create Draft Project"}
                </button>
              </footer>
            </form>
          </section>
        </div>
      ) : null}
    </section>
  );
}
