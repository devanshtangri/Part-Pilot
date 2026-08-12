// PARTPILOT:RESERVATIONS_WORKSPACE:V340

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

import { useAuth } from "../auth/AuthContext";
import { formatWorkspaceDateTime, parseApiDateTime } from "../utils/dateTime";
import {
  cancelReservation,
  consumeReservation,
  deleteReservation,
  expireReservation,
  getReservation,
  getReservationActivity,
  getReservations,
  searchReservableParts,
  updateReservation
} from "../services/reservationsClient";
import type {
  ReservablePart,
  Reservation,
  ReservationActivityCollection,
  ReservationActivityEntry,
  ReservationCollection,
  ReservationStatus,
  ReservationUpdatePayload
} from "../types/reservations";

import "./Reservations.css";

const PAGE_SIZE = 25;
const RESERVATION_STATUS_STORAGE_KEY =
  "partpilot.reservations.status-filter";

const STATUS_OPTIONS: Array<{
  value: ReservationStatus | "all";
  label: string;
}> = [
  { value: "all", label: "All" },
  { value: "active", label: "Active" },
  { value: "consumed", label: "Consumed" },
  { value: "cancelled", label: "Cancelled" },
  { value: "expired", label: "Expired" }
];

// PARTPILOT:RESERVATION_STATUS_PREFERENCE:V352
function readReservationStatusPreference(): ReservationStatus | "all" {
  if (typeof window === "undefined") {
    return "active";
  }

  try {
    const stored = window.localStorage.getItem(
      RESERVATION_STATUS_STORAGE_KEY
    );
    if (STATUS_OPTIONS.some((option) => option.value === stored)) {
      return stored as ReservationStatus | "all";
    }
    if (stored !== null) {
      window.localStorage.removeItem(RESERVATION_STATUS_STORAGE_KEY);
    }
  } catch {
    // Blocked storage must not prevent the Reservations workspace from loading.
  }

  return "active";
}

function writeReservationStatusPreference(
  value: ReservationStatus | "all"
): void {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(RESERVATION_STATUS_STORAGE_KEY, value);
  } catch {
    // The selected tab still works for the current session without storage.
  }
}

interface DraftItem {
  part: ReservablePart;
  quantity: number;
  note: string;
  maxQuantity: number;
  originalQuantity: number;
}

// PARTPILOT:RESERVATION_API_DATETIME_UTC:V348
function formatDate(value: string | null, timezone: string | null): string {
  return formatWorkspaceDateTime(value, timezone, "No expiry");
}

function localDateTimeInputFromDate(date: Date): string {
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const pad = (part: number) => String(part).padStart(2, "0");
  return [
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
    `${pad(date.getHours())}:${pad(date.getMinutes())}`
  ].join("T");
}

function toLocalDateTimeInput(value: string | null): string {
  if (!value) {
    return "";
  }
  return localDateTimeInputFromDate(parseApiDateTime(value));
}

// PARTPILOT:RESERVATION_NOOP_GUARD:V348
function reservationMatchesPayload(
  reservation: Reservation,
  payload: ReservationUpdatePayload
): boolean {
  const reservationExpiry = reservation.expiry_at
    ? parseApiDateTime(reservation.expiry_at).getTime()
    : null;
  const payloadExpiry = payload.expiry_at
    ? parseApiDateTime(payload.expiry_at).getTime()
    : null;
  if (
    reservation.label !== payload.label ||
    reservation.notes !== (payload.notes ?? null) ||
    reservationExpiry !== payloadExpiry ||
    reservation.items.length !== payload.items.length
  ) {
    return false;
  }

  const existingItems = [...reservation.items]
    .map((item) => ({
      part_id: item.part_id,
      quantity: Number(item.quantity),
      note: item.note ?? null
    }))
    .sort((left, right) => Number(left.part_id) - Number(right.part_id));
  const submittedItems = [...payload.items]
    .map((item) => ({
      part_id: item.part_id,
      quantity: Number(item.quantity),
      note: item.note ?? null
    }))
    .sort((left, right) => left.part_id - right.part_id);

  return existingItems.every((item, index) => {
    const submitted = submittedItems[index];
    return (
      item.part_id === submitted.part_id &&
      item.quantity === submitted.quantity &&
      item.note === submitted.note
    );
  });
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

function statusLabel(status: ReservationStatus): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function reservationUnits(reservation: Reservation): number {
  return reservation.items.reduce(
    (total, item) => total + Number(item.quantity || 0),
    0
  );
}

function isDue(reservation: Reservation): boolean {
  if (!reservation.expiry_at) {
    return false;
  }
  const expiry = Date.parse(reservation.expiry_at);
  return Number.isFinite(expiry) && expiry <= Date.now();
}

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : "Unexpected request failure.";
}

function activityTitle(activity: ReservationActivityEntry): string {
  if (activity.kind === "stock_movement") {
    if (activity.movement_type === "reserve") {
      return "Stock reserved";
    }
    if (activity.movement_type === "release") {
      return "Reserved stock released";
    }
    if (activity.movement_type === "consume") {
      return "Reserved stock consumed";
    }
    return "Inventory movement";
  }

  const auditTitles: Record<string, string> = {
    "reservation.created": "Reservation created",
    "reservation.updated": "Reservation updated",
    "reservation.cancelled": "Reservation cancelled",
    "reservation.consumed": "Reservation consumed",
    "reservation.expired": "Reservation expired"
  };
  return auditTitles[activity.event_type] ?? "Reservation updated";
}

function activityActor(activity: ReservationActivityEntry): string {
  if (activity.actor_display_name) {
    return activity.actor_display_name;
  }
  if (activity.actor_type === "system") {
    return "System";
  }
  if (activity.actor_type) {
    return activity.actor_type.charAt(0).toUpperCase() + activity.actor_type.slice(1);
  }
  return "Unknown actor";
}

function activityPart(activity: ReservationActivityEntry): string | null {
  if (!activity.part_id) {
    return null;
  }
  return activity.part_number ?? activity.part_name ?? `Part #${activity.part_id}`;
}

function activityStockSummary(
  activity: ReservationActivityEntry
): string | null {
  if (activity.kind !== "stock_movement") {
    return null;
  }
  if (
    activity.reserved_quantity_before === null ||
    activity.reserved_quantity_after === null ||
    activity.available_quantity_before === null ||
    activity.available_quantity_after === null
  ) {
    return activity.quantity === null
      ? null
      : `${activity.quantity} units`;
  }
  return [
    `Reserved ${activity.reserved_quantity_before} → ${activity.reserved_quantity_after}`,
    `Available ${activity.available_quantity_before} → ${activity.available_quantity_after}`
  ].join(" · ");
}

