// PATCH 067: custom part type creation workspace
import {
  useEffect,
  useMemo,
  useState } from "react";
import type {
  ChangeEvent,
  FormEvent } from "react";

import { useAuth } from "../auth/AuthContext";
import "./PartManager.css";
// PATCH 094: dynamic inventory Add Part modal
import { AddPartModal } from "../components/AddPartModal";
import {
  createPartType,
  getPartTypes,
  updatePartType,
  deletePartType,
} from "../services/partTypesClient";
// PATCH 110: basic inventory browsing collection
import { getParts } from "../services/partsClient";
import type { Part, PartCollection } from "../types/parts";
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
type InventoryStockFilter = "all" | "in" | "low" | "out";

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

export function PartManager() {
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
  // PATCH 120: client-side inventory search and stock filter
  const [inventoryQuery, setInventoryQuery] = useState("");
  const [inventoryStockFilter, setInventoryStockFilter] =
    useState<InventoryStockFilter>("all");
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

  // PATCH 110: load the existing inventory collection
  useEffect(() => {
    if (!token) {
      setInventoryCollection(null);
      setInventoryLoading(false);
      return;
    }

    let cancelled = false;
    setInventoryLoading(true);
    setInventoryError(null);

    getParts(token, {
      limit: 250,
      offset: 0
    })
      .then((result) => {
        if (!cancelled) {
          setInventoryCollection(result);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setInventoryError(
            caught instanceof Error
              ? caught.message
              : "Unable to load inventory"
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setInventoryLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token, inventoryRefreshSequence]);

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

  const filteredInventoryParts = useMemo(() => {
    const normalizedQuery = inventoryQuery.trim().toLowerCase();
    const parts = inventoryCollection?.parts ?? [];

    return parts.filter((part) => {
      const matchesQuery =
        !normalizedQuery
        || [
          part.name,
          part.part_number,
          part.part_type_name,
          part.manufacturer_name
        ].some(
          (value) =>
            Boolean(
              value
              && value.toLowerCase().includes(normalizedQuery)
            )
        );

      if (!matchesQuery) {
        return false;
      }

      if (inventoryStockFilter === "in") {
        return part.available_quantity > 0 && !part.is_low_stock;
      }

      if (inventoryStockFilter === "low") {
        return part.available_quantity > 0 && part.is_low_stock;
      }

      if (inventoryStockFilter === "out") {
        return part.available_quantity <= 0;
      }

      return true;
    });
  }, [
    inventoryCollection,
    inventoryQuery,
    inventoryStockFilter
  ]);

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

  return (
    <div
      className="page-stack part-manager-page"
      data-manufacturer-preset-version="part-manager-manufacturer-preset-v106"
    >
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

      {collection ? (
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
                ? `${filteredInventoryParts.length} of ${
                    inventoryCollection?.parts.length ?? 0
                  } shown`
                : `${inventoryCollection?.total ?? 0} parts`}
            </span>
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
              disabled={inventoryLoading || !inventoryCollection}
            />
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
          && inventoryCollection.parts.length === 0 ? (
            <div className="inventory-browser-state">
              No inventory parts yet. Use Add part to create the first one.
            </div>
          ) : null}

        {!inventoryLoading
          && !inventoryError
          && inventoryCollection
          && inventoryCollection.parts.length > 0
          && filteredInventoryParts.length === 0 ? (
            <div className="inventory-browser-state inventory-filter-empty">
              <strong>No stored parts match</strong>
              <p>
                Try another search or clear the stock filter.
              </p>
              <button
                type="button"
                onClick={() => {
                  setInventoryQuery("");
                  setInventoryStockFilter("all");
                }}
              >
                Clear filters
              </button>
            </div>
          ) : null}

        {!inventoryLoading
          && !inventoryError
          && inventoryCollection
          && filteredInventoryParts.length > 0 ? (
            <div className="inventory-table-wrap">
              <table className="inventory-table">
                <thead>
                  <tr>
                    <th scope="col">Part</th>
                    <th scope="col">Type</th>
                    <th scope="col">Manufacturer</th>
                    <th scope="col">Available</th>
                    <th scope="col">Total</th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredInventoryParts.map((part) => (
                    <tr key={part.id}>
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
          ) : null}
      </section>
    </div>
  );
}
