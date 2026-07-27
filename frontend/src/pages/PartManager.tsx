// PATCH 067: custom part type creation workspace
import {
  useEffect,
  useMemo,
  useRef,
  useState } from "react";
import type {
  ChangeEvent,
  FormEvent } from "react";

import { useAuth } from "../auth/AuthContext";
import "./PartManager.css";
// PATCH 094: dynamic inventory Add Part modal
import { AddPartModal } from "../components/AddPartModal";
import { EditPartModal } from "../components/EditPartModal";
import { PartLifecycleModal } from "../components/PartLifecycleModal";
import {
  createPartType,
  getPartTypes,
  updatePartType,
  deletePartType,
} from "../services/partTypesClient";
// PATCH 110: basic inventory browsing collection
import {
  adjustPartQuantity,
  getPart,
  getPartMovements,
  getParts
} from "../services/partsClient";
import { getLocations } from "../services/locationsClient";
import { getSearchSettings } from "../services/settingsClient";
import type { LocationOption } from "../types/locations";
import type {
  Part,
  PartCollection,
  PartStockStatus,
  QuantityAdjustmentOperation,
  StockMovement
} from "../types/parts";
import type {
  CreatePartTypeFieldPayload,
  CreatePartTypePayload,
  PartType,
  PartTypeCollection,
  PartTypeField,
  PartTypeFieldKind,
  UpdatePartTypePayload,
} from "../types/partTypes";

type FilterMode = "all" | "builtin" | "custom";
type InventoryStockFilter = PartStockStatus;
const STORED_PARTS_SERVER_SEARCH_VERSION = "stored-parts-server-search-v233";

// PATCH 106: editor-only semantic field preset
type EditorFieldKind = PartTypeFieldKind | "manufacturer";

interface EditableField extends CreatePartTypeFieldPayload {
  id: number | null;
  client_id: string;
  options_text: string;
}

const FIELD_TYPES: Array<{
  value: PartTypeFieldKind;
  label: string;
  description: string;
}> = [
  { value: "text", label: "Text", description: "Names, codes, notes" },
  { value: "number", label: "Number", description: "Plain numeric value" },
  { value: "boolean", label: "Yes / No", description: "True or false state" },
  { value: "dropdown", label: "Dropdown", description: "Fixed option list" },
  { value: "url", label: "URL", description: "Datasheet or reference link" },
  {
    value: "unit_value",
    label: "Unit-aware value",
    description: "Value with a default unit"
  }
];

const EDITOR_FIELD_TYPES: Array<{
  value: EditorFieldKind;
  label: string;
  description: string;
}> = [
  ...FIELD_TYPES,
  {
    value: "manufacturer",
    label: "Manufacturer",
    description: "Reusable catalogue with inline creation"
  }
];

const FIELD_TYPE_LABELS: Record<string, string> = Object.fromEntries(
  FIELD_TYPES.map((item) => [item.value, item.label])
);

let fieldSequence = 0;

function createEditableField(): EditableField {
  fieldSequence += 1;
  return {
    id: null,
    client_id: `field-${Date.now()}-${fieldSequence}`,
    field_key: "",
    label: "",
    field_type: "text",
    is_required: false,
    options: [],
    options_text: "",
    default_unit: null,
    help_text: null
  };
}

function fieldKeyFromLabel(label: string): string {
  return label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .replace(/^[^a-z]+/, "");
}