type ReservationLifecycleAction = "cancel" | "consume" | "expire";

export function Reservations() {
  const { token, timezone } = useAuth();

  const [collection, setCollection] = useState<ReservationCollection>({
    total: 0,
    limit: PAGE_SIZE,
    offset: 0,
    reservations: []
  });
  const [statusFilter, setStatusFilter] =
    useState<ReservationStatus | "all">(readReservationStatusPreference);
  const [searchQuery, setSearchQuery] = useState("");
  const [pageOffset, setPageOffset] = useState(0);
  const [reloadVersion, setReloadVersion] = useState(0);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedReservation, setSelectedReservation] =
    useState<Reservation | null>(null);
  const [activityCollection, setActivityCollection] =
    useState<ReservationActivityCollection>({
      reservation_id: 0,
      total: 0,
      limit: 100,
      offset: 0,
      activities: []
    });
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityError, setActivityError] = useState("");
  const [activityReloadVersion, setActivityReloadVersion] = useState(0);

  const [listLoading, setListLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [listError, setListError] = useState("");
  const [detailError, setDetailError] = useState("");

const [actionName, setActionName] =
  useState<ReservationLifecycleAction | null>(null);
const [actionReservationId, setActionReservationId] =
  useState<number | null>(null);
const [actionSubmitting, setActionSubmitting] = useState(false);
const [actionError, setActionError] = useState("");
const [actionNotice, setActionNotice] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Reservation | null>(null);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [deletionNotice, setDeletionNotice] = useState("");

  const [createOpen, setCreateOpen] = useState(false);
  const [editingReservationId, setEditingReservationId] = useState<number | null>(
    null
  );
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState("");
  const [draftLabel, setDraftLabel] = useState("");
  const [draftNotes, setDraftNotes] = useState("");
  const [draftExpiry, setDraftExpiry] = useState("");
  const [draftItems, setDraftItems] = useState<DraftItem[]>([]);
  const [partQuery, setPartQuery] = useState("");
  const [partOptions, setPartOptions] = useState<ReservablePart[]>([]);
  const [partSearchLoading, setPartSearchLoading] = useState(false);
  const [partSearchError, setPartSearchError] = useState("");

  const listRequest = useRef(0);
  const detailRequest = useRef(0);
  const activityRequest = useRef(0);
  const expiryInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!token) {
      setCollection({
        total: 0,
        limit: PAGE_SIZE,
        offset: 0,
        reservations: []
      });
      setSelectedId(null);
      setSelectedReservation(null);
      setListLoading(false);
      return;
    }

    const controller = new AbortController();
    const requestId = ++listRequest.current;
    setListLoading(true);
    setListError("");

    void getReservations(token, {
      status: statusFilter === "all" ? undefined : statusFilter,
      limit: PAGE_SIZE,
      offset: pageOffset,
      signal: controller.signal
    })
      .then((nextCollection) => {
        if (requestId !== listRequest.current) {
          return;
        }
        setCollection(nextCollection);
        setSelectedId((current) => {
          if (
            current !== null &&
            nextCollection.reservations.some(
              (reservation) => reservation.id === current
            )
          ) {
            return current;
          }
          if (window.matchMedia("(max-width: 900px)").matches) {
            return null;
          }
          return nextCollection.reservations[0]?.id ?? null;
        });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          (error instanceof DOMException && error.name === "AbortError")
        ) {
          return;
        }
        if (requestId === listRequest.current) {
          setListError(messageFrom(error));
        }
      })
      .finally(() => {
        if (requestId === listRequest.current) {
          setListLoading(false);
        }
      });

    return () => controller.abort();
  }, [pageOffset, reloadVersion, statusFilter, token]);

  useEffect(() => {
    if (!token || selectedId === null) {
      setSelectedReservation(null);
      setDetailLoading(false);
      return;
    }

    const controller = new AbortController();
    const requestId = ++detailRequest.current;
    setDetailLoading(true);
    setDetailError("");
    setActionError("");

    void getReservation(token, selectedId, controller.signal)
      .then((reservation) => {
        if (requestId === detailRequest.current) {
          setSelectedReservation(reservation);
        }
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          (error instanceof DOMException && error.name === "AbortError")
        ) {
          return;
        }
        if (requestId === detailRequest.current) {
          setDetailError(messageFrom(error));
          setSelectedReservation(null);
        }
      })
      .finally(() => {
        if (requestId === detailRequest.current) {
          setDetailLoading(false);
        }
      });

    return () => controller.abort();
  }, [selectedId, token]);

useEffect(() => {
    if (!token || selectedId === null) {
      setActivityCollection({
        reservation_id: 0,
        total: 0,
        limit: 100,
        offset: 0,
        activities: []
      });
      setActivityLoading(false);
      setActivityError("");
      return;
    }

    const controller = new AbortController();
    const requestId = ++activityRequest.current;
    setActivityLoading(true);
    setActivityError("");

    void getReservationActivity(token, selectedId, controller.signal)
      .then((nextActivity) => {
        if (requestId === activityRequest.current) {
          setActivityCollection(nextActivity);
        }
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          (error instanceof DOMException && error.name === "AbortError")
        ) {
          return;
        }
        if (requestId === activityRequest.current) {
          setActivityError(messageFrom(error));
          setActivityCollection({
            reservation_id: selectedId,
            total: 0,
            limit: 100,
            offset: 0,
            activities: []
          });
        }
      })
      .finally(() => {
        if (requestId === activityRequest.current) {
          setActivityLoading(false);
        }
      });

    return () => controller.abort();
  }, [activityReloadVersion, selectedId, token]);

  useEffect(() => {
    if (!createOpen || !token) {
      return;
    }
    const query = partQuery.trim();
    if (query.length < 2) {
      setPartOptions([]);
      setPartSearchLoading(false);
      setPartSearchError("");
      return;
    }

    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      setPartSearchLoading(true);
      setPartSearchError("");
      void searchReservableParts(token, query, controller.signal)
        .then(setPartOptions)
        .catch((error: unknown) => {
          if (
            controller.signal.aborted ||
            (error instanceof DOMException && error.name === "AbortError")
          ) {
            return;
          }
          setPartSearchError(messageFrom(error));
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setPartSearchLoading(false);
          }
        });
    }, 280);

    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [createOpen, partQuery, token]);

  useEffect(() => {
    if (!createOpen) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !createSubmitting) {
        setCreateOpen(false);
        setEditingReservationId(null);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [createOpen, createSubmitting]);


  useEffect(() => {
    if (!deleteTarget) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !deleteSubmitting) {
        setDeleteTarget(null);
        setDeleteConfirmation("");
        setDeleteError("");
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [deleteSubmitting, deleteTarget]);


useEffect(() => {
  if (actionName === null) {
    return;
  }
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === "Escape" && !actionSubmitting) {
      setActionName(null);
      setActionReservationId(null);
      setActionError("");
    }
  };
  window.addEventListener("keydown", onKeyDown);
  return () => window.removeEventListener("keydown", onKeyDown);
}, [actionName, actionSubmitting]);

  const visibleReservations = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) {
      return collection.reservations;
    }
    return collection.reservations.filter((reservation) => {
      const partText = reservation.items
        .map((item) => `${item.part_number ?? ""} ${item.part_name ?? ""}`)
        .join(" ");
      return [
        reservation.label,
        reservation.notes ?? "",
        reservation.created_by,
        partText
      ]
        .join(" ")
        .toLowerCase()
        .includes(query);
    });
  }, [collection.reservations, searchQuery]);

  const pageNumber = Math.floor(pageOffset / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(collection.total / PAGE_SIZE));
  const pageActiveCount = collection.reservations.filter(
    (reservation) => reservation.status === "active"
  ).length;
  const pageDueCount = collection.reservations.filter(
    (reservation) =>
      reservation.status === "active" && isDue(reservation)
  ).length;
  const pageReservedUnits = collection.reservations
    .filter((reservation) => reservation.status === "active")
    .reduce((total, reservation) => total + reservationUnits(reservation), 0);

