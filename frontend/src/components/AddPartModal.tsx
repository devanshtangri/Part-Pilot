import {
  useEffect,
  useMemo,
  useState
} from "react";
import type {
  ChangeEvent,
  FormEvent
} from "react";

import { createPart } from "../services/partsClient";
// PATCH 095: reusable manufacturer selector
import {
  createManufacturer,
  getManufacturers
} from "../services/manufacturersClient";
import type { Manufacturer } from "../types/manufacturers";
import type {
  CreatePartPayload,
  Part,
  PartFieldValueCreatePayload
} from "../types/parts";
import type {
  PartType,
  PartTypeField
} from "../types/partTypes";

import { PackageSelector } from "./PackageSelector";
// PATCH 160: reusable location selector in Add Part
import { LocationSelector } from "./LocationSelector";

import "./AddPartModal.css";


interface AddPartModalProps {
  token: string;
  partTypes: PartType[];
  initialPartTypeId: number | null;
  onClose: () => void;
}


interface FieldDraft {
  textValue: string;
  numberValue: string;
  booleanValue: "" | "true" | "false";
  unit: string;
}


const EMPTY_FIELD_DRAFT: FieldDraft = {
  textValue: "",
  numberValue: "",
  booleanValue: "",
  unit: ""
};


function optionsForField(field: PartTypeField): string[] {
  if (!Array.isArray(field.options)) {
    return [];
  }

  return field.options.filter(
    (option): option is string =>
      typeof option === "string"
  );
}


function initialTypeId(
  partTypes: PartType[],
  requestedId: number | null
): number | null {
  if (
    requestedId !== null
    && partTypes.some(
      (partType) =>
        partType.id === requestedId
        && partType.is_active
    )
  ) {
    return requestedId;
  }

  return (
    partTypes.find((partType) => partType.is_active)?.id
    ?? null
  );
}


function validateHttpUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return (
      parsed.protocol === "http:"
      || parsed.protocol === "https:"
    );
  } catch {
    return false;
  }
}


function normalizeTemplateFieldKey(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}


function isManufacturerField(
  field: PartTypeField
): boolean {
  const key = normalizeTemplateFieldKey(field.field_key);

  return (
    key === "manufacturer"
    || key === "manufacturer_name"
  );
}


// PATCH 115: fields already represented by dedicated core controls
function isCoreIdentificationField(
  field: PartTypeField
): boolean {
  const key = normalizeTemplateFieldKey(field.field_key);

  return (
    isManufacturerField(field)
    || key === "package"
    || key === "package_name"
  );
}


function displayPartName(part: Part): string {
  return (
    part.name
    || part.part_number
    || `Part ${part.id}`
  );
}