// PATCH 106: Manufacturer remains text + reserved key in storage
function normalizeEditorFieldKey(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function isManufacturerEditorField(field: {
  field_key: string;
}): boolean {
  const key = normalizeEditorFieldKey(field.field_key);
  return key === "manufacturer" || key === "manufacturer_name";
}

function editorFieldKind(field: EditableField): EditorFieldKind {
  return isManufacturerEditorField(field)
    ? "manufacturer"
    : field.field_type;
}

function parseOptions(value: string): string[] {
  const result: string[] = [];
  const seen = new Set<string>();

  value.split(/[,\n]/).forEach((rawOption) => {
    const option = rawOption.trim().replace(/\s+/g, " ");
    const normalized = option.toLowerCase();
    if (!option || seen.has(normalized)) {
      return;
    }
    seen.add(normalized);
    result.push(option);
  });

  return result;
}

function fieldTypeLabel(fieldType: string): string {
  return FIELD_TYPE_LABELS[fieldType] ?? fieldType;
}

function fieldSummary(field: PartTypeField): string {
  const details: string[] = [];
  if (field.default_unit) {
    details.push(`Default unit: ${field.default_unit}`);
  }
  if (Array.isArray(field.options) && field.options.length > 0) {
    details.push(`${field.options.length} options`);
  }
  return details.join(" · ");
}

function previewInput(field: EditableField) {
  const placeholder = field.help_text?.trim() || field.label || "Field preview";

  if (isManufacturerEditorField(field)) {
    return (
      <select disabled defaultValue="">
        <option value="">Select or add a manufacturer</option>
      </select>
    );
  }

  if (field.field_type === "boolean") {
    return (
      <label className="creator-preview-boolean">
        <input type="checkbox" disabled />
        <span>Yes / enabled</span>
      </label>
    );
  }

  if (field.field_type === "dropdown") {
    const options = parseOptions(field.options_text);
    return (
      <select disabled defaultValue="">
        <option value="">Select an option</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    );
  }

  if (field.field_type === "unit_value") {
    return (
      <div className="creator-preview-unit">
        <input type="number" disabled placeholder={placeholder} />
        <span>{field.default_unit?.trim() || "unit"}</span>
      </div>
    );
  }

  return (
    <input
      type={
        field.field_type === "number"
          ? "number"
          : field.field_type === "url"
            ? "url"
            : "text"
      }
      disabled
      placeholder={placeholder}
    />
  );
}

// PATCH 110: basic inventory list presentation helpers
function inventoryPartName(part: Part): string {
  return part.name || part.part_number || `Part ${part.id}`;
}

function inventoryStockLabel(part: Part): string {
  if (part.available_quantity <= 0) {
    return "Out of stock";
  }
  if (part.is_low_stock) {
    return "Low stock";
  }
  return "In stock";
}

function inventoryStockClass(part: Part): string {
  if (part.available_quantity <= 0) {
    return "is-out";
  }
  if (part.is_low_stock) {
    return "is-low";
  }
  return "is-in";
}

// PATCH 124: read-only inventory detail helpers
// PATCH 127: trim database decimal padding without rounding
const PART_DETAIL_NUMBER_FORMAT_VERSION = "part-detail-number-format-v127";

function inventoryNumberDisplayValue(value: string): string {
  const normalized = value.trim();

  if (!/^-?\d+(?:\.\d+)?$/.test(normalized)) {
    return normalized;
  }

  const [integerPart, decimalPart] = normalized.split(".");
  if (!decimalPart) {
    return integerPart;
  }

  const trimmedDecimal = decimalPart.replace(/0+$/, "");
  return trimmedDecimal
    ? `${integerPart}.${trimmedDecimal}`
    : integerPart;
}

function inventoryFieldDisplayValue(
  field: Part["field_values"][number]
): string | null {
  if (field.value_bool !== null) {
    return field.value_bool ? "Yes" : "No";
  }
  if (field.value_number !== null) {
    const value = inventoryNumberDisplayValue(field.value_number);
    return `${value}${field.unit ? ` ${field.unit}` : ""}`;
  }
  return field.value_text || null;
}

function inventoryDateLabel(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString();
}

// PATCH 137: compact quantity adjustment and movement history UI
function movementTypeLabel(movement: StockMovement): string {
  if (movement.movement_type === "restock") {
    return "Stock added";
  }
  if (movement.movement_type === "consume") {
    return "Stock consumed";
  }
  if (movement.movement_type === "adjust") {
    return movement.quantity_delta < 0
      ? "Stock reduced"
      : "Stock corrected";
  }
  return movement.movement_type
    .replace(/_/g, " ")
    .replace(/^./, (character) => character.toUpperCase());
}

function movementDeltaLabel(quantityDelta: number): string {
  return quantityDelta > 0 ? `+${quantityDelta}` : String(quantityDelta);
}

function quantityOperationHint(
  operation: QuantityAdjustmentOperation,
  part: Part
): string {
  if (operation === "add") {
    return "Increase total stock by the entered quantity.";
  }
  if (operation === "remove") {
    return `Remove unreserved stock. ${part.available_quantity} available.`;
  }
  if (operation === "consume") {
    return `Record consumed stock. ${part.available_quantity} available.`;
  }
  return "Apply a signed correction, such as -2 or 3. A reason is required.";
}

interface PartManagerProps {
  inventoryOnly?: boolean;
}


export function PartManager({
  inventoryOnly = false
}: PartManagerProps) {
  const { token } = useAuth();
  const [collection, setCollection] = useState<PartTypeCollection | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [filter, setFilter] = useState<FilterMode>("all");
  const [query, setQuery] = useState("");
  // PATCH 110: inventory collection state
  const [inventoryCollection, setInventoryCollection] =
    useState<PartCollection | null>(null);
  const [inventoryLoading, setInventoryLoading] = useState(true);
  const [inventoryError, setInventoryError] =
    useState<string | null>(null);
  const [inventoryRefreshSequence, setInventoryRefreshSequence] =
    useState(0);
  // PATCH 232: PARTPILOT_STORED_PARTS_SERVER_SEARCH_V233
  const [inventoryQuery, setInventoryQuery] = useState("");
  const [inventoryServerSearch, setInventoryServerSearch] =
    useState("");
  const [inventoryStockFilter, setInventoryStockFilter] =
    useState<InventoryStockFilter>("all");
  const inventoryRequestSequence = useRef(0);
  // PATCH 194: settings-driven out-of-stock grouping
  const [showOutOfStockSection, setShowOutOfStockSection] =
    useState(true);
  const [
    inventorySearchSettingsError,
    setInventorySearchSettingsError
  ] = useState<string | null>(null);
  // PATCH 171: Stored Parts location display and filtering
  const [inventoryLocations, setInventoryLocations] =
    useState<LocationOption[]>([]);
  const [inventoryLocationsLoading, setInventoryLocationsLoading] =
    useState(true);
  const [inventoryLocationsError, setInventoryLocationsError] =
    useState<string | null>(null);
  const [inventoryLocationFilter, setInventoryLocationFilter] =
    useState<number | null>(null);
  // PATCH 124: selected inventory record and drawer state
  const [selectedInventoryPartId, setSelectedInventoryPartId] =
    useState<number | null>(null);
  const [selectedInventoryPart, setSelectedInventoryPart] =
    useState<Part | null>(null);
  const [partDetailsLoading, setPartDetailsLoading] = useState(false);
  const [partDetailsError, setPartDetailsError] =
    useState<string | null>(null);
  const [partMovements, setPartMovements] = useState<StockMovement[]>([]);
  const [partMovementsLoading, setPartMovementsLoading] = useState(false);
  const [partMovementsError, setPartMovementsError] =
    useState<string | null>(null);
  const [adjustmentOperation, setAdjustmentOperation] =
    useState<QuantityAdjustmentOperation>("add");
  const [adjustmentQuantity, setAdjustmentQuantity] = useState("");
  const [adjustmentReason, setAdjustmentReason] = useState("");
  const [adjustmentNote, setAdjustmentNote] = useState("");
  const [adjustmentSaving, setAdjustmentSaving] = useState(false);
  const [adjustmentError, setAdjustmentError] =
    useState<string | null>(null);
  const [adjustmentSuccess, setAdjustmentSuccess] =
    useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isCreating, setIsCreating] = useState(false);
  const [editingTypeId, setEditingTypeId] = useState<number | null>(null);
  const [typeName, setTypeName] = useState("");
  const [typeDescription, setTypeDescription] = useState("");
  const [editableFields, setEditableFields] = useState<EditableField[]>([]);
  const [creatorError, setCreatorError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] =
    useState<PartType | null>(null);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [deleteError, setDeleteError] =
    useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  // PATCH 094: Add Part modal state
  const [isAddingPart, setIsAddingPart] = useState(false);
  const [partBeingEdited, setPartBeingEdited] =
    useState<Part | null>(null);
  // PATCH 153: recoverable part deletion and restoration UI
  const [partDeleteTarget, setPartDeleteTarget] =
    useState<Part | null>(null);
  const [deletedPartsOpen, setDeletedPartsOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadPartTypes() {
      if (!token) {
        setError("Your session is unavailable. Sign in again.");
        setIsLoading(false);
        return;
      }

      try {
        const result = await getPartTypes(token);
        if (cancelled) {
          return;
        }
        setCollection(result);
        setSelectedId(result.part_types[0]?.id ?? null);
      } catch (caught) {
        if (!cancelled) {
          setError(
            caught instanceof Error
              ? caught.message
              : "Unable to load part types"
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    loadPartTypes();
    return () => {
      cancelled = true;
    };
  }, [token]);

  // PATCH 171: load the reusable location catalogue for Stored Parts
  useEffect(() => {
    if (!token) {
      setInventoryLocations([]);
      setInventoryLocationsLoading(false);
      setInventoryLocationsError(null);
      setInventoryLocationFilter(null);
      return;
    }

    let cancelled = false;
    setInventoryLocationsLoading(true);
    setInventoryLocationsError(null);

    getLocations(token)
      .then((result) => {
        if (cancelled) {
          return;
        }
        setInventoryLocations(result.locations);
        setInventoryLocationFilter((current) =>
          current !== null
          && !result.locations.some((location) => location.id === current)
            ? null
            : current
        );
      })
      .catch((caught) => {
        if (!cancelled) {
          setInventoryLocations([]);
          setInventoryLocationsError(
            caught instanceof Error
              ? caught.message
              : "Unable to load locations"
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setInventoryLocationsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token, inventoryRefreshSequence]);

  // PATCH 233: debounce Stored Parts server search
  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setInventoryServerSearch(inventoryQuery.trim());
    }, 280);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [inventoryQuery]);

  // PATCH 233: PARTPILOT_STORED_PARTS_SERVER_SEARCH_V233
  useEffect(() => {
    if (!token) {
      inventoryRequestSequence.current += 1;
      setInventoryCollection(null);
      setInventoryLoading(false);
      return;
    }

    const requestId = inventoryRequestSequence.current + 1;
    inventoryRequestSequence.current = requestId;
    let cancelled = false;

    setInventoryLoading(true);
    setInventoryError(null);
    getParts(token, {
      limit: 250,
      offset: 0,
      locationId: inventoryLocationFilter ?? undefined,
      search: inventoryServerSearch || undefined,
      stockStatus: inventoryStockFilter
    })
      .then((result) => {
        if (
          !cancelled
          && requestId === inventoryRequestSequence.current
        ) {
          setInventoryCollection(result);
        }
      })
      .catch((caught) => {
        if (
          !cancelled
          && requestId === inventoryRequestSequence.current
        ) {
          setInventoryError(
            caught instanceof Error
              ? caught.message
              : "Unable to load inventory"
          );
        }
      })
      .finally(() => {
        if (
          !cancelled
          && requestId === inventoryRequestSequence.current
        ) {
          setInventoryLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [
    token,
    inventoryLocationFilter,
    inventoryRefreshSequence,
    inventoryServerSearch,
    inventoryStockFilter
  ]);

  // PATCH 194: load the Stored Parts grouping preference
  useEffect(() => {
    if (!token) {
      setShowOutOfStockSection(true);
      setInventorySearchSettingsError(
        "Search preferences are unavailable without an active session."
      );
      return;
    }

    let cancelled = false;
    setInventorySearchSettingsError(null);

    getSearchSettings(token)
      .then((result) => {
        if (!cancelled) {
          setShowOutOfStockSection(
            result.show_out_of_stock_section
          );
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setShowOutOfStockSection(true);
          setInventorySearchSettingsError(
            caught instanceof Error
              ? caught.message
              : "Unable to load search preferences"
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token, inventoryRefreshSequence]);

  useEffect(() => {
    if (selectedInventoryPartId === null || !token) {
      return;
    }

    let cancelled = false;
    setPartDetailsLoading(true);
    setPartDetailsError(null);
    setSelectedInventoryPart(null);

    getPart(token, selectedInventoryPartId)
      .then((part) => {
        if (!cancelled) {
          setSelectedInventoryPart(part);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setPartDetailsError(
            caught instanceof Error
              ? caught.message
              : "Unable to load part details"
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setPartDetailsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedInventoryPartId, token]);

  useEffect(() => {
    if (selectedInventoryPartId === null || !token) {
      setPartMovements([]);
      setPartMovementsLoading(false);
      return;
    }

    let cancelled = false;
    setPartMovementsLoading(true);
    setPartMovementsError(null);
    getPartMovements(token, selectedInventoryPartId, { limit: 12 })
      .then((result) => {
        if (!cancelled) {
          setPartMovements(result.movements);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setPartMovementsError(
            caught instanceof Error
              ? caught.message
              : "Unable to load stock history"
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setPartMovementsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedInventoryPartId, token]);

  useEffect(() => {
    if (selectedInventoryPartId === null) {
      return;
    }

    const previousOverflow = document.body.style.overflow;

    function handlePartDetailsKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && partBeingEdited === null) {
        setSelectedInventoryPartId(null);
        setSelectedInventoryPart(null);
        setPartDetailsError(null);
      }
    }

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handlePartDetailsKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handlePartDetailsKeyDown);
    };
  }, [selectedInventoryPartId, partBeingEdited]);

  const filteredTypes = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const allTypes = collection?.part_types ?? [];

    return allTypes.filter((partType) => {
      if (filter === "builtin" && !partType.is_builtin) {
        return false;
      }
      if (filter === "custom" && partType.is_builtin) {
        return false;
      }
      if (!normalizedQuery) {
        return true;
      }

      return (
        partType.name.toLowerCase().includes(normalizedQuery) ||
        partType.slug.toLowerCase().includes(normalizedQuery) ||
        partType.fields.some(
          (field) =>
            field.label.toLowerCase().includes(normalizedQuery) ||
            field.field_key.toLowerCase().includes(normalizedQuery)
        )
      );
    });
  }, [collection, filter, query]);

  useEffect(() => {
    if (
      filteredTypes.length > 0 &&
      !filteredTypes.some((partType) => partType.id === selectedId)
    ) {
      setSelectedId(filteredTypes[0].id);
    }
  }, [filteredTypes, selectedId]);

  const selectedType: PartType | null =
    collection?.part_types.find((item) => item.id === selectedId) ?? null;

  const selectedInventoryLocation = useMemo(
    () =>
      inventoryLocationFilter === null
        ? null
        : inventoryLocations.find(
            (location) => location.id === inventoryLocationFilter
          ) ?? null,
    [inventoryLocationFilter, inventoryLocations]
  );

  // PATCH 233: PARTPILOT_STORED_PARTS_SERVER_SEARCH_V233
  // Search and stock filtering now happen on the backend. The local split only
  // preserves the approved Available / Out of stock presentation for "all".
  const inventoryServerParts = inventoryCollection?.parts ?? [];
  const filteredInventoryParts = useMemo(() => {
    return inventoryServerParts.filter((part) => {
      if (inventoryStockFilter === "in") {
        return part.available_quantity > 0 && !part.is_low_stock;
      }

      if (inventoryStockFilter === "low") {
        return part.available_quantity > 0 && part.is_low_stock;
      }

      if (inventoryStockFilter === "out") {
        return part.available_quantity <= 0;
      }

      return part.available_quantity > 0;
    });
  }, [inventoryServerParts, inventoryStockFilter]);

  const outOfStockInventoryParts = useMemo(() => {
    if (
      inventoryStockFilter !== "all"
      || !showOutOfStockSection
    ) {
      return [];
    }

    return inventoryServerParts.filter(
      (part) => part.available_quantity <= 0
    );
  }, [
    inventoryServerParts,
    inventoryStockFilter,
    showOutOfStockSection
  ]);
  const visibleInventoryPartCount =
    filteredInventoryParts.length
    + outOfStockInventoryParts.length;

  function resetQuantityAdjustment() {
    setAdjustmentOperation("add");
    setAdjustmentQuantity("");
    setAdjustmentReason("");
    setAdjustmentNote("");
    setAdjustmentError(null);
    setAdjustmentSuccess(null);
  }


  // PATCH 144: close details drawer while metadata editor is open
  function openPartMetadataEditor(part: Part) {
    setPartBeingEdited(part);
    setSelectedInventoryPartId(null);
    setSelectedInventoryPart(null);
    setPartDetailsError(null);
  }

  function closePartMetadataEditor() {
    if (partBeingEdited) {
      setSelectedInventoryPart(partBeingEdited);
      setSelectedInventoryPartId(partBeingEdited.id);
    }
    setPartBeingEdited(null);
  }


  // PATCH 153: recoverable part deletion and restoration UI
  function openPartDeleteDialog(part: Part) {
    setPartDeleteTarget(part);
    setSelectedInventoryPartId(null);
    setSelectedInventoryPart(null);
    setPartDetailsError(null);
    setPartMovements([]);
    setPartMovementsError(null);
    resetQuantityAdjustment();
  }

  function closePartDeleteDialog() {
    if (partDeleteTarget) {
      setSelectedInventoryPart(partDeleteTarget);
      setSelectedInventoryPartId(partDeleteTarget.id);
    }
    setPartDeleteTarget(null);
  }

  function handlePartDeleted(partId: number) {
    setPartDeleteTarget(null);
    setSelectedInventoryPartId(null);
    setSelectedInventoryPart(null);
    setPartDetailsError(null);
    setPartMovements([]);
    setPartMovementsError(null);
    resetQuantityAdjustment();
    setInventoryCollection((current) =>
      current
        ? {
            ...current,
            total: Math.max(0, current.total - 1),
            parts: current.parts.filter((item) => item.id !== partId)
          }
        : current
    );
    setInventoryRefreshSequence((current) => current + 1);
  }

  function handlePartRestored(part: Part) {
    setInventoryCollection((current) => {
      if (!current) {
        return current;
      }

      const withoutRestored = current.parts.filter(
        (item) => item.id !== part.id
      );
      return {
        ...current,
        total: withoutRestored.length + 1,
        parts: [part, ...withoutRestored]
      };
    });
    setInventoryRefreshSequence((current) => current + 1);
  }

  function openPartDetails(partId: number) {
    setPartBeingEdited(null);
    setPartDetailsError(null);
    setPartMovements([]);
    setPartMovementsError(null);
    setSelectedInventoryPart(null);
    resetQuantityAdjustment();
    setSelectedInventoryPartId(partId);
  }

  function closePartDetails() {
    setPartBeingEdited(null);
    setSelectedInventoryPartId(null);
    setSelectedInventoryPart(null);
    setPartDetailsError(null);
    setPartMovements([]);
    setPartMovementsError(null);
    resetQuantityAdjustment();
  }

  async function handleQuantityAdjustment(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();
    if (!token || !selectedInventoryPart) {
      setAdjustmentError("Part details are unavailable. Reopen the record.");
      return;
    }

    const normalizedQuantity = adjustmentQuantity.trim();
    if (!/^-?\d+$/.test(normalizedQuantity)) {
      setAdjustmentError("Enter a whole-number quantity.");
      return;
    }

    const quantity = Number(normalizedQuantity);
    if (!Number.isSafeInteger(quantity)) {
      setAdjustmentError("Quantity is outside the supported range.");
      return;
    }
    if (adjustmentOperation === "correction" && quantity === 0) {
      setAdjustmentError("Correction cannot be zero.");
      return;
    }
    if (adjustmentOperation !== "correction" && quantity <= 0) {
      setAdjustmentError("Enter a quantity greater than zero.");
      return;
    }
    if (
      adjustmentOperation === "correction"
      && adjustmentReason.trim().length === 0
    ) {
      setAdjustmentError("A correction reason is required.");
      return;
    }

    setAdjustmentSaving(true);
    setAdjustmentError(null);
    setAdjustmentSuccess(null);
    try {
      const result = await adjustPartQuantity(
        token,
        selectedInventoryPart.id,
        {
          operation: adjustmentOperation,
          quantity,
          reason: adjustmentReason.trim() || null,
          note: adjustmentNote.trim() || null
        }
      );
      setSelectedInventoryPart(result.part);
      setPartMovements((current) => [
        result.movement,
        ...current.filter((movement) => movement.id !== result.movement.id)
      ].slice(0, 12));
      setInventoryCollection((current) => current
        ? {
            ...current,
            parts: current.parts.map((part) =>
              part.id === result.part.id ? result.part : part
            )
          }
        : current);
      setInventoryRefreshSequence((current) => current + 1);
      setAdjustmentQuantity("");
      setAdjustmentReason("");
      setAdjustmentNote("");
      setAdjustmentSuccess(
        `Stock updated from ${result.movement.quantity_before ?? "—"} `
        + `to ${result.movement.quantity_after ?? "—"}.`
      );
    } catch (caught) {
      setAdjustmentError(
        caught instanceof Error
          ? caught.message
          : "Unable to update stock quantity"
      );
    } finally {
      setAdjustmentSaving(false);
    }
  }

  function openCreator() {
    setEditingTypeId(null);
    setTypeName("");
    setTypeDescription("");
    setEditableFields([createEditableField()]);
    setCreatorError(null);
    setIsCreating(true);
  }

    // PATCH 085: custom part type edit workflow
  function openEditor(partType: PartType) {
    if (partType.is_builtin) {
      return;
    }

    setEditingTypeId(partType.id);
    setTypeName(partType.name);
    setTypeDescription(partType.description ?? "");
    setEditableFields(
      partType.fields.map((field) => {
        const options = Array.isArray(field.options)
          ? field.options.filter(
              (option): option is string => typeof option === "string"
            )
          : [];

        fieldSequence += 1;

        return {
          id: field.id,
          client_id: `field-${Date.now()}-${fieldSequence}`,
          field_key: field.field_key,
          label: field.label,
          field_type: field.field_type,
          is_required: field.is_required,
          options,
          options_text: options.join("\n"),
          default_unit: field.default_unit,
          help_text: field.help_text
        };
      })
    );
    setCreatorError(null);
    setIsCreating(true);
  }

function closeCreator() {
    if (isSaving) {
      return;
    }
    setIsCreating(false);
    setEditingTypeId(null);
    setCreatorError(null);
  }

      // PATCH 078: creator modal keyboard and scroll handling
      useEffect(() => {
        if (!isCreating) {
          return;
        }

        const previousOverflow = document.body.style.overflow;

        function handleCreatorKeyDown(event: KeyboardEvent) {
          if (event.key === "Escape" && !isSaving) {
            setIsCreating(false);
        setEditingTypeId(null);
            setCreatorError(null);
          }
        }

        document.body.style.overflow = "hidden";
        window.addEventListener("keydown", handleCreatorKeyDown);

        return () => {
          document.body.style.overflow = previousOverflow;
          window.removeEventListener("keydown", handleCreatorKeyDown);
        };
      }, [isCreating, isSaving]);

  function updateField(
    clientId: string,
    patch: Partial<EditableField>
  ) {
    setEditableFields((current) =>
      current.map((field) => {
        if (field.client_id !== clientId) {
          return field;
        }

        const next = { ...field, ...patch };
        if (typeof patch.label === "string") {
          const previousGeneratedKey = fieldKeyFromLabel(field.label);
          if (!field.field_key || field.field_key === previousGeneratedKey) {
            next.field_key = fieldKeyFromLabel(patch.label);
          }
        }
        return next;
      })
    );
  }

  // PATCH 106: convert the semantic preset to the existing storage contract
  function updateEditorFieldKind(
    field: EditableField,
    nextKind: EditorFieldKind
  ) {
    if (nextKind === "manufacturer") {
      const patch: Partial<EditableField> = {
        field_type: "text",
        field_key: "manufacturer",
        options: [],
        options_text: "",
        default_unit: null
      };
      if (!field.label.trim()) {
        patch.label = "Manufacturer";
      }
      updateField(field.client_id, patch);
      return;
    }

    updateField(field.client_id, {
      field_type: nextKind,
      field_key: isManufacturerEditorField(field)
        ? ""
        : field.field_key
    });
  }

  function moveField(index: number, direction: -1 | 1) {
    setEditableFields((current) => {
      const destination = index + direction;
      if (destination < 0 || destination >= current.length) {
        return current;
      }
      const copy = [...current];
      const [moved] = copy.splice(index, 1);
      copy.splice(destination, 0, moved);
      return copy;
    });
  }

  function validateCreator(): string[] {
    const issues: string[] = [];
    const cleanName = typeName.trim().replace(/\s+/g, " ");

    if (cleanName.length < 2) {
      issues.push("Enter a part type name with at least 2 characters.");
    }
    if (cleanName.length > 120) {
      issues.push("Part type name cannot exceed 120 characters.");
    }
    if (editableFields.length > 40) {
      issues.push("A part type can contain at most 40 template fields.");
    }

    const keys = new Set<string>();
    editableFields.forEach((field, index) => {
      const position = index + 1;
      const key = field.field_key.trim().toLowerCase();
      if (!field.label.trim()) {
        issues.push(`Field ${position} needs a label.`);
      }
      if (!/^[a-z][a-z0-9_]*$/.test(key)) {
        issues.push(
          `Field ${position} key must start with a letter and use lowercase letters, numbers, or underscores.`
        );
      } else if (keys.has(key)) {
        issues.push(`Field key “${key}” is duplicated.`);
      }
      keys.add(key);

      if (
        field.field_type === "dropdown" &&
        parseOptions(field.options_text).length < 2
      ) {
        issues.push(`Dropdown field ${position} needs at least 2 options.`);
      }
    });

    const manufacturerFieldCount = editableFields.filter(
      isManufacturerEditorField
    ).length;
    if (manufacturerFieldCount > 1) {
      issues.push(
        "A part type can contain only one Manufacturer field."
      );
    }

    return issues;
  }

  function buildPayload(): CreatePartTypePayload {
    return {
      name: typeName.trim().replace(/\s+/g, " "),
      description: typeDescription.trim() || null,
      fields: editableFields.map((field) => ({
        field_key: field.field_key.trim().toLowerCase(),
        label: field.label.trim().replace(/\s+/g, " "),
        field_type: field.field_type,
        is_required: field.is_required,
        options:
          field.field_type === "dropdown"
            ? parseOptions(field.options_text)
            : [],
        default_unit:
          field.field_type === "unit_value"
            ? field.default_unit?.trim() || null
            : null,
        help_text: field.help_text?.trim() || null
      }))
    };
  }

  function buildUpdatePayload(): UpdatePartTypePayload {
    const createPayload = buildPayload();

    return {
      ...createPayload,
      fields: createPayload.fields.map((field, index) => ({
        ...field,
        id: editableFields[index]?.id ?? null
      }))
    };
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const issues = validateCreator();
    if (issues.length > 0) {
      setCreatorError(issues.join(" "));
      return;
    }
    if (!token) {
      setCreatorError("Your session is unavailable. Sign in again.");
      return;
    }

    setIsSaving(true);
    setCreatorError(null);
    try {
      const saved =
        editingTypeId === null
          ? await createPartType(token, buildPayload())
          : await updatePartType(
              token,
              editingTypeId,
              buildUpdatePayload()
            );
      const refreshed = await getPartTypes(token);
      setCollection(refreshed);
      setSelectedId(saved.id);
      setFilter("custom");
      setQuery("");
      setEditingTypeId(null);
    setIsCreating(false);
    } catch (caught) {
      setCreatorError(
        caught instanceof Error
          ? caught.message
          : (editingTypeId === null
            ? "Unable to create the custom part type"
            : "Unable to update the custom part type")
      );
    } finally {
      setIsSaving(false);
    }
  }

  // PATCH 089: custom part type delete workflow
  function openDeleteDialog(partType: PartType) {
    if (partType.is_builtin) {
      return;
    }

    setDeleteTarget(partType);
    setDeleteConfirmation("");
    setDeleteError(null);
  }

  function closeDeleteDialog() {
    if (isDeleting) {
      return;
    }

    setDeleteTarget(null);
    setDeleteConfirmation("");
    setDeleteError(null);
  }

  useEffect(() => {
    if (!deleteTarget) {
      return;
    }

    const previousOverflow = document.body.style.overflow;

    function handleDeleteDialogKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !isDeleting) {
        setDeleteTarget(null);
        setDeleteConfirmation("");
        setDeleteError(null);
      }
    }

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleDeleteDialogKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener(
        "keydown",
        handleDeleteDialogKeyDown
      );
    };
  }, [deleteTarget, isDeleting]);

  async function handleDeletePartType(event: FormEvent) {
    event.preventDefault();

    if (
      !token
      || !deleteTarget
      || deleteConfirmation !== deleteTarget.name
    ) {
      return;
    }

    setIsDeleting(true);
    setDeleteError(null);

    try {
      await deletePartType(token, deleteTarget.id);
      const refreshed = await getPartTypes(token);

      setCollection(refreshed);
      setSelectedId(refreshed.part_types[0]?.id ?? null);
      setDeleteTarget(null);
      setDeleteConfirmation("");
    } catch (caught) {
      setDeleteError(
        caught instanceof Error
          ? caught.message
          : "Unable to delete the custom part type"
      );
    } finally {
      setIsDeleting(false);
    }
  }

  function renderInventoryTable(
    parts: Part[],
    labelledBy?: string
  ) {
    return (
      <div className="inventory-table-wrap">
        <table
          className="inventory-table"
          aria-labelledby={labelledBy}
        >
          <thead>
            <tr>
              <th scope="col">Part</th>
              <th scope="col">Type</th>
              <th scope="col">Manufacturer</th>
              <th scope="col">Location</th>
              <th scope="col">Available</th>
              <th scope="col">Total</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {parts.map((part) => (
              <tr
                key={part.id}
                className={
                  selectedInventoryPartId === part.id
                    ? "inventory-row-action is-selected"
                    : "inventory-row-action"
                }
                tabIndex={0}
                aria-label={`View details for ${inventoryPartName(part)}`}
                aria-haspopup="dialog"
                onClick={() => openPartDetails(part.id)}
                onKeyDown={(event) => {
                  if (
                    event.key === "Enter"
                    || event.key === " "
                  ) {
                    event.preventDefault();
                    openPartDetails(part.id);
                  }
                }}
              >
                <td>
                  <strong>{inventoryPartName(part)}</strong>
                  <small>
                    {part.part_number || "No part number"}
                  </small>
                </td>
                <td>{part.part_type_name}</td>
                <td>
                  {part.manufacturer_name || "Not specified"}
                </td>
                <td
                  className="inventory-location-cell"
                  title={part.location_name || "Not specified"}
                >
                  {part.location_name || "Not specified"}
                </td>
                <td className="inventory-quantity">
                  {part.available_quantity}
                </td>
                <td className="inventory-quantity">
                  {part.total_quantity}
                </td>
                <td>
                  <span
                    className={
                      `inventory-stock-pill ${
                        inventoryStockClass(part)
                      }`
                    }
                  >
                    {inventoryStockLabel(part)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div
      className={
        `page-stack part-manager-page${
          inventoryOnly ? " inventory-page" : ""
        }`
      }
      data-inventory-page-mode={
        inventoryOnly ? "inventory-page-mode-v202" : undefined
      }
      data-manufacturer-preset-version="part-manager-manufacturer-preset-v106"
      data-part-lifecycle-version="part-lifecycle-v153"
      data-out-of-stock-grouping-version="stored-parts-out-of-stock-group-v194"
    >
      {inventoryOnly ? (
        <header
          className="page-header part-manager-header inventory-page-header"
          data-inventory-page-version="inventory-live-page-v202"
        >
          <div>
            <p className="eyebrow">Inventory</p>
            <h1>Stored parts</h1>
            <p>
              Search, filter, inspect, add, edit, adjust, delete, and restore
              the components kept in this Part Pilot installation.
            </p>
          </div>
          <span className="status-pill">
            {isLoading
              ? "Loading templates"
              : collection
                ? `${collection.total} part types`
                : "Inventory workspace"}
          </span>
        </header>
      ) : (
              <header className="page-header part-manager-header">
                <div>
                  <p className="eyebrow">Phase 4</p>
                  <h1>Part Manager</h1>
                  <p>
                    Browse built-in electronics templates and create custom part
                    types for the inventory you actually keep.
                  </p>
                </div>
                <div className="part-manager-header-actions">
                  <span className="status-pill">
                    {isCreating
                      ? editingTypeId === null
                        ? "Creating custom type"
                        : "Editing custom type"
                      : "Template manager"}
                  </span>

                  <button
                    className="part-manager-create-button"
                    type="button"
                    onClick={isCreating ? closeCreator : openCreator}
                    disabled={isSaving}
                  >
                    {isCreating ? "Close creator" : "New custom type"}
                  </button>
                </div>
              </header>
      )}

      {!inventoryOnly && collection ? (
        <section className="part-manager-stats" aria-label="Part type totals">
          <article className="card">
            <span>Part types</span>
            <strong>{collection.total}</strong>
          </article>
          <article className="card">
            <span>Built-in</span>
            <strong>{collection.builtin_count}</strong>
          </article>
          <article className="card">
            <span>Custom</span>
            <strong>{collection.custom_count}</strong>
          </article>
          <article className="card">
            <span>Template fields</span>
            <strong>{collection.total_fields}</strong>
          </article>
        </section>
      ) : null}

      {/* PATCH 094: Add Part modal mount */}
      {isAddingPart && collection && token ? (
        <AddPartModal
          token={token}
          partTypes={collection.part_types}
          initialPartTypeId={selectedType?.id ?? null}
          onClose={() => {
            setIsAddingPart(false);
            setInventoryRefreshSequence(
              (current) => current + 1
            );
          }}
        />
      ) : null}


      {/* PATCH 143: focused existing-part metadata edit workflow */}
      {partBeingEdited && collection && token ? (
        <EditPartModal
          token={token}
          part={partBeingEdited}
          partType={
            collection.part_types.find(
              (item) => item.id === partBeingEdited.part_type_id
            ) as PartType
          }
          onClose={closePartMetadataEditor}
          onSaved={(updatedPart) => {
            setPartBeingEdited(null);
            setSelectedInventoryPart(updatedPart);
            setSelectedInventoryPartId(updatedPart.id);
            setInventoryCollection((current) =>
              current
                ? {
                    ...current,
                    parts: current.parts.map((item) =>
                      item.id === updatedPart.id
                        ? updatedPart
                        : item
                    )
                  }
                : current
            );
            setInventoryRefreshSequence((current) => current + 1);
          }}
        />
      ) : null}

      {token ? (
        <PartLifecycleModal
          token={token}
          deleteTarget={partDeleteTarget}
          deletedPartsOpen={deletedPartsOpen}
          onCloseDelete={closePartDeleteDialog}
          onDeleted={handlePartDeleted}
          onCloseDeletedParts={() => setDeletedPartsOpen(false)}
          onRestored={handlePartRestored}
        />
      ) : null}

      {isCreating ? (
            <div
              className="creator-modal-backdrop"
              role="presentation"
              onMouseDown={(event) => {
                if (event.target === event.currentTarget && !isSaving) {
                  closeCreator();
                }
              }}
            >
              <section
                className={`part-type-creator creator-modal card${
              editingTypeId === null ? "" : " is-editing"
            }`}
                role="dialog"
                aria-modal="true"
                aria-labelledby="create-part-type-title"
              >
          <form onSubmit={handleCreate}>
            <div className="creator-heading">
              <div>
                <p className="eyebrow">Custom template</p>
                <h2 id="create-part-type-title">
                  {editingTypeId === null
                    ? "Create part type"
                    : "Edit part type"}
                </h2>
                <p>
                  {editingTypeId === null
                    ? "Define the reusable fields that will appear whenever this type of part is added later."
                    : "Update this custom template. Existing field identities are preserved when possible."}
                </p>
              </div>
              <div className="creator-heading-actions">
                    <span className="creator-field-count">
                      {editableFields.length} fields
                    </span>
                    <button
                      className="creator-modal-close"
                      type="button"
                      onClick={closeCreator}
                      disabled={isSaving}
                      aria-label="Close part type creator"
                      title="Close"
                    >
                      ×
                    </button>
                  </div>
            </div>

            {creatorError ? (
              <div className="creator-error" role="alert">
                {creatorError}
              </div>
            ) : null}

            <div className="creator-grid">
              <div className="creator-editor">
                <div className="creator-basics">
                  <label>
                    <span>Type name</span>
                    <input
                      value={typeName}
                      onChange={(event: ChangeEvent<HTMLInputElement>) =>
                        setTypeName(event.target.value)
                      }
                      placeholder="Example: Development board"
                      maxLength={120}
                      autoFocus
                    />
                  </label>
                  <label>
                    <span>Description</span>
                    <textarea
                      value={typeDescription}
                      onChange={(event: ChangeEvent<HTMLTextAreaElement>) =>
                        setTypeDescription(event.target.value)
                      }
                      placeholder="What belongs in this category?"
                      rows={3}
                      maxLength={2000}
                    />
                  </label>
                </div>

                <div className="creator-fields-heading">
                  <div>
                    <strong>Template fields</strong>
                    <span>Order here becomes display order.</span>
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      setEditableFields((current) => [
                        ...current,
                        createEditableField()
                      ])
                    }
                    disabled={editableFields.length >= 40}
                  >
                    Add field
                  </button>
                </div>

                <div className="creator-field-list">
                  {editableFields.length === 0 ? (
                    <div className="creator-empty-fields">
                      This template has no custom fields. You can still create
                      it or add a field now.
                    </div>
                  ) : null}

                  {editableFields.map((field, index) => (
                    <article className="creator-field-card" key={field.client_id}>
                      <div className="creator-field-toolbar">
                        <strong>Field {index + 1}</strong>
                        <div>
                          <button
                            type="button"
                            onClick={() => moveField(index, -1)}
                            disabled={index === 0}
                          >
                            Up
                          </button>
                          <button
                            type="button"
                            onClick={() => moveField(index, 1)}
                            disabled={index === editableFields.length - 1}
                          >
                            Down
                          </button>
                          <button
                            className="creator-remove-button"
                            type="button"
                            onClick={() =>
                              setEditableFields((current) =>
                                current.filter(
                                  (item) => item.client_id !== field.client_id
                                )
                              )
                            }
                          >
                            Remove
                          </button>
                        </div>
                      </div>

                      <div className="creator-field-grid">
                        <label>
                          <span>Label</span>
                          <input
                            value={field.label}
                            onChange={(event: ChangeEvent<HTMLInputElement>) =>
                              updateField(field.client_id, {
                                label: event.target.value
                              })
                            }
                            placeholder="Example: Chipset"
                            maxLength={160}
                          />
                        </label>
                        <label>
                          <span>Field key</span>
                          <input
                            value={field.field_key}
                            onChange={(event: ChangeEvent<HTMLInputElement>) =>
                              updateField(field.client_id, {
                                field_key: event.target.value
                                  .toLowerCase()
                                  .replace(/[^a-z0-9_]/g, "")
                              })
                            }
                            placeholder="chipset"
                            maxLength={120}
                            disabled={isManufacturerEditorField(field)}
                            title={
                              isManufacturerEditorField(field)
                                ? "Manufacturer uses the reusable catalogue key"
                                : undefined
                            }
                            spellCheck={false}
                          />
                        </label>
                        <label>
                          <span>Field type</span>
                          <select
                            value={editorFieldKind(field)}
                            onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                              updateEditorFieldKind(
                                field,
                                event.target.value as EditorFieldKind
                              )
                            }
                          >
                            {EDITOR_FIELD_TYPES.map((type) => (
                              <option key={type.value} value={type.value}>
                                {type.label} — {type.description}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="creator-required-toggle">
                          <input
                            type="checkbox"
                            checked={field.is_required}
                            onChange={(event: ChangeEvent<HTMLInputElement>) =>
                              updateField(field.client_id, {
                                is_required: event.target.checked
                              })
                            }
                          />
                          <span>Required when adding a part</span>
                        </label>
                      </div>

                      {field.field_type === "dropdown" ? (
                        <label className="creator-wide-control">
                          <span>Dropdown options</span>
                          <textarea
                            value={field.options_text}
                            onChange={(event: ChangeEvent<HTMLTextAreaElement>) =>
                              updateField(field.client_id, {
                                options_text: event.target.value
                              })
                            }
                            placeholder="One per line or comma separated"
                            rows={3}
                          />
                        </label>
                      ) : null}

                      {field.field_type === "unit_value" ? (
                        <label className="creator-wide-control">
                          <span>Default unit</span>
                          <input
                            value={field.default_unit ?? ""}
                            onChange={(event: ChangeEvent<HTMLInputElement>) =>
                              updateField(field.client_id, {
                                default_unit: event.target.value
                              })
                            }
                            placeholder="Example: V, A, Ω, mm"
                            maxLength={30}
                          />
                        </label>
                      ) : null}

                      <label className="creator-wide-control">
                        <span>Help text</span>
                        <input
                          value={field.help_text ?? ""}
                          onChange={(event: ChangeEvent<HTMLInputElement>) =>
                            updateField(field.client_id, {
                              help_text: event.target.value
                            })
                          }
                          placeholder="Optional guidance shown with the field"
                          maxLength={1000}
                        />
                      </label>
                    </article>
                  ))}
                </div>
              </div>

              <aside className="creator-preview">
                <div className="creator-preview-card">
                  <p className="eyebrow">Live preview</p>
                  <h3>{typeName.trim() || "Untitled part type"}</h3>
                  <p>
                    {typeDescription.trim() ||
                      "Your description will appear here."}
                  </p>

                  <div className="creator-preview-fields">
                    {editableFields.length === 0 ? (
                      <span>No custom fields yet.</span>
                    ) : null}
                    {editableFields.map((field) => (
                      <label key={field.client_id}>
                        <span>
                          {field.label || "Untitled field"}
                          {field.is_required ? <b>Required</b> : null}
                        </span>
                        {previewInput(field)}
                        <small>
                          {fieldTypeLabel(field.field_type)} · {field.field_key || "field_key"}
                        </small>
                      </label>
                    ))}
                  </div>
                </div>
              </aside>
            </div>

            <footer className="creator-actions">
              <button type="button" onClick={closeCreator} disabled={isSaving}>
                Cancel
              </button>
              <button
                className="creator-submit-button"
                type="submit"
                disabled={isSaving}
              >
                {isSaving
                ? editingTypeId === null
                  ? "Creating…"
                  : "Saving…"
                : editingTypeId === null
                  ? "Create custom type"
                  : "Save changes"}
              </button>
            </footer>
          </form>
        </section>
            </div>
      ) : null}

      {deleteTarget ? (
        <div
          className="delete-type-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (
              event.target === event.currentTarget
              && !isDeleting
            ) {
              closeDeleteDialog();
            }
          }}
        >
          <section
            className="delete-type-dialog card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-part-type-title"
            aria-describedby="delete-part-type-description"
          >
            <form onSubmit={handleDeletePartType}>
              <header>
                <div>
                  <p className="eyebrow">Permanent action</p>
                  <h2 id="delete-part-type-title">
                    Delete custom part type?
                  </h2>
                </div>
                <button
                  className="delete-type-close"
                  type="button"
                  onClick={closeDeleteDialog}
                  disabled={isDeleting}
                  aria-label="Close deletion dialog"
                  title="Close"
                >
                  ×
                </button>
              </header>

              <div className="delete-type-content">
                <p id="delete-part-type-description">
                  This permanently removes the
                  <strong> {deleteTarget.name} </strong>
                  template and all of its template fields. Deletion is
                  blocked when any inventory part still uses this type.
                </p>

                <label>
                  <span>
                    Type <strong>{deleteTarget.name}</strong> to confirm
                  </span>
                  <input
                    value={deleteConfirmation}
                    onChange={(event: ChangeEvent<HTMLInputElement>) =>
                      setDeleteConfirmation(event.target.value)
                    }
                    autoComplete="off"
                    spellCheck={false}
                    autoFocus
                  />
                </label>

                {deleteError ? (
                  <div className="delete-type-error" role="alert">
                    {deleteError}
                  </div>
                ) : null}
              </div>

              <footer>
                <button
                  type="button"
                  onClick={closeDeleteDialog}
                  disabled={isDeleting}
                >
                  Cancel
                </button>
                <button
                  className="delete-type-confirm"
                  type="submit"
                  disabled={
                    isDeleting
                    || deleteConfirmation !== deleteTarget.name
                  }
                >
                  {isDeleting
                    ? "Deleting…"
                    : "Delete custom type"}
                </button>
              </footer>
            </form>
          </section>
        </div>
      ) : null}

      {!inventoryOnly ? (
        <>
                <section className="search-card">
                  <label>
                    <span>Search part types and fields</span>
                    <input
                      type="search"
                      value={query}
                      onChange={(event: ChangeEvent<HTMLInputElement>) =>
                        setQuery(event.target.value)
                      }
                      placeholder="Search types or template fields..."
                    />
                  </label>
                  <div className="filter-tabs" aria-label="Part type filter">
                    {(["all", "builtin", "custom"] as FilterMode[]).map((mode) => (
                      <button
                        key={mode}
                        type="button"
                        className={filter === mode ? "active" : ""}
                        onClick={() => setFilter(mode)}
                      >
                        {mode === "all"
                          ? "All"
                          : mode === "builtin"
                            ? "Built-in"
                            : "Custom"}
                      </button>
                    ))}
                  </div>
                </section>

                {isLoading ? (
                  <section className="empty-state">
                    <strong>Loading part templates...</strong>
                    <p>Reading seeded part types and their custom fields.</p>
                  </section>
                ) : null}

                {error ? (
                  <section className="empty-state error-state">
                    <strong>Part Manager could not load</strong>
                    <p>{error}</p>
                  </section>
                ) : null}

                {!isLoading && !error && collection ? (
                <section className={`part-manager-layout${filteredTypes.length <= 4 ? " is-compact" : ""}`}>
                    <div className="part-type-list">
                      <div className="part-type-list-heading">
                        <strong>Types</strong>
                        <span>{filteredTypes.length} shown</span>
                      </div>
                      {filteredTypes.length > 0 ? (
                        filteredTypes.map((partType) => (
                          <button
                            key={partType.id}
                            type="button"
                            className={`part-type-item ${
                              selectedType?.id === partType.id ? "active" : ""
                            }`}
                            onClick={() => setSelectedId(partType.id)}
                          >
                            <span>
                              <strong>{partType.name}</strong>
                              <small>{partType.field_count} fields</small>
                            </span>
                            <em>{partType.is_builtin ? "Built-in" : "Custom"}</em>
                          </button>
                        ))
                      ) : (
                        <div className="part-type-list-empty">
                          No part types match this filter.
                        </div>
                      )}
                    </div>

                    <div className="part-type-detail">
                      {selectedType ? (
                        <>
                          <header className="part-type-detail-header">
                            <div>
                              <p className="eyebrow">
                                {selectedType.is_builtin ? "Built-in" : "Custom"}
                              </p>
                              <h2>{selectedType.name}</h2>
                              <p>
                                {selectedType.description ||
                                  `Template slug: ${selectedType.slug}`}
                              </p>
                            </div>
                            <div className="part-type-detail-actions">
                              {!selectedType.is_builtin ? (
                                <>
                                <button
                                  className="part-type-edit-button"
                                  type="button"
                                  onClick={() => openEditor(selectedType)}
                                >
                                  Edit custom type
                                </button>
                                <button
                                  className="part-type-delete-button"
                                  type="button"
                                  onClick={() => openDeleteDialog(selectedType)}
                                >
                                  Delete
                                </button>
                              </>
                              ) : null}
                              {/* PATCH 118: contextual Add Part action */}
                              <button
                                className="part-manager-add-part-button"
                                data-contextual-add-version="contextual-add-part-v118"
                                type="button"
                                onClick={() => setIsAddingPart(true)}
                                disabled={
                                  !token
                                  || !collection
                                  || isLoading
                                  || isCreating
                                  || !selectedType
                                }
                              >
                                Add part
                              </button>
                              <span className="status-pill">
                                Template v{selectedType.template_version}
                              </span>
                            </div>
                          </header>

                          <div className="template-field-heading">
                            <div>
                              <strong>Template fields</strong>
                              <span>
                                Fields shown when creating a {selectedType.name} part
                              </span>
                            </div>
                            <span>{selectedType.field_count}</span>
                          </div>

                          {selectedType.fields.length > 0 ? (
                            <div className="template-field-list">
                              {selectedType.fields.map((field) => (
                                <article className="template-field-row" key={field.id}>
                                  <div className="template-field-copy">
                                    <strong>
                                      {field.label}
                                      {field.is_required ? (
                                        <span className="required-badge">Required</span>
                                      ) : null}
                                    </strong>
                                    <code>{field.field_key}</code>
                                    {field.help_text ? <p>{field.help_text}</p> : null}
                                  </div>
                                  <div className="template-field-meta">
                                    <span>
                                    {isManufacturerEditorField(field)
                                      ? "Manufacturer"
                                      : fieldTypeLabel(field.field_type)}
                                  </span>
                                    {fieldSummary(field) ? (
                                      <small>{fieldSummary(field)}</small>
                                    ) : null}
                                  </div>
                                </article>
                              ))}
                            </div>
                          ) : (
                            <div className="part-type-detail-empty">
                              This type has no template fields yet.
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="part-type-detail-empty">
                          Select a part type to inspect its template.
                        </div>
                      )}
                    </div>
                  </section>
                ) : null}
        </>
      ) : null}
      {/* PATCH 110: first inventory browsing slice */}
      <section
        className="inventory-browser card"
        data-inventory-browser-version="inventory-browser-v110"
        aria-labelledby="inventory-browser-title"
      >
        <header className="inventory-browser-header">
          <div>
            <p className="eyebrow">Inventory</p>
            <h2 id="inventory-browser-title">Stored parts</h2>
            <p>
              Search stored parts and filter them by current stock status.
            </p>
          </div>
          <div className="inventory-browser-actions">
            <span>
              {inventoryQuery.trim()
                || inventoryStockFilter !== "all"
                || !showOutOfStockSection
                ? `${visibleInventoryPartCount} of ${
                    inventoryCollection?.total ?? 0
                  } shown`
                : selectedInventoryLocation
                  ? `${inventoryCollection?.total ?? 0} in ${
                      selectedInventoryLocation.name
                    }`
                  : `${inventoryCollection?.total ?? 0} parts`}
            </span>
            {inventoryOnly ? (
              <button
                className="inventory-add-part-button"
                data-inventory-add-version="inventory-page-add-part-v202"
                type="button"
                onClick={() => setIsAddingPart(true)}
                disabled={
                  !token
                  || !collection
                  || inventoryLoading
                  || isLoading
                }
              >
                Add part
              </button>
            ) : null}
            <button
              className="inventory-deleted-button"
              type="button"
              onClick={() => setDeletedPartsOpen(true)}
              disabled={!token}
            >
              Deleted items
            </button>
            <button
              type="button"
              onClick={() =>
                setInventoryRefreshSequence(
                  (current) => current + 1
                )
              }
              disabled={inventoryLoading || !token}
            >
              {inventoryLoading ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </header>

        {/* PATCH 120: inventory search and stock filter */}
        <div
          className="inventory-browser-toolbar"
          data-inventory-filter-version="inventory-search-filter-v120"
          data-server-search-version={
            STORED_PARTS_SERVER_SEARCH_VERSION
          }
          data-location-filter-version="stored-parts-location-filter-v171"
        >
          <label className="inventory-search-control">
            <span className="sr-only">Search stored parts</span>
            <input
              type="search"
              value={inventoryQuery}
              onChange={(
                event: ChangeEvent<HTMLInputElement>
              ) => setInventoryQuery(event.target.value)}
              placeholder="Search name, model, type, or manufacturer..."
              disabled={!token}
            />
          </label>

          <label className="inventory-location-filter">
            <span className="sr-only">Filter inventory by location</span>
            <select
              value={inventoryLocationFilter ?? ""}
              onChange={(
                event: ChangeEvent<HTMLSelectElement>
              ) => {
                const value = event.target.value;
                setInventoryLocationFilter(
                  value ? Number(value) : null
                );
              }}
              aria-label="Filter inventory by location"
              title={
                inventoryLocationsError
                  ?? "Filter stored parts by location"
              }
              disabled={inventoryLocationsLoading || !token}
            >
              <option value="">All locations</option>
              {inventoryLocationsLoading ? (
                <option value="" disabled>
                  Loading locations...
                </option>
              ) : null}
              {inventoryLocationsError ? (
                <option value="" disabled>
                  Locations unavailable
                </option>
              ) : null}
              {inventoryLocations.map((location) => (
                <option key={location.id} value={location.id}>
                  {location.name}
                </option>
              ))}
            </select>
          </label>
          <div
            className="inventory-stock-filters"
            role="group"
            aria-label="Filter inventory by stock status"
          >
            {(
              [
                ["all", "All"],
                ["in", "In stock"],
                ["low", "Low"],
                ["out", "Out"]
              ] as Array<[InventoryStockFilter, string]>
            ).map(([mode, label]) => (
              <button
                key={mode}
                type="button"
                className={
                  inventoryStockFilter === mode ? "active" : ""
                }
                aria-pressed={inventoryStockFilter === mode}
                onClick={() => setInventoryStockFilter(mode)}
                disabled={inventoryLoading || !inventoryCollection}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {inventoryLoading ? (
          <div className="inventory-browser-state">
            Loading inventory...
          </div>
        ) : null}

        {inventoryError ? (
          <div
            className="inventory-browser-state is-error"
            role="alert"
          >
            {inventoryError}
          </div>
        ) : null}

        {!inventoryLoading
          && !inventoryError
          && inventoryCollection
          && !inventoryQuery.trim()
          && inventoryStockFilter === "all"
          && inventoryLocationFilter === null
          && inventoryCollection.parts.length === 0 ? (
            <div className="inventory-browser-state">
              No inventory parts yet. Use Add part to create the first one.
            </div>
          ) : null}

        {!inventoryLoading
          && !inventoryError
          && inventoryCollection
          && (
            Boolean(inventoryQuery.trim())
            || inventoryStockFilter !== "all"
            || inventoryLocationFilter !== null
          )
          && visibleInventoryPartCount === 0 ? (
            <div className="inventory-browser-state inventory-filter-empty">
              <strong>No stored parts match</strong>
              <p>
                Try another search or clear the stock or location filter.
              </p>
              <button
                type="button"
                onClick={() => {
                  setInventoryQuery("");
                  setInventoryStockFilter("all");
                  setInventoryLocationFilter(null);
                }}
              >
                Clear filters
              </button>
            </div>
          ) : null}

        {!inventoryLoading
          && !inventoryError
          && inventoryCollection
          && filteredInventoryParts.length > 0
          ? renderInventoryTable(filteredInventoryParts)
          : null}

        {!inventoryLoading
          && !inventoryError
          && inventoryCollection
          && outOfStockInventoryParts.length > 0 ? (
            <section
              className="inventory-out-of-stock-section"
              data-out-of-stock-grouping-version="stored-parts-out-of-stock-group-v194"
              aria-labelledby="inventory-out-of-stock-title"
            >
              <header className="inventory-out-of-stock-header">
                <div>
                  <p className="eyebrow">Separate results</p>
                  <h3 id="inventory-out-of-stock-title">
                    Out of stock
                  </h3>
                  <p>
                    These matching parts have no available quantity.
                  </p>
                </div>
                <span>
                  {outOfStockInventoryParts.length}
                  {" "}
                  {outOfStockInventoryParts.length === 1
                    ? "part"
                    : "parts"}
                </span>
              </header>
              {renderInventoryTable(
                outOfStockInventoryParts,
                "inventory-out-of-stock-title"
              )}
            </section>
          ) : null}

        {inventorySearchSettingsError ? (
          <div
            className="inventory-settings-warning"
            role="status"
          >
            Search preference unavailable. Out-of-stock grouping is
            temporarily shown by default.
          </div>
        ) : null}
      </section>

      {selectedInventoryPartId !== null ? (
        <div
          className="part-details-backdrop"
          data-part-details-version="inventory-part-details-v124"
          data-stock-adjustment-version="inventory-stock-adjustment-v137"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              closePartDetails();
            }
          }}
        >
          <aside
            className="part-details-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="part-details-title"
          >
            <header className="part-details-header">
              <div>
                <p className="eyebrow">Inventory record</p>
                <h2 id="part-details-title">
                  {selectedInventoryPart
                    ? inventoryPartName(selectedInventoryPart)
                    : "Part details"}
                </h2>
                <p>
                  {selectedInventoryPart?.part_number
                    || "Read-only inventory details"}
                </p>
              </div>
              <button
                className="part-details-close"
                type="button"
                onClick={closePartDetails}
                aria-label="Close part details"
                title="Close"
                autoFocus
              >
                ×
              </button>
            </header>

            <div
              className="part-details-body"
              data-number-format-version={
                PART_DETAIL_NUMBER_FORMAT_VERSION
              }
            >
              {partDetailsLoading
                || (!selectedInventoryPart && !partDetailsError) ? (
                  <div className="part-details-state">
                    Loading part details...
                  </div>
                ) : null}

              {partDetailsError ? (
                <div
                  className="part-details-state is-error"
                  role="alert"
                >
                  <strong>Part details could not load</strong>
                  <p>{partDetailsError}</p>
                </div>
              ) : null}

              {selectedInventoryPart ? (
                <>
                  <section
                    className="part-details-stock"
                    aria-label="Stock quantities"
                  >
                    <article>
                      <span>Available</span>
                      <strong>
                        {selectedInventoryPart.available_quantity}
                      </strong>
                    </article>
                    <article>
                      <span>Reserved</span>
                      <strong>
                        {selectedInventoryPart.reserved_quantity}
                      </strong>
                    </article>
                    <article>
                      <span>Total</span>
                      <strong>
                        {selectedInventoryPart.total_quantity}
                      </strong>
                    </article>
                  </section>

                                    <section
                    className="part-details-section part-quantity-adjustment"
                    aria-label="Adjust stock quantity"
                  >
                    <div className="part-details-section-heading">
                      <strong>Adjust quantity</strong>
                      <span className="part-quantity-current">
                        Total {selectedInventoryPart.total_quantity}
                      </span>
                    </div>
                    <form
                      className="part-quantity-form"
                      onSubmit={handleQuantityAdjustment}
                    >
                      <div className="part-quantity-controls">
                        <label>
                          <span>Action</span>
                          <select
                            value={adjustmentOperation}
                            onChange={(event) => {
                              setAdjustmentOperation(
                                event.target.value as QuantityAdjustmentOperation
                              );
                              setAdjustmentError(null);
                              setAdjustmentSuccess(null);
                            }}
                            disabled={adjustmentSaving}
                          >
                            <option value="add">Add stock</option>
                            <option value="remove">Remove stock</option>
                            <option value="consume">Consume stock</option>
                            <option value="correction">Correction</option>
                          </select>
                        </label>
                        <label>
                          <span>
                            {adjustmentOperation === "correction"
                              ? "Change by"
                              : "Quantity"}
                          </span>
                          <input
                            type="number"
                            step="1"
                            min={
                              adjustmentOperation === "correction"
                                ? undefined
                                : 1
                            }
                            value={adjustmentQuantity}
                            onChange={(event) =>
                              setAdjustmentQuantity(event.target.value)}
                            placeholder={
                              adjustmentOperation === "correction"
                                ? "-2 or 3"
                                : "1"
                            }
                            required
                            disabled={adjustmentSaving}
                          />
                        </label>
                      </div>
                      <p className="part-quantity-hint">
                        {quantityOperationHint(
                          adjustmentOperation,
                          selectedInventoryPart
                        )}
                      </p>
                      <label className="part-quantity-wide-field">
                        <span>
                          Reason
                          {adjustmentOperation === "correction"
                            ? " (required)"
                            : " (optional)"}
                        </span>
                        <input
                          type="text"
                          maxLength={180}
                          value={adjustmentReason}
                          onChange={(event) =>
                            setAdjustmentReason(event.target.value)}
                          placeholder="Why is the stock changing?"
                          required={adjustmentOperation === "correction"}
                          disabled={adjustmentSaving}
                        />
                      </label>
                      <label className="part-quantity-wide-field">
                        <span>Note (optional)</span>
                        <textarea
                          rows={2}
                          maxLength={5000}
                          value={adjustmentNote}
                          onChange={(event) =>
                            setAdjustmentNote(event.target.value)}
                          placeholder="Add useful context for this movement"
                          disabled={adjustmentSaving}
                        />
                      </label>
                      {adjustmentError ? (
                        <div
                          className="part-quantity-feedback is-error"
                          role="alert"
                        >
                          {adjustmentError}
                        </div>
                      ) : null}
                      {adjustmentSuccess ? (
                        <div
                          className="part-quantity-feedback is-success"
                          role="status"
                        >
                          {adjustmentSuccess}
                        </div>
                      ) : null}
                      <div className="part-quantity-submit-row">
                        <span>
                          Reserved stock cannot be removed or consumed.
                        </span>
                        <button type="submit" disabled={adjustmentSaving}>
                          {adjustmentSaving ? "Saving..." : "Apply change"}
                        </button>
                      </div>
                    </form>
                  </section>
                  <section
                    className="part-details-section part-movement-history"
                    aria-label="Recent stock history"
                  >
                    <div className="part-details-section-heading">
                      <strong>Recent stock history</strong>
                      <span className="part-movement-count">
                        {partMovements.length} shown
                      </span>
                    </div>
                    {partMovementsLoading ? (
                      <div className="part-movement-state">
                        Loading stock history...
                      </div>
                    ) : null}
                    {partMovementsError ? (
                      <div
                        className="part-movement-state is-error"
                        role="alert"
                      >
                        {partMovementsError}
                      </div>
                    ) : null}
                    {!partMovementsLoading
                      && !partMovementsError
                      && partMovements.length === 0 ? (
                        <div className="part-movement-state">
                          No stock movements recorded yet.
                        </div>
                      ) : null}
                    {partMovements.length > 0 ? (
                      <ol className="part-movement-list">
                        {partMovements.map((movement) => (
                          <li key={movement.id}>
                            <div className="part-movement-primary">
                              <div>
                                <strong>
                                  {movement.reason
                                    || movementTypeLabel(movement)}
                                </strong>
                                <span>
                                  {movementTypeLabel(movement)}
                                  {` · ${inventoryDateLabel(
                                    movement.created_at
                                  )}`}
                                </span>
                              </div>
                              <b
                                className={
                                  movement.quantity_delta > 0
                                    ? "is-positive"
                                    : "is-negative"
                                }
                              >
                                {movementDeltaLabel(
                                  movement.quantity_delta
                                )}
                              </b>
                            </div>
                            <p>
                              {movement.quantity_before ?? "—"}
                              {" → "}
                              {movement.quantity_after ?? "—"}
                            </p>
                            {movement.note ? (
                              <small>{movement.note}</small>
                            ) : null}
                          </li>
                        ))}
                      </ol>
                    ) : null}
                  </section>
<section className="part-details-section">
                    <div className="part-details-section-heading">
                      <strong>Identification</strong>
                      <span
                        className={
                          `inventory-stock-pill ${
                            inventoryStockClass(selectedInventoryPart)
                          }`
                        }
                      >
                        {inventoryStockLabel(selectedInventoryPart)}
                      </span>
                    </div>
                    <dl className="part-details-grid">
                      <div>
                        <dt>Display name</dt>
                        <dd>
                          {selectedInventoryPart.name || "Not specified"}
                        </dd>
                      </div>
                      <div>
                        <dt>Part number / model</dt>
                        <dd>
                          {selectedInventoryPart.part_number
                            || "Not specified"}
                        </dd>
                      </div>
                      <div>
                        <dt>Part type</dt>
                        <dd>{selectedInventoryPart.part_type_name}</dd>
                      </div>
                      <div>
                        <dt>Manufacturer</dt>
                        <dd>
                          {selectedInventoryPart.manufacturer_name
                            || "Not specified"}
                        </dd>
                      </div>
                      <div>
                        <dt>Location</dt>
                        <dd>
                          {selectedInventoryPart.location_name
                            || "Not specified"}
                        </dd>
                      </div>
                      <div>
                        <dt>Package / form factor</dt>
                        <dd>
                          {selectedInventoryPart.package
                            || "Not specified"}
                        </dd>
                      </div>
                      <div>
                        <dt>Low-stock threshold</dt>
                        <dd>
                          {selectedInventoryPart.low_stock_enabled
                            ? (
                              selectedInventoryPart.low_stock_threshold
                              ?? "Not set"
                            )
                            : "Disabled"}
                        </dd>
                      </div>
                    </dl>
                  </section>

                  <section className="part-details-section">
                    <div className="part-details-section-heading">
                      <strong>Purchase and record</strong>
                    </div>
                    <dl className="part-details-grid">
                      <div>
                        <dt>Unit price</dt>
                        <dd>
                          {selectedInventoryPart.unit_price
                            ?? "Not specified"}
                        </dd>
                      </div>
                      <div>
                        <dt>Purchase link</dt>
                        <dd>
                          {selectedInventoryPart.purchase_link ? (
                            <a
                              href={selectedInventoryPart.purchase_link}
                              target="_blank"
                              rel="noreferrer"
                            >
                              Open purchase page
                            </a>
                          ) : (
                            "Not specified"
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt>Created</dt>
                        <dd>
                          {inventoryDateLabel(
                            selectedInventoryPart.created_at
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt>Last updated</dt>
                        <dd>
                          {inventoryDateLabel(
                            selectedInventoryPart.updated_at
                          )}
                        </dd>
                      </div>
                    </dl>
                  </section>

                  {selectedInventoryPart.description ? (
                    <section className="part-details-section">
                      <div className="part-details-section-heading">
                        <strong>Description</strong>
                      </div>
                      <p className="part-details-copy">
                        {selectedInventoryPart.description}
                      </p>
                    </section>
                  ) : null}

                  {selectedInventoryPart.notes ? (
                    <section className="part-details-section">
                      <div className="part-details-section-heading">
                        <strong>Notes</strong>
                      </div>
                      <p className="part-details-copy">
                        {selectedInventoryPart.notes}
                      </p>
                    </section>
                  ) : null}

                  {selectedInventoryPart.field_values.some(
                    (field) =>
                      inventoryFieldDisplayValue(field) !== null
                  ) ? (
                    <section className="part-details-section">
                      <div className="part-details-section-heading">
                        <strong>Template fields</strong>
                      </div>
                      <dl className="part-details-template-fields">
                        {selectedInventoryPart.field_values
                          .filter(
                            (field) =>
                              inventoryFieldDisplayValue(field)
                              !== null
                          )
                          .map((field) => (
                            <div key={field.id}>
                              <dt>{field.label}</dt>
                              <dd>
                                {inventoryFieldDisplayValue(field)}
                              </dd>
                            </div>
                          ))}
                      </dl>
                    </section>
                  ) : null}
                </>
              ) : null}
            </div>

                        <footer className="part-details-footer">
              <span>Stock changes are recorded in history</span>
              <div className="part-details-footer-actions">
                {selectedInventoryPart ? (
                  <>
                    <button
                      className="part-details-delete-button"
                      type="button"
                      onClick={() =>
                        openPartDeleteDialog(selectedInventoryPart)}
                    >
                      Delete
                    </button>
                    <button
                      className="part-details-edit-button"
                      type="button"
                      onClick={() =>
                        openPartMetadataEditor(selectedInventoryPart)}
                    >
                      Edit details
                    </button>
                  </>
                ) : null}
                <button type="button" onClick={closePartDetails}>
                  Close
                </button>
              </div>
            </footer>
          </aside>
        </div>
      ) : null}
</div>
  );
}