const actionTarget =
  actionName !== null &&
  actionReservationId !== null &&
  selectedReservation?.id === actionReservationId
    ? selectedReservation
    : null;
const actionUnits = actionTarget ? reservationUnits(actionTarget) : 0;

  const chooseStatusFilter = (value: ReservationStatus | "all") => {
    writeReservationStatusPreference(value);
    setStatusFilter(value);
    setPageOffset(0);
    setSelectedId(null);
    setDeletionNotice("");
    setActionNotice("");
    setActionName(null);
    setActionReservationId(null);
    setActionError("");
  };

  const openDelete = () => {
    if (!selectedReservation || selectedReservation.status === "active") {
      return;
    }
    setDeleteTarget(selectedReservation);
    setDeleteConfirmation("");
    setDeleteError("");
    setDeletionNotice("");
  };

  const closeDelete = () => {
    if (!deleteSubmitting) {
      setDeleteTarget(null);
      setDeleteConfirmation("");
      setDeleteError("");
    }
  };

  const resetCreateForm = () => {
    setDraftLabel("");
    setDraftNotes("");
    setDraftExpiry("");
    setDraftItems([]);
    setPartQuery("");
    setPartOptions([]);
    setPartSearchError("");
    setCreateError("");
  };

  const openEdit = () => {
    if (!selectedReservation || selectedReservation.status !== "active") {
      return;
    }
    if (selectedReservation.items.some((item) => item.part_id === null)) {
      setActionNotice(
        "This reservation contains a deleted part and cannot be edited."
      );
      return;
    }

    resetCreateForm();
    setActionNotice("");
    setActionError("");
    setEditingReservationId(selectedReservation.id);
    setDraftLabel(selectedReservation.label);
    setDraftNotes(selectedReservation.notes ?? "");
    setDraftExpiry(toLocalDateTimeInput(selectedReservation.expiry_at));
    setDraftItems(
      selectedReservation.items.map((item) => {
        const partId = item.part_id as number;
        const availableQuantity = Math.max(
          0,
          Number(item.available_quantity ?? 0)
        );
        const originalQuantity = Math.max(1, Number(item.quantity));
        return {
          part: {
            id: partId,
            part_number: item.part_number ?? `Part #${partId}`,
            name: item.part_name ?? "Part name unavailable",
            total_quantity: Number(item.total_quantity ?? originalQuantity),
            reserved_quantity: Number(
              item.reserved_quantity ?? originalQuantity
            ),
            available_quantity: availableQuantity
          },
          quantity: originalQuantity,
          note: item.note ?? "",
          maxQuantity: availableQuantity + originalQuantity,
          originalQuantity
        };
      })
    );
    setCreateOpen(true);
  };

  const closeCreate = () => {
    if (!createSubmitting) {
      setCreateOpen(false);
      setEditingReservationId(null);
    }
  };

  const openExpiryPicker = () => {
    const input = expiryInputRef.current;
    if (!input) {
      return;
    }
    const pickerInput = input as HTMLInputElement & {
      showPicker?: () => void;
    };
    try {
      if (pickerInput.showPicker) {
        pickerInput.showPicker();
      } else {
        input.focus();
      }
    } catch {
      input.focus();
    }
  };

  const addDraftItem = (part: ReservablePart) => {
    setDraftItems((current) => {
      if (current.some((item) => item.part.id === part.id)) {
        return current;
      }
      return [
        ...current,
        {
          part,
          quantity: 1,
          note: "",
          maxQuantity: part.available_quantity,
          originalQuantity: 0
        }
      ];
    });
  };

  const updateDraftQuantity = (partId: number, quantity: number) => {
    setDraftItems((current) =>
      current.map((item) =>
        item.part.id === partId
          ? {
              ...item,
              quantity: Math.max(
                1,
                Math.min(
                  Number.isFinite(quantity) ? quantity : 1,
                  item.maxQuantity
                )
              )
            }
          : item
      )
    );
  };

  const updateDraftNote = (partId: number, note: string) => {
    setDraftItems((current) =>
      current.map((item) =>
        item.part.id === partId ? { ...item, note } : item
      )
    );
  };

  const removeDraftItem = (partId: number) => {
    setDraftItems((current) =>
      current.filter((item) => item.part.id !== partId)
    );
  };

  const submitReservation = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || createSubmitting) {
      return;
    }
    if (!draftLabel.trim()) {
      setCreateError("A reservation label is required.");
      return;
    }
    if (draftItems.length === 0) {
      setCreateError("Add at least one available part.");
      return;
    }

    let expiryAt: string | null = null;
    if (draftExpiry) {
      const parsed = new Date(draftExpiry);
      if (Number.isNaN(parsed.getTime())) {
        setCreateError("Enter a valid expiry date and time.");
        return;
      }
      if (parsed.getTime() <= Date.now()) {
        setCreateError("Expiry must be in the future.");
        return;
      }
      expiryAt = parsed.toISOString();
    }

    if (
      editingReservationId === null ||
      selectedReservation?.id !== editingReservationId
    ) {
      setCreateError(
        "Manual Reservation creation is disabled. Start new work in Projects."
      );
      return;
    }

    const payload: ReservationUpdatePayload = {
      label: draftLabel.trim(),
      notes: draftNotes.trim() || null,
      expiry_at: expiryAt,
      items: draftItems.map((item) => ({
        part_id: item.part.id,
        quantity: item.quantity,
        note: item.note.trim() || null
      }))
    };

    if (reservationMatchesPayload(selectedReservation, payload)) {
      setCreateOpen(false);
      setEditingReservationId(null);
      resetCreateForm();
      return;
    }

    setCreateSubmitting(true);
    setCreateError("");
    try {
      const saved = await updateReservation(
        token,
        editingReservationId,
        payload
      );
      setCreateOpen(false);
      setEditingReservationId(null);
      resetCreateForm();
      setSelectedId(saved.id);
      setSelectedReservation(saved);
      setActionNotice(
        saved.project_id !== null
          ? `Updated Reservation and linked Project #${saved.project_id}.`
          : "Reservation updated."
      );
      setReloadVersion((value) => value + 1);
      setActivityReloadVersion((value) => value + 1);
    } catch (error: unknown) {
      setCreateError(messageFrom(error));
    } finally {
      setCreateSubmitting(false);
    }
  };

  const submitDelete = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !deleteTarget || deleteSubmitting) {
      return;
    }
    if (deleteTarget.status === "active") {
      setDeleteError("Active reservations must be completed or cancelled first.");
      return;
    }
    if (deleteConfirmation.trim() !== deleteTarget.label) {
      setDeleteError("Type the reservation label exactly to confirm deletion.");
      return;
    }

    setDeleteSubmitting(true);
    setDeleteError("");
    try {
      const deleted = await deleteReservation(token, deleteTarget.id, {
        confirmation_label: deleteConfirmation
      });
      setDeleteTarget(null);
      setDeleteConfirmation("");
      setSelectedId(null);
      setSelectedReservation(null);
      setDeletionNotice(
        `Deleted "${deleted.label}". ${deleted.removed_item_count} ` +
          `${deleted.removed_item_count === 1 ? "item" : "items"} removed; ` +
          `${deleted.detached_movement_count} inventory ` +
          `${deleted.detached_movement_count === 1 ? "movement" : "movements"} retained.`
      );
      if (collection.reservations.length <= 1 && pageOffset > 0) {
        setPageOffset((value) => Math.max(0, value - PAGE_SIZE));
      } else {
        setReloadVersion((value) => value + 1);
      }
    } catch (error: unknown) {
      setDeleteError(messageFrom(error));
    } finally {
      setDeleteSubmitting(false);
    }
  };