export function AddPartModal({
  token,
  partTypes,
  initialPartTypeId,
  onClose
}: AddPartModalProps) {
  const activeTypes = useMemo(
    () => partTypes.filter((partType) => partType.is_active),
    [partTypes]
  );

  const [partTypeId, setPartTypeId] = useState<number | null>(
    () => initialTypeId(activeTypes, initialPartTypeId)
  );
  const [partNumber, setPartNumber] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [packageName, setPackageName] = useState("");
  const [locationId, setLocationId] =
    useState<number | null>(null);
  const [notes, setNotes] = useState("");
  const [quantity, setQuantity] = useState("0");
  const [unitPrice, setUnitPrice] = useState("");
  const [purchaseLink, setPurchaseLink] = useState("");
  const [lowStockEnabled, setLowStockEnabled] =
    useState(false);
  const [lowStockThreshold, setLowStockThreshold] =
    useState("");
  const [fieldDrafts, setFieldDrafts] = useState<
    Record<number, FieldDraft>
  >({});
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [createdPart, setCreatedPart] =
    useState<Part | null>(null);
  const [manufacturers, setManufacturers] =
    useState<Manufacturer[]>([]);
  const [manufacturerId, setManufacturerId] =
    useState<number | null>(null);
  const [manufacturersLoading, setManufacturersLoading] =
    useState(true);
  const [showManufacturerCreator, setShowManufacturerCreator] =
    useState(false);
  const [newManufacturerName, setNewManufacturerName] =
    useState("");
  const [manufacturerError, setManufacturerError] =
    useState<string | null>(null);
  const [isCreatingManufacturer, setIsCreatingManufacturer] =
    useState(false);

  const selectedType = useMemo(
    () =>
      activeTypes.find(
        (partType) => partType.id === partTypeId
      ) ?? null,
    [activeTypes, partTypeId]
  );

  const selectedManufacturer = useMemo(
    () =>
      manufacturers.find(
        (manufacturer) =>
          manufacturer.id === manufacturerId
      ) ?? null,
    [manufacturers, manufacturerId]
  );

  const visibleTemplateFields = useMemo(
    () =>
      selectedType?.fields.filter(
        (field) => !isCoreIdentificationField(field)
      ) ?? [],
    [selectedType]
  );

  useEffect(() => {
    let cancelled = false;

    setManufacturersLoading(true);
    setManufacturerError(null);

    getManufacturers(token)
      .then((collection) => {
        if (!cancelled) {
          setManufacturers(collection.manufacturers);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setManufacturerError(
            caught instanceof Error
              ? caught.message
              : "Unable to load manufacturers"
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setManufacturersLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;

    function handleKeyDown(event: KeyboardEvent) {
      if (
        event.key === "Escape"
        && !isSaving
      ) {
        onClose();
      }
    }

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isSaving, onClose]);

  async function handleCreateManufacturer() {
    const cleanedName = newManufacturerName.trim();

    if (!cleanedName) {
      setManufacturerError(
        "Enter a manufacturer name."
      );
      return;
    }

    setIsCreatingManufacturer(true);
    setManufacturerError(null);

    try {
      const created = await createManufacturer(
        token,
        cleanedName
      );

      setManufacturers((current) =>
        [...current, created].sort((left, right) =>
          left.name.localeCompare(
            right.name,
            undefined,
            { sensitivity: "base" }
          )
        )
      );
      setManufacturerId(created.id);
      setNewManufacturerName("");
      setShowManufacturerCreator(false);
    } catch (caught) {
      setManufacturerError(
        caught instanceof Error
          ? caught.message
          : "Unable to create the manufacturer"
      );
    } finally {
      setIsCreatingManufacturer(false);
    }
  }

  function updateFieldDraft(
    fieldId: number,
    patch: Partial<FieldDraft>
  ) {
    setFieldDrafts((current) => ({
      ...current,
      [fieldId]: {
        ...EMPTY_FIELD_DRAFT,
        ...current[fieldId],
        ...patch
      }
    }));
  }

  function resetForAnotherPart() {
    setPartNumber("");
    setName("");
    setDescription("");
    setPackageName("");
    setLocationId(null);
    setNotes("");
    setQuantity("0");
    setUnitPrice("");
    setPurchaseLink("");
    setManufacturerId(null);
    setShowManufacturerCreator(false);
    setNewManufacturerName("");
    setManufacturerError(null);
    setLowStockEnabled(false);
    setLowStockThreshold("");
    setFieldDrafts({});
    setError(null);
    setCreatedPart(null);
  }

  function validate(): string[] {
    const issues: string[] = [];

    if (!selectedType) {
      issues.push("Select an active part type.");
      return issues;
    }

    if (!name.trim() && !partNumber.trim()) {
      issues.push(
        "Enter at least a part name or part number."
      );
    }

    const parsedQuantity = Number(quantity);
    if (
      !Number.isInteger(parsedQuantity)
      || parsedQuantity < 0
    ) {
      issues.push(
        "Quantity must be a non-negative whole number."
      );
    }

    if (unitPrice.trim()) {
      const parsedPrice = Number(unitPrice);
      if (
        !Number.isFinite(parsedPrice)
        || parsedPrice < 0
      ) {
        issues.push(
          "Unit price must be a non-negative number."
        );
      }
    }

    if (
      purchaseLink.trim()
      && !validateHttpUrl(purchaseLink.trim())
    ) {
      issues.push(
        "Purchase link must be a valid HTTP or HTTPS URL."
      );
    }

    if (lowStockEnabled) {
      const threshold = Number(lowStockThreshold);
      if (
        !Number.isInteger(threshold)
        || threshold < 0
      ) {
        issues.push(
          "Low-stock threshold must be a non-negative whole number."
        );
      }
    }

    selectedType.fields.forEach((field) => {
      if (!field.is_required) {
        return;
      }

      if (isManufacturerField(field)) {
        if (!selectedManufacturer) {
          issues.push("Manufacturer is required.");
        }
        return;
      }

      const draft = {
        ...EMPTY_FIELD_DRAFT,
        ...fieldDrafts[field.id]
      };

      if (
        field.field_type === "boolean"
        && draft.booleanValue === ""
      ) {
        issues.push(`${field.label} is required.`);
      } else if (
        ["number", "unit_value"].includes(field.field_type)
        && !draft.numberValue.trim()
      ) {
        issues.push(`${field.label} is required.`);
      } else if (
        !["boolean", "number", "unit_value"].includes(
          field.field_type
        )
        && !draft.textValue.trim()
      ) {
        issues.push(`${field.label} is required.`);
      }
    });

    return issues;
  }

  function buildFieldValue(
    field: PartTypeField
  ): PartFieldValueCreatePayload | null {
    if (isManufacturerField(field)) {
      if (!selectedManufacturer) {
        return null;
      }

      return {
        field_id: field.id,
        value_text: selectedManufacturer.name
      };
    }

    const draft = {
      ...EMPTY_FIELD_DRAFT,
      ...fieldDrafts[field.id]
    };

    if (field.field_type === "boolean") {
      if (draft.booleanValue === "") {
        return null;
      }

      return {
        field_id: field.id,
        value_bool: draft.booleanValue === "true"
      };
    }

    if (
      field.field_type === "number"
      || field.field_type === "unit_value"
    ) {
      const value = draft.numberValue.trim();
      if (!value) {
        return null;
      }

      return {
        field_id: field.id,
        value_number: value,
        unit:
          field.field_type === "unit_value"
            ? (
                draft.unit.trim()
                || field.default_unit
                || null
              )
            : null
      };
    }

    const value = draft.textValue.trim();
    if (!value) {
      return null;
    }

    return {
      field_id: field.id,
      value_text: value
    };
  }

  function buildPayload(): CreatePartPayload {
    if (!selectedType) {
      throw new Error("Select an active part type.");
    }

    return {
      part_type_id: selectedType.id,
      manufacturer_id: manufacturerId,
      location_id: locationId,
      part_number: partNumber.trim() || null,
      name: name.trim() || null,
      description: description.trim() || null,
      package: packageName.trim() || null,
      notes: notes.trim() || null,
      total_quantity: Number(quantity),
      unit_price: unitPrice.trim() || null,
      purchase_link: purchaseLink.trim() || null,
      low_stock_enabled: lowStockEnabled,
      low_stock_threshold:
        lowStockEnabled
          ? Number(lowStockThreshold)
          : null,
      field_values: selectedType.fields
        .map(buildFieldValue)
        .filter(
          (
            value
          ): value is PartFieldValueCreatePayload =>
            value !== null
        )
    };
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    const issues = validate();
    if (issues.length > 0) {
      setError(issues.join(" "));
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      const created = await createPart(
        token,
        buildPayload()
      );
      setCreatedPart(created);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to create the inventory part"
      );
    } finally {
      setIsSaving(false);
    }
  }

  function renderTemplateField(field: PartTypeField) {
    const draft = {
      ...EMPTY_FIELD_DRAFT,
      ...fieldDrafts[field.id]
    };
    const options = optionsForField(field);

    if (field.field_type === "boolean") {
      return (
        <select
          value={draft.booleanValue}
          onChange={(
            event: ChangeEvent<HTMLSelectElement>
          ) =>
            updateFieldDraft(field.id, {
              booleanValue: event.target.value as
                | ""
                | "true"
                | "false"
            })
          }
        >
          <option value="">Select yes or no</option>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
      );
    }

    if (field.field_type === "dropdown") {
      return (
        <select
          value={draft.textValue}
          onChange={(
            event: ChangeEvent<HTMLSelectElement>
          ) =>
            updateFieldDraft(field.id, {
              textValue: event.target.value
            })
          }
        >
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
        <div className="add-part-unit-control">
          <input
            type="number"
            step="any"
            value={draft.numberValue}
            onChange={(
              event: ChangeEvent<HTMLInputElement>
            ) =>
              updateFieldDraft(field.id, {
                numberValue: event.target.value
              })
            }
            placeholder="0"
          />
          <input
            value={draft.unit}
            onChange={(
              event: ChangeEvent<HTMLInputElement>
            ) =>
              updateFieldDraft(field.id, {
                unit: event.target.value
              })
            }
            placeholder={field.default_unit || "unit"}
            maxLength={30}
          />
        </div>
      );
    }

    if (field.field_type === "number") {
      return (
        <input
          type="number"
          step="any"
          value={draft.numberValue}
          onChange={(
            event: ChangeEvent<HTMLInputElement>
          ) =>
            updateFieldDraft(field.id, {
              numberValue: event.target.value
            })
          }
          placeholder="0"
        />
      );
    }

    return (
      <input
        type={field.field_type === "url" ? "url" : "text"}
        value={draft.textValue}
        onChange={(
          event: ChangeEvent<HTMLInputElement>
        ) =>
          updateFieldDraft(field.id, {
            textValue: event.target.value
          })
        }
        placeholder={
          field.help_text
          || (
            field.field_type === "url"
              ? "https://example.com"
              : field.label
          )
        }
      />
    );
  }

  return (
    <div
      className="add-part-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (
          event.target === event.currentTarget
          && !isSaving
        ) {
          onClose();
        }
      }}
    >
      <section
        className={
          `add-part-modal card${
            createdPart
              ? " add-part-modal-success"
              : ""
          }`
        }
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-part-title"
      >
        <form onSubmit={handleSubmit}>
          {!createdPart ? (
            <header className="add-part-header">
              <div>
                <p className="eyebrow">New inventory record</p>
                <h2 id="add-part-title">Add part</h2>
                <p>
                  Select a template and record the part&apos;s identifiers,
                  quantity, and specifications.
                </p>
              </div>

              <button
                className="add-part-close"
                type="button"
                onClick={onClose}
                disabled={isSaving}
                aria-label="Close Add Part dialog"
                title="Close"
              >
                ×
              </button>
            </header>
          ) : null}

          {createdPart ? (
            <div
              className="add-part-success"
              data-success-panel-version="add-part-success-panel-v113"
            >
              {/* PATCH 113: unified success confirmation */}
              <div className="add-part-success-top">
                <div className="add-part-success-mark">✓</div>

                <div className="add-part-success-copy">
                  <p className="eyebrow">Inventory updated</p>
                  <h2 id="add-part-title">Part added</h2>
                  <span>
                    {displayPartName(createdPart)} is now in inventory.
                  </span>
                </div>

                <button
                  className="add-part-close add-part-success-close"
                  type="button"
                  onClick={onClose}
                  aria-label="Close Add Part dialog"
                  title="Close"
                >
                  ×
                </button>
              </div>

              <div className="add-part-success-details">
                <div>
                  <span>Part type</span>
                  <strong>{createdPart.part_type_name}</strong>
                </div>
                <div>
                  <span>Manufacturer</span>
                  <strong>
                    {createdPart.manufacturer_name
                      || "Not specified"}
                  </strong>
                </div>
                <div>
                  <span>Location</span>
                  <strong>
                    {createdPart.location_name
                      || "Not specified"}
                  </strong>
                </div>
                <div>
                  <span>Quantity</span>
                  <strong>{createdPart.total_quantity}</strong>
                </div>
                <div>
                  <span>Part number</span>
                  {createdPart.part_number ? (
                    <code>{createdPart.part_number}</code>
                  ) : (
                    <strong>Not specified</strong>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="add-part-scroll-region">
              {error ? (
                <div className="add-part-error" role="alert">
                  {error}
                </div>
              ) : null}

              <section className="add-part-section">
                <div className="add-part-section-heading">
                  <div>
                    <strong>Part template</strong>
                    <span>
                      Template fields update when the type changes.
                    </span>
                  </div>
                </div>

                <label className="add-part-wide-control">
                  <span>Part type</span>
                  <select
                    value={partTypeId ?? ""}
                    onChange={(
                      event: ChangeEvent<HTMLSelectElement>
                    ) => {
                      setPartTypeId(
                        event.target.value
                          ? Number(event.target.value)
                          : null
                      );
                      setFieldDrafts({});
                      setError(null);
                    }}
                    autoFocus
                  >
                    {activeTypes.map((partType) => (
                      <option
                        key={partType.id}
                        value={partType.id}
                      >
                        {partType.name}
                        {partType.is_builtin
                          ? " — Built-in"
                          : " — Custom"}
                      </option>
                    ))}
                  </select>
                </label>
              </section>

              <section
                className="add-part-section"
                data-field-guidance-version="add-part-field-guidance-v115"
              >
                <div className="add-part-section-heading">
                  <div>
                    <strong>Identification</strong>
                    <span>
                      Enter the model number. Add a display name only when
                      it helps distinguish the item.
                    </span>
                  </div>
                </div>

                <div className="add-part-grid">
                  <label>
                    <span>Display name (optional)</span>
                    <input
                      value={name}
                      onChange={(
                        event: ChangeEvent<HTMLInputElement>
                      ) => setName(event.target.value)}
                      placeholder="Example: Bench stock 2N2222A"
                      maxLength={220}
                    />
                    <small>
                      Friendly label used in lists. Leave blank to use
                      the part number.
                    </small>
                  </label>

                  <label>
                    <span>Part number / model</span>
                    <input
                      value={partNumber}
                      onChange={(
                        event: ChangeEvent<HTMLInputElement>
                      ) => setPartNumber(event.target.value)}
                      placeholder="Example: 2N2222A"
                      maxLength={160}
                      spellCheck={false}
                    />
                    <small>
                      Manufacturer model, catalogue number, or internal code.
                    </small>
                  </label>

                  <label>
                    <span>Manufacturer</span>
                    <div className="add-part-manufacturer-control">
                      <select
                        value={manufacturerId ?? ""}
                        onChange={(
                          event: ChangeEvent<HTMLSelectElement>
                        ) => {
                          setManufacturerId(
                            event.target.value
                              ? Number(event.target.value)
                              : null
                          );
                          setManufacturerError(null);
                        }}
                        disabled={manufacturersLoading}
                      >
                        <option value="">
                          {manufacturersLoading
                            ? "Loading manufacturers…"
                            : "Not specified"}
                        </option>
                        {manufacturers.map((manufacturer) => (
                          <option
                            key={manufacturer.id}
                            value={manufacturer.id}
                          >
                            {manufacturer.name}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={() => {
                          setShowManufacturerCreator(
                            (current) => !current
                          );
                          setManufacturerError(null);
                        }}
                      >
                        {showManufacturerCreator
                          ? "Hide"
                          : "Add new"}
                      </button>
                    </div>

                    {showManufacturerCreator ? (
                      <div className="add-part-manufacturer-create">
                        <input
                          value={newManufacturerName}
                          onChange={(
                            event: ChangeEvent<HTMLInputElement>
                          ) =>
                            setNewManufacturerName(
                              event.target.value
                            )
                          }
                          placeholder="Manufacturer name"
                          maxLength={180}
                        />
                        <button
                          type="button"
                          onClick={handleCreateManufacturer}
                          disabled={isCreatingManufacturer}
                        >
                          {isCreatingManufacturer
                            ? "Saving…"
                            : "Save"}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setShowManufacturerCreator(false);
                            setNewManufacturerName("");
                            setManufacturerError(null);
                          }}
                          disabled={isCreatingManufacturer}
                        >
                          Cancel
                        </button>
                      </div>
                    ) : null}

                    {manufacturerError ? (
                      <small
                        className="add-part-manufacturer-error"
                        role="alert"
                      >
                        {manufacturerError}
                      </small>
                    ) : null}
                  </label>

                  <PackageSelector
                    token={token}
                    value={packageName}
                    onChange={setPackageName}
                    disabled={isSaving}
                  />
                  <LocationSelector
                    token={token}
                    value={locationId}
                    onChange={(value) => {
                      setLocationId(value);
                      setError(null);
                    }}
                    disabled={isSaving}
                  />

                  <label>
                    <span>Quantity</span>
                    <input
                      type="number"
                      min="0"
                      step="1"
                      value={quantity}
                      onChange={(
                        event: ChangeEvent<HTMLInputElement>
                      ) => setQuantity(event.target.value)}
                    />
                  </label>
                </div>

                <label className="add-part-wide-control">
                  <span>Description</span>
                  <textarea
                    value={description}
                    onChange={(
                      event: ChangeEvent<HTMLTextAreaElement>
                    ) => setDescription(event.target.value)}
                    placeholder="Optional identification or usage details"
                    rows={3}
                    maxLength={5000}
                  />
                </label>
              </section>

              <section className="add-part-section">
                <div className="add-part-section-heading">
                  <div>
                    <strong>Purchase and stock</strong>
                    <span>
                      Price is per individual unit.
                    </span>
                  </div>
                </div>

                <div className="add-part-grid">
                  <label>
                    <span>Unit price</span>
                    <input
                      type="number"
                      min="0"
                      step="any"
                      value={unitPrice}
                      onChange={(
                        event: ChangeEvent<HTMLInputElement>
                      ) => setUnitPrice(event.target.value)}
                      placeholder="0.00"
                    />
                  </label>

                  <label>
                    <span>Purchase link</span>
                    <input
                      type="url"
                      value={purchaseLink}
                      onChange={(
                        event: ChangeEvent<HTMLInputElement>
                      ) => setPurchaseLink(event.target.value)}
                      placeholder="https://..."
                      maxLength={2000}
                    />
                  </label>
                </div>

                <div className="add-part-low-stock-row">
                  <label className="add-part-checkbox">
                    <input
                      type="checkbox"
                      checked={lowStockEnabled}
                      onChange={(
                        event: ChangeEvent<HTMLInputElement>
                      ) => {
                        setLowStockEnabled(event.target.checked);
                        if (!event.target.checked) {
                          setLowStockThreshold("");
                        }
                      }}
                    />
                    <span>Enable low-stock warning</span>
                  </label>

                  {lowStockEnabled ? (
                    <label>
                      <span>Warn at or below</span>
                      <input
                        type="number"
                        min="0"
                        step="1"
                        value={lowStockThreshold}
                        onChange={(
                          event: ChangeEvent<HTMLInputElement>
                        ) =>
                          setLowStockThreshold(event.target.value)
                        }
                        placeholder="0"
                      />
                    </label>
                  ) : null}
                </div>
              </section>

              <section className="add-part-section">
                <div className="add-part-section-heading">
                  <div>
                    <strong>
                      {selectedType?.name || "Template"} fields
                    </strong>
                    <span>
                      {selectedType
                        ? `${visibleTemplateFields.length} additional specification fields`
                        : "Select a template"}
                    </span>
                  </div>
                </div>

                {visibleTemplateFields.length ? (
                  <div className="add-part-template-grid">
                    {visibleTemplateFields.map((field) => (
                      <label
                        className={
                          field.field_type === "url"
                            ? "add-part-wide-control"
                            : ""
                        }
                        key={field.id}
                      >
                        <span>
                          {field.label}
                          {field.is_required ? (
                            <b>Required</b>
                          ) : null}
                        </span>
                        {renderTemplateField(field)}
                        {field.help_text ? (
                          <small>{field.help_text}</small>
                        ) : null}
                      </label>
                    ))}
                  </div>
                ) : (
                  <div className="add-part-empty-template">
                    This template has no additional fields.
                  </div>
                )}
              </section>

              <section className="add-part-section">
                <div className="add-part-section-heading">
                  <div>
                    <strong>Notes</strong>
                    <span>Optional internal context.</span>
                  </div>
                </div>

                <label className="add-part-wide-control">
                  <span>Inventory notes</span>
                  <textarea
                    value={notes}
                    onChange={(
                      event: ChangeEvent<HTMLTextAreaElement>
                    ) => setNotes(event.target.value)}
                    placeholder="Supplier, project, storage, or handling notes"
                    rows={3}
                    maxLength={10000}
                  />
                </label>
              </section>
            </div>
          )}

          <footer className="add-part-actions">
            {createdPart ? (
              <>
                <button
                  type="button"
                  onClick={resetForAnotherPart}
                >
                  Add another
                </button>
                <button
                  className="add-part-primary"
                  type="button"
                  onClick={onClose}
                >
                  Done
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  onClick={onClose}
                  disabled={isSaving}
                >
                  Cancel
                </button>
                <button
                  className="add-part-primary"
                  type="submit"
                  disabled={
                    isSaving
                    || !selectedType
                  }
                >
                  {isSaving ? "Adding…" : "Add to inventory"}
                </button>
              </>
            )}
          </footer>
        </form>
      </section>
    </div>
  );
}