const openAction = (action: ReservationLifecycleAction) => {
  if (
    !selectedReservation ||
    selectedReservation.status !== "active" ||
    actionSubmitting
  ) {
    return;
  }
  setActionNotice("");
  setActionError("");
  setActionReservationId(selectedReservation.id);
  setActionName(action);
};

const closeAction = () => {
  if (!actionSubmitting) {
    setActionName(null);
    setActionReservationId(null);
    setActionError("");
  }
};

const runAction = async () => {
  if (
    !token ||
    !actionTarget ||
    actionName === null ||
    actionSubmitting
  ) {
    return;
  }

  const action = actionName;
  const target = actionTarget;
  setActionSubmitting(true);
  setActionError("");
  try {
    const updated =
      action === "cancel"
        ? await cancelReservation(token, target.id)
        : action === "consume"
          ? await consumeReservation(token, target.id)
          : await expireReservation(token, target.id);
    setSelectedReservation(updated);
    setActionName(null);
    setActionReservationId(null);
    setActionNotice(
      `${updated.label} is now ${statusLabel(updated.status)}.${
        updated.project_id !== null
          ? ` Linked Project #${updated.project_id} was synchronised.`
          : ""
      }`
    );
    setReloadVersion((value) => value + 1);
    setActivityReloadVersion((value) => value + 1);
  } catch (error: unknown) {
    const originalMessage = messageFrom(error);
    try {
      const latest = await getReservation(token, target.id);
      if (
        latest.status !== target.status ||
        latest.updated_at !== target.updated_at
      ) {
        setSelectedReservation(latest);
        setActionName(null);
        setActionReservationId(null);
        setActionNotice(
          `${latest.label} changed to ${statusLabel(
            latest.status
          )} in another tab. The latest state has been loaded; no duplicate action was applied.`
        );
        setReloadVersion((value) => value + 1);
        setActivityReloadVersion((value) => value + 1);
      } else {
        setActionError(originalMessage);
      }
    } catch {
      setActionError(originalMessage);
    }
  } finally {
    setActionSubmitting(false);
  }
};

  return (
    <section
      className="page-stack reservations-page"
      data-partpilot-marker="PARTPILOT:RESERVATIONS_WORKSPACE:V322"
      data-partpilot-mobile-landing="PARTPILOT:MOBILE_RESERVATION_LANDING:V343"
      data-partpilot-reservation-edit="PARTPILOT:RESERVATION_EDIT_FRONTEND:V347"
      data-partpilot-reservation-noop="PARTPILOT:RESERVATION_NOOP_FIX:V348"
      data-partpilot-reservation-delete="PARTPILOT:RESERVATION_DELETE_FRONTEND:V352"
      data-partpilot-reservation-preference="PARTPILOT:RESERVATION_STATUS_PREFERENCE:V352"
      data-partpilot-reservation-layout="PARTPILOT:RESERVATION_LAYOUT_REFINEMENT:V353"
      data-partpilot-reservation-default-expiry="PARTPILOT:RESERVATION_DEFAULT_EXPIRY:V362"
      data-partpilot-reservation-action-dialog="PARTPILOT:RESERVATION_ACTION_DIALOG:V399"
      data-partpilot-compact-summary="PARTPILOT:COMPACT_MOBILE_SUMMARY:V399"
      data-partpilot-linked-reservation-edit="PARTPILOT:LINKED_RESERVATION_EDIT_UI:V402"
      data-partpilot-lifecycle-information="PARTPILOT:LIFECYCLE_INFORMATION_HIERARCHY:V402"
    >
      <header
        className="reservations-header"
        data-partpilot-marker="PARTPILOT:PROJECT_DERIVED_RESERVATIONS:V386"
      >
        <div className="page-header">
          <p className="eyebrow">Operational inventory commitments</p>
          <h1>Reservations</h1>
          <p>
            Review stock committed by Reserved Projects, adjust active holds,
            and complete them through consumption, cancellation, or expiry.
            Plan new work in Projects first.
          </p>
        </div>
        <a
          className="reservations-button reservations-button-primary"
          href="/projects"
        >
          Plan in Projects
        </a>
      </header>

      <div className="reservations-summary" aria-label="Reservation summary">
        <article>
          <span>Total results</span>
          <strong>{collection.total}</strong>
        </article>
        <article>
          <span>Active on page</span>
          <strong>{pageActiveCount}</strong>
        </article>
        <article>
          <span>Due on page</span>
          <strong>{pageDueCount}</strong>
        </article>
        <article>
          <span>Reserved units on page</span>
          <strong>{pageReservedUnits}</strong>
        </article>
      </div>

      <div className="reservations-toolbar">
        <div
          className="reservations-status-tabs"
          role="group"
          aria-label="Filter reservations by status"
        >
          {STATUS_OPTIONS.map((option) => (
            <button
              className={
                statusFilter === option.value
                  ? "reservations-status-tab is-active"
                  : "reservations-status-tab"
              }
              key={option.value}
              type="button"
              onClick={() => chooseStatusFilter(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
        <label className="reservations-search">
          <span className="sr-only">Search loaded reservations</span>
          <input
            type="search"
            value={searchQuery}
            onChange={(event: ChangeEvent<HTMLInputElement>) =>
              setSearchQuery(event.currentTarget.value)
            }
            placeholder="Search this page"
          />
        </label>
        <button
          className="reservations-button"
          type="button"
          onClick={() => setReloadVersion((value) => value + 1)}
          disabled={listLoading}
        >
          Refresh
        </button>
      </div>

      {listError ? (
        <div className="reservations-notice is-error" role="alert">
          <strong>Reservations could not be loaded.</strong>
          <span>{listError}</span>
        </div>
      ) : null}

      {deletionNotice ? (
        <div className="reservations-notice is-success" role="status">
          <strong>Reservation deleted.</strong>
          <span>{deletionNotice}</span>
        </div>
      ) : null}

      <div className="reservations-workspace">
        <section className="reservations-list-panel" aria-label="Reservations">
          <div className="reservations-list-heading">
            <div>
              <strong>Reservation register</strong>
              <span>
                Page {pageNumber} of {pageCount}
              </span>
            </div>
            <span>
              {visibleReservations.length} shown
            </span>
          </div>

          <div className="reservations-list-columns" aria-hidden="true">
            <span>Reservation</span>
            <span>Status</span>
            <span>Units</span>
            <span>Updated</span>
          </div>

          <div className="reservations-list" aria-live="polite">
            {listLoading ? (
              <div className="reservations-list-state">
                Loading reservations…
              </div>
            ) : visibleReservations.length === 0 ? (
              <div className="reservations-list-state">
                <strong>No matching reservations</strong>
                <span>
                  Change the status filter, clear the page search, or create a
                  reservation.
                </span>
              </div>
            ) : (
              visibleReservations.map((reservation) => (
                <button
                  className={
                    selectedId === reservation.id
                      ? "reservation-row is-selected"
                      : "reservation-row"
                  }
                  key={reservation.id}
                  type="button"
                  aria-pressed={selectedId === reservation.id}
                  onClick={() => setSelectedId(reservation.id)}
                >
                  <span className="reservation-row-main">
                    <strong>{reservation.label}</strong>
                    <small>
                      {reservation.items.length} part
                      {reservation.items.length === 1 ? "" : "s"}
                      {" · "}
                      {reservation.expiry_at
                        ? `Expires ${formatDate(reservation.expiry_at, timezone)}`
                        : "No expiry"}
                    </small>
                  </span>
                  <span
                    className={`reservation-status is-${reservation.status}`}
                  >
                    {statusLabel(reservation.status)}
                  </span>
                  <span className="reservation-row-number">
                    {reservationUnits(reservation)}
                  </span>
                  <span className="reservation-row-date">
                    {formatDate(reservation.updated_at, timezone)}
                  </span>
                </button>
              ))
            )}
          </div>

          <footer className="reservations-pagination">
            <button
              className="reservations-button"
              type="button"
              disabled={pageOffset === 0 || listLoading}
              onClick={() =>
                setPageOffset((value) => Math.max(0, value - PAGE_SIZE))
              }
            >
              Previous
            </button>
            <span>
              {collection.total === 0
                ? "0 results"
                : `${pageOffset + 1}–${Math.min(
                    pageOffset + PAGE_SIZE,
                    collection.total
                  )} of ${collection.total}`}
            </span>
            <button
              className="reservations-button"
              type="button"
              disabled={
                pageOffset + PAGE_SIZE >= collection.total || listLoading
              }
              onClick={() => setPageOffset((value) => value + PAGE_SIZE)}
            >
              Next
            </button>
          </footer>
        </section>

        <aside className="reservation-detail-panel">
          {detailLoading ? (
            <div className="reservation-detail-state">
              Loading reservation details…
            </div>
          ) : detailError ? (
            <div className="reservation-detail-state is-error" role="alert">
              <strong>Reservation details could not be loaded.</strong>
              <span>{detailError}</span>
            </div>
          ) : !selectedReservation ? (
            <div
              className="reservation-detail-empty"
              data-partpilot-marker="PARTPILOT:RESERVATION_DETAIL_EMPTY:V353"
            >
              <div className="reservation-detail-empty-copy">
                <span>Reservation detail</span>
                <h2>No reservation selected</h2>
                <p>
                  Choose a record from the register to inspect its committed
                  inventory, timing, value, activity, and available actions.
                </p>
              </div>
              <dl className="reservation-detail-empty-map" aria-hidden="true">
                <div>
                  <dt>Parts</dt>
                  <dd>Committed quantities</dd>
                </div>
                <div>
                  <dt>Timing</dt>
                  <dd>Creation and expiry</dd>
                </div>
                <div>
                  <dt>Value</dt>
                  <dd>Reserved cost snapshot</dd>
                </div>
                <div>
                  <dt>Activity</dt>
                  <dd>Lifecycle and stock events</dd>
                </div>
              </dl>
            </div>
          ) : (
            <>
              <div className="reservation-detail-header">
                <div>
                  <span
                    className={`reservation-status is-${selectedReservation.status}`}
                  >
                    {statusLabel(selectedReservation.status)}
                  </span>
                  <h2>{selectedReservation.label}</h2>
                  <p>
                    Reservation #{selectedReservation.id}
                    {" · "}
                    Created {formatDate(selectedReservation.created_at, timezone)}
                  </p>
                </div>
                <button
                  className="reservations-button reservations-close-mobile"
                  type="button"
                  onClick={() => setSelectedId(null)}
                >
                  Close
                </button>
              </div>

              {actionNotice ? (
                <div
                  className="reservations-notice is-success reservation-action-notice"
                  role="status"
                  aria-live="polite"
                >
                  <span>{actionNotice}</span>
                </div>
              ) : null}

              <dl className="reservation-facts">
                <div>
                  <dt>Expiry</dt>
                  <dd>{formatDate(selectedReservation.expiry_at, timezone)}</dd>
                </div>
                <div>
                  <dt>Reserved value</dt>
                  <dd>
                    {formatMoney(
                      selectedReservation.estimated_reserved_value,
                      selectedReservation.currency_snapshot
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Created by</dt>
                  <dd>{selectedReservation.created_by}</dd>
                </div>
                <div>
                  <dt>Linked project</dt>
                  <dd>
                    {selectedReservation.project_id
                      ? `#${selectedReservation.project_id}`
                      : "Not linked"}
                  </dd>
                </div>
              </dl>

              {selectedReservation.notes ? (
                <div className="reservation-notes">
                  <span>Notes</span>
                  <p>{selectedReservation.notes}</p>
                </div>
              ) : null}

              <div className="reservation-items-heading">
                <div>
                  <strong>Reserved parts</strong>
                  <span>{reservationUnits(selectedReservation)} units</span>
                </div>
              </div>

              <div className="reservation-items">
                {selectedReservation.items.map((item) => (
                  <article className="reservation-item" key={item.id}>
                    <div className="reservation-item-main">
                      <strong>
                        {item.part_number ?? item.part_name ?? "Deleted part"}
                      </strong>
                      <span>
                        {item.part_number
                          ? item.part_name ?? "Part name unavailable"
                          : item.part_id === null
                            ? "Part no longer available"
                            : "Inventory part"}
                      </span>
                    </div>
                    <dl>
                      <div>
                        <dt>Reserved</dt>
                        <dd>{item.quantity}</dd>
                      </div>
                      <div>
                        <dt>Physical</dt>
                        <dd>{item.total_quantity ?? "—"}</dd>
                      </div>
                      <div>
                        <dt>Available</dt>
                        <dd>{item.available_quantity ?? "—"}</dd>
                      </div>
                    </dl>
                    {item.note ? <p>{item.note}</p> : null}
                  </article>
                ))}
              </div>

<section
                className="reservation-activity"
                aria-labelledby={`reservation-${selectedReservation.id}-activity-title`}
                data-partpilot-marker="PARTPILOT:RESERVATION_ACTIVITY_PANEL:V340"
              >
                <header className="reservation-activity-heading">
                  <div>
                    <strong
                      id={`reservation-${selectedReservation.id}-activity-title`}
                    >
                      Activity
                    </strong>
                    <span>
                      {activityCollection.total}{" "}
                      {activityCollection.total === 1 ? "event" : "events"}
                    </span>
                  </div>
                </header>

                {activityLoading ? (
                  <div className="reservation-activity-state" aria-live="polite">
                    Loading reservation activity…
                  </div>
                ) : activityError ? (
                  <div
                    className="reservation-activity-state is-error"
                    role="alert"
                  >
                    <strong>Activity could not be loaded.</strong>
                    <span>{activityError}</span>
                    <button
                      className="reservations-button"
                      type="button"
                      onClick={() =>
                        setActivityReloadVersion((value) => value + 1)
                      }
                    >
                      Retry
                    </button>
                  </div>
                ) : activityCollection.activities.length === 0 ? (
                  <div className="reservation-activity-state">
                    No activity has been recorded for this reservation.
                  </div>
                ) : (
                  <ol className="reservation-activity-list">
                    {activityCollection.activities.map((activity) => {
                      const partLabel = activityPart(activity);
                      const stockSummary = activityStockSummary(activity);
                      return (
                        <li key={activity.key}>
                          <article className="reservation-activity-entry">
                            <div className="reservation-activity-entry-header">
                              <strong>{activityTitle(activity)}</strong>
                              <time dateTime={activity.occurred_at}>
                                {formatDate(activity.occurred_at, timezone)}
                              </time>
                            </div>
                            {activity.summary ? (
                              <p>{activity.summary}</p>
                            ) : null}
                            <div className="reservation-activity-meta">
                              <span>{activityActor(activity)}</span>
                              {partLabel ? <span>{partLabel}</span> : null}
                            </div>
                            {stockSummary ? (
                              <div className="reservation-activity-stock">
                                {stockSummary}
                              </div>
                            ) : null}
                          </article>
                        </li>
                      );
                    })}
                  </ol>
                )}
              </section>


{selectedReservation.status === "active" ? (
  <div className="reservation-actions">
    <button
      className="reservations-button reservations-button-primary"
      type="button"
      disabled={actionSubmitting}
      onClick={() => openAction("consume")}
    >
      Consume reservation
    </button>
    <button
      className="reservations-button"
      type="button"
      disabled={actionSubmitting}
      onClick={openEdit}
    >
      Edit reservation
    </button>
    <button
      className="reservations-button"
      type="button"
      disabled={actionSubmitting}
      onClick={() => openAction("cancel")}
    >
      Cancel
    </button>
    {isDue(selectedReservation) ? (
      <button
        className="reservations-button"
        type="button"
        disabled={actionSubmitting}
        onClick={() => openAction("expire")}
      >
        Mark expired
      </button>
    ) : null}
  </div>
) : (                <div className="reservation-actions">
                  <button
                    className="reservations-button reservations-button-danger"
                    type="button"
                    onClick={openDelete}
                  >
                    Delete reservation
                  </button>
                </div>
              )}
            </>
          )}
        </aside>
      </div>


{actionTarget && actionName ? (
  <div
    className="reservation-modal-backdrop"
    role="presentation"
    onMouseDown={(event: MouseEvent<HTMLDivElement>) => {
      if (event.target === event.currentTarget) {
        closeAction();
      }
    }}
  >
    <section
      className={`reservation-modal reservation-action-modal is-${actionName}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="reservation-action-title"
      aria-describedby="reservation-action-description"
      aria-busy={actionSubmitting}
      data-partpilot-marker="PARTPILOT:RESERVATION_ACTION_DIALOG:V399"
    >
      <header>
        <div>
          <p className="eyebrow">
            {actionName === "consume"
              ? "Permanent stock movement"
              : actionName === "expire"
                ? "Due reservation release"
                : "Release inventory commitment"}
          </p>
          <h2 id="reservation-action-title">
            {actionName === "consume"
              ? "Consume reservation"
              : actionName === "expire"
                ? "Mark reservation expired"
                : "Cancel reservation"}
          </h2>
          <p id="reservation-action-description">
            {actionName === "consume"
              ? "Confirm the permanent removal of the physical stock committed to this Reservation."
              : "Confirm that this Reservation should release its committed stock without changing physical totals."}
          </p>
        </div>
        <button
          className="reservations-button"
          type="button"
          disabled={actionSubmitting}
          onClick={closeAction}
        >
          Close
        </button>
      </header>

      <div className="reservation-action-body">
        <div className="reservation-action-summary">
          <article>
            <span>Reservation</span>
            <strong>{actionTarget.label}</strong>
          </article>
          <article>
            <span>Parts</span>
            <strong>{actionTarget.items.length}</strong>
          </article>
          <article>
            <span>
              {actionName === "consume"
                ? "Units to remove"
                : "Units to release"}
            </span>
            <strong>{actionUnits}</strong>
          </article>
        </div>

        <div
          className={`reservation-action-impact is-${actionName}`}
        >
          <strong>Stock impact</strong>
          <p>
            {actionName === "consume"
              ? `Physical and reserved quantities both decrease by ${actionUnits}. Available quantity remains unchanged.`
              : `Reserved quantity decreases by ${actionUnits} and available quantity increases by the same amount. Physical stock remains unchanged.`}
          </p>
        </div>

        <div className="reservation-action-terminal-note">
          <strong>
            {actionName === "consume"
              ? "This stock removal cannot be undone from the Reservation."
              : actionName === "expire"
                ? "The Reservation will close as Expired."
                : "The Reservation will close as Cancelled."}
          </strong>
          <span>
            {actionTarget.project_id !== null
              ? `Linked Project #${actionTarget.project_id} will be synchronised atomically.`
              : "This Reservation is not linked to a Project."}
          </span>
        </div>

        {actionError ? (
          <div className="reservations-notice is-error" role="alert">
            <span>{actionError}</span>
          </div>
        ) : null}
      </div>

      <footer>
        <span>
          Current status, linked Project state, and inventory are
          checked again when you confirm.
        </span>
        <button
          autoFocus
          className={`reservations-button ${
            actionName === "consume"
              ? "reservations-button-danger"
              : "reservations-button-primary"
          }`}
          type="button"
          disabled={actionSubmitting}
          onClick={() => void runAction()}
        >
          {actionSubmitting
            ? actionName === "consume"
              ? "Consuming…"
              : actionName === "expire"
                ? "Expiring…"
                : "Cancelling…"
            : actionName === "consume"
              ? "Consume physical stock"
              : actionName === "expire"
                ? "Release and mark expired"
                : "Release reserved stock"}
        </button>
      </footer>
    </section>
  </div>
) : null}

      {deleteTarget ? (
        <div
          className="reservation-modal-backdrop"
          role="presentation"
          onMouseDown={(event: MouseEvent<HTMLDivElement>) => {
            if (event.target === event.currentTarget) {
              closeDelete();
            }
          }}
        >
          <section
            className="reservation-modal reservation-delete-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="reservation-delete-title"
            aria-describedby="reservation-delete-description"
            data-partpilot-marker="PARTPILOT:RESERVATION_DELETE_MODAL:V352"
          >
            <header>
              <div>
                <p className="eyebrow">Permanent record removal</p>
                <h2 id="reservation-delete-title">Delete reservation</h2>
                <p id="reservation-delete-description">
                  This removes the reservation and its item records. Inventory
                  movements and audit history are retained for History.
                </p>
              </div>
              <button
                className="reservations-button"
                type="button"
                onClick={closeDelete}
                disabled={deleteSubmitting}
              >
                Close
              </button>
            </header>

            <form onSubmit={(event) => void submitDelete(event)}>
              <div className="reservation-delete-warning">
                <strong>This action cannot be undone.</strong>
                <span>
                  {statusLabel(deleteTarget.status)} reservation #{deleteTarget.id}
                </span>
              </div>

              <label className="reservation-delete-confirmation">
                <span>
                  Type <strong>{deleteTarget.label}</strong> to confirm
                </span>
                <input
                  autoFocus
                  required
                  maxLength={180}
                  autoComplete="off"
                  spellCheck={false}
                  value={deleteConfirmation}
                  onChange={(event: ChangeEvent<HTMLInputElement>) => {
                    setDeleteConfirmation(event.currentTarget.value);
                    setDeleteError("");
                  }}
                  placeholder={deleteTarget.label}
                />
              </label>

              {deleteError ? (
                <div className="reservations-notice is-error" role="alert">
                  <span>{deleteError}</span>
                </div>
              ) : null}

              <footer>
                <button
                  className="reservations-button"
                  type="button"
                  onClick={closeDelete}
                  disabled={deleteSubmitting}
                >
                  Cancel
                </button>
                <button
                  className="reservations-button reservations-button-danger"
                  type="submit"
                  disabled={
                    deleteSubmitting ||
                    deleteConfirmation.trim() !== deleteTarget.label
                  }
                >
                  {deleteSubmitting ? "Deleting…" : "Delete permanently"}
                </button>
              </footer>
            </form>
          </section>
        </div>
      ) : null}

      {createOpen ? (
        <div
          className="reservation-modal-backdrop"
          role="presentation"
          onMouseDown={(event: MouseEvent<HTMLDivElement>) => {
            if (event.target === event.currentTarget) {
              closeCreate();
            }
          }}
        >
          <section
            className="reservation-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="reservation-form-title"
            data-partpilot-marker="PARTPILOT:RESERVATION_EDIT_MODAL:V347"
          >
            <header data-partpilot-marker="PARTPILOT:RESERVATION_SINGLE_DISMISS_ACTION:V364">
              <div>
                <p className="eyebrow">
                  {selectedReservation?.project_id !== null
                    ? "Two-way Project synchronization"
                    : "Update inventory commitment"}
                </p>
                <h2 id="reservation-form-title">
                  {selectedReservation?.project_id !== null
                    ? "Edit Project reservation"
                    : "Edit reservation"}
                </h2>
                <p>
                  {selectedReservation?.project_id !== null
                    ? "Changes update this active Reservation and its linked Reserved Project together. Quantity deltas adjust reserved and available stock while physical totals remain unchanged."
                    : "Adjust this active hold's details, parts, quantities, notes, or expiry. New commitments are created by reserving Projects."}
                </p>
              </div>
            </header>

            <form
              onSubmit={(event: FormEvent<HTMLFormElement>) =>
                void submitReservation(event)
              }
            >
              <div className="reservation-form-grid">
                <label>
                  <span>Label</span>
                  <input
                    required
                    maxLength={180}
                    value={draftLabel}
                    onChange={(event: ChangeEvent<HTMLInputElement>) =>
                      setDraftLabel(event.currentTarget.value)
                    }
                    placeholder="Prototype controller build"
                  />
                </label>
                <div
                  className="reservation-expiry-field"
                  data-partpilot-marker="PARTPILOT:RESERVATION_DATETIME_CONTROL:V348"
                >
                  <label htmlFor="reservation-expiry-input">Expiry</label>
                  <div className="reservation-datetime-control">
                    <input
                      id="reservation-expiry-input"
                      ref={expiryInputRef}
                      type="datetime-local"
                      value={draftExpiry}
                      onChange={(event: ChangeEvent<HTMLInputElement>) =>
                        setDraftExpiry(event.currentTarget.value)
                      }
                    />
                    <button
                      className="reservation-datetime-button"
                      type="button"
                      onClick={openExpiryPicker}
                      aria-label="Open date and time picker"
                      title="Choose date and time"
                    >
                      <svg
                        viewBox="0 0 24 24"
                        aria-hidden="true"
                        focusable="false"
                      >
                        <path d="M7 2v3M17 2v3M3.5 9h17M5.5 4h13a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" />
                        <path d="M8 13h3v3H8zM14 13h2" />
                      </svg>
                    </button>
                  </div>
                  <small>Optional · interpreted in your local time</small>
                </div>
                <label className="reservation-form-wide">
                  <span>Notes</span>
                  <textarea
                    rows={3}
                    maxLength={10000}
                    value={draftNotes}
                    onChange={(event: ChangeEvent<HTMLTextAreaElement>) =>
                      setDraftNotes(event.currentTarget.value)
                    }
                    placeholder="Optional context for this reservation"
                  />
                </label>
              </div>

              <div className="reservation-part-picker">
                <label>
                  <span>Find parts</span>
                  <input
                    type="search"
                    value={partQuery}
                    onChange={(event: ChangeEvent<HTMLInputElement>) =>
                      setPartQuery(event.currentTarget.value)
                    }
                    placeholder="Search part number, name, tag, or metadata"
                    autoComplete="off"
                  />
                </label>
                {partQuery.trim().length >= 2 ? (
                  <div
                    className="reservation-part-results"
                    aria-live="polite"
                    aria-label="Matching available inventory parts"
                  >
                    {partSearchLoading ? (
                      <span>Searching inventory…</span>
                    ) : partSearchError ? (
                      <span className="is-error">{partSearchError}</span>
                    ) : partOptions.length === 0 ? (
                      <span>No available matching parts.</span>
                    ) : (
                      <>
                        <div className="reservation-part-results-summary">
                          <strong>
                            {partOptions.length} matching available{" "}
                            {partOptions.length === 1 ? "part" : "parts"}
                          </strong>
                          <small>Showing up to 50 results</small>
                        </div>
                        {partOptions.map((part) => (
                          <button
                            key={part.id}
                            type="button"
                            onClick={() => addDraftItem(part)}
                            disabled={draftItems.some(
                              (item) => item.part.id === part.id
                            )}
                          >
                            <span>
                              <strong>{part.part_number}</strong>
                              <small>
                                {[part.name, part.manufacturer_name, part.location_name]
                                  .filter(Boolean)
                                  .join(" · ") || "No additional metadata"}
                              </small>
                            </span>
                            <span>{part.available_quantity} available</span>
                          </button>
                        ))}
                      </>
                    )}
                  </div>
                ) : (
                  <small className="reservation-part-search-hint">
                    Enter at least two characters to search inventory.
                  </small>
                )}
              </div>

              <div className="reservation-draft-items">
                <div className="reservation-draft-heading">
                  <strong>Reservation items</strong>
                  <span>{draftItems.length} selected</span>
                </div>
                {draftItems.length === 0 ? (
                  <div className="reservation-draft-empty">
                    Search and add one or more available parts.
                  </div>
                ) : (
                  draftItems.map((item) => (
                    <article key={item.part.id}>
                      <div>
                        <strong>{item.part.part_number}</strong>
                        <span>{item.part.name}</span>
                        <small>
                          {item.originalQuantity > 0
                            ? `${item.part.available_quantity} unreserved · ${item.maxQuantity} max here`
                            : `${item.part.available_quantity} available`}
                        </small>
                      </div>
                      <label>
                        <span>Quantity</span>
                        <input
                          type="number"
                          min={1}
                          max={item.maxQuantity}
                          value={item.quantity}
                          onChange={(event: ChangeEvent<HTMLInputElement>) =>
                            updateDraftQuantity(
                              item.part.id,
                              Number(event.currentTarget.value)
                            )
                          }
                        />
                      </label>
                      <label className="reservation-draft-note">
                        <span>Item note</span>
                        <input
                          maxLength={5000}
                          value={item.note}
                          onChange={(event: ChangeEvent<HTMLInputElement>) =>
                            updateDraftNote(
                              item.part.id,
                              event.currentTarget.value
                            )
                          }
                          placeholder="Optional"
                        />
                      </label>
                      <button
                        className="reservations-button"
                        type="button"
                        onClick={() => removeDraftItem(item.part.id)}
                      >
                        Remove
                      </button>
                    </article>
                  ))
                )}
              </div>

              {createError ? (
                <div className="reservations-notice is-error" role="alert">
                  <span>{createError}</span>
                </div>
              ) : null}

              <footer>
                <button
                  className="reservations-button"
                  type="button"
                  onClick={closeCreate}
                  disabled={createSubmitting}
                >
                  Cancel
                </button>
                <button
                  className="reservations-button reservations-button-primary"
                  type="submit"
                  disabled={
                    createSubmitting ||
                    editingReservationId === null ||
                    draftItems.length === 0
                  }
                >
                  {createSubmitting ? "Saving…" : "Save changes"}
                </button>
              </footer>
            </form>
          </section>
        </div>
      ) : null}
    </section>
  );
}
