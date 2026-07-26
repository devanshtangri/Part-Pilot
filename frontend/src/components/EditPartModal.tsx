// PATCH 143: prefilled existing-part metadata edit modal
import {
  useEffect,
  useMemo,
  useState
} from "react";
import type {
  ChangeEvent,
  FormEvent
} from "react";

import {
  createManufacturer,
  getManufacturers
} from "../services/manufacturersClient";
import { updatePart } from "../services/partsClient";
import type { Manufacturer } from "../types/manufacturers";
import type {
  Part,
  PartFieldValueCreatePayload,
  UpdatePartPayload
} from "../types/parts";
import type {
  PartType,
  PartTypeField
} from "../types/partTypes";

import { PackageSelector } from "./PackageSelector";
// PATCH 160: reusable location selector in Edit Part
import { LocationSelector } from "./LocationSelector";

import "./AddPartModal.css";
import "./EditPartModal.css";


interface EditPartModalProps {
  token: string;
  part: Part;
  partType: PartType;
  onClose: () => void;
  onSaved: (part: Part) => void;
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


function normalizeTemplateFieldKey(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}


function isManufacturerField(field: PartTypeField): boolean {
  const key = normalizeTemplateFieldKey(field.field_key);
  return key === "manufacturer" || key === "manufacturer_name";
}


function isPackageField(field: PartTypeField): boolean {
  const key = normalizeTemplateFieldKey(field.field_key);
  return key === "package" || key === "package_name";
}


function isCoreIdentificationField(field: PartTypeField): boolean {
  return isManufacturerField(field) || isPackageField(field);
}


function optionsForField(field: PartTypeField): string[] {
  if (!Array.isArray(field.options)) {
    return [];
  }

  return field.options.filter(
    (option): option is string => typeof option === "string"
  );
}


function validateHttpUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}



// PATCH 146: trim insignificant fixed-scale decimal padding
function trimDecimalInputValue(value: string | null): string {
  if (!value) {
    return "";
  }

  if (!/^-?\d+(?:\.\d+)?$/.test(value)) {
    return value;
  }

  if (!value.includes(".")) {
    return value;
  }

  return value
    .replace(/0+$/, "")
    .replace(/\.$/, "");
}


function initialFieldDrafts(part: Part): Record<number, FieldDraft> {
  const drafts: Record<number, FieldDraft> = {};

  part.field_values.forEach((value) => {
    drafts[value.field_id] = {
      textValue: value.value_text ?? "",
      numberValue: trimDecimalInputValue(value.value_number),
      booleanValue:
        value.value_bool === null
          ? ""
          : value.value_bool
            ? "true"
            : "false",
      unit: value.unit ?? ""
    };
  });

  return drafts;
}


function sortManufacturers(
  manufacturers: Manufacturer[]
): Manufacturer[] {
  return [...manufacturers].sort((left, right) =>
    left.name.localeCompare(
      right.name,
      undefined,
      { sensitivity: "base" }
    )
  );
}


export function EditPartModal({
  token,
  part,
  partType,
  onClose,
  onSaved
}: EditPartModalProps) {
  const [partNumber, setPartNumber] = useState(part.part_number ?? "");
  const [name, setName] = useState(part.name ?? "");
  const [description, setDescription] =
    useState(part.description ?? "");
  const [packageName, setPackageName] = useState(part.package ?? "");
  const [locationId, setLocationId] =
    useState<number | null>(part.location_id);
  const [notes, setNotes] = useState(part.notes ?? "");
  const [unitPrice, setUnitPrice] = useState(
    trimDecimalInputValue(part.unit_price)
  );
  const [purchaseLink, setPurchaseLink] =
    useState(part.purchase_link ?? "");
  const [lowStockEnabled, setLowStockEnabled] =
    useState(part.low_stock_enabled);
  const [lowStockThreshold, setLowStockThreshold] = useState(
    part.low_stock_threshold === null
      ? ""
      : String(part.low_stock_threshold)
  );
  const [fieldDrafts, setFieldDrafts] =
    useState<Record<number, FieldDraft>>(
      () => initialFieldDrafts(part)
    );
  const [manufacturers, setManufacturers] =
    useState<Manufacturer[]>([]);
  const [manufacturerId, setManufacturerId] =
    useState<number | null>(part.manufacturer_id);
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
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const visibleTemplateFields = useMemo(
    () =>
      partType.fields.filter(
        (field) => !isCoreIdentificationField(field)
      ),
    [partType]
  );

  const manufacturerField = useMemo(
    () => partType.fields.find(isManufacturerField) ?? null,
    [partType]
  );
  const packageField = useMemo(
    () => partType.fields.find(isPackageField) ?? null,
    [partType]
  );
  const selectedManufacturer = useMemo(
    () =>
      manufacturers.find(
        (manufacturer) => manufacturer.id === manufacturerId
      ) ?? null,
    [manufacturers, manufacturerId]
  );

  useEffect(() => {
    let cancelled = false;

    setManufacturersLoading(true);
    setManufacturerError(null);
    getManufacturers(token)
      .then((collection) => {
        if (!cancelled) {
          setManufacturers(
            sortManufacturers(collection.manufacturers)
          );
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
      if (event.key === "Escape" && !isSaving) {
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
    setError(null);
  }

  async function handleCreateManufacturer() {
    const cleanedName = newManufacturerName
      .trim()
      .replace(/\s+/g, " ");

    if (!cleanedName) {
      setManufacturerError("Enter a manufacturer name.");
      return;
    }

    setIsCreatingManufacturer(true);
    setManufacturerError(null);

    try {
      const created = await createManufacturer(token, cleanedName);
      setManufacturers((current) =>
        sortManufacturers([
          ...current.filter((item) => item.id !== created.id),
          created
        ])
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

  function validate(): string[] {
    const issues: string[] = [];

    if (!name.trim() && !partNumber.trim()) {
      issues.push("Enter at least a part name or part number.");
    }

    if (unitPrice.trim()) {
      const parsedPrice = Number(unitPrice);
      if (!Number.isFinite(parsedPrice) || parsedPrice < 0) {
        issues.push("Unit price must be a non-negative number.");
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
      if (!Number.isInteger(threshold) || threshold < 0) {
        issues.push(
          "Low-stock threshold must be a non-negative whole number."
        );
      }
    }

    if (
      manufacturerField?.is_required
      && manufacturerId === null
    ) {
      issues.push("Manufacturer is required.");
    }

    if (packageField?.is_required && !packageName.trim()) {
      issues.push("Package / form factor is required.");
    }

    visibleTemplateFields.forEach((field) => {
      const draft = {
        ...EMPTY_FIELD_DRAFT,
        ...fieldDrafts[field.id]
      };

      if (field.is_required) {
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
      }

      if (
        ["number", "unit_value"].includes(field.field_type)
        && draft.numberValue.trim()
        && !Number.isFinite(Number(draft.numberValue))
      ) {
        issues.push(`${field.label} must be numeric.`);
      }

      if (
        field.field_type === "url"
        && draft.textValue.trim()
        && !validateHttpUrl(draft.textValue.trim())
      ) {
        issues.push(
          `${field.label} must be a valid HTTP or HTTPS URL.`
        );
      }

      if (
        field.field_type === "dropdown"
        && draft.textValue.trim()
        && !optionsForField(field).includes(draft.textValue.trim())
      ) {
        issues.push(`${field.label} has an invalid option.`);
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

    if (isPackageField(field)) {
      const value = packageName.trim();
      if (!value) {
        return null;
      }

      return {
        field_id: field.id,
        value_text: value
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

  function buildPayload(): UpdatePartPayload {
    return {
      part_type_id: part.part_type_id,
      manufacturer_id: manufacturerId,
      location_id: locationId,
      part_number: partNumber.trim() || null,
      name: name.trim() || null,
      description: description.trim() || null,
      package: packageName.trim() || null,
      notes: notes.trim() || null,
      unit_price: unitPrice.trim() || null,
      purchase_link: purchaseLink.trim() || null,
      low_stock_enabled: lowStockEnabled,
      low_stock_threshold:
        lowStockEnabled
          ? Number(lowStockThreshold)
          : null,
      field_values: partType.fields
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
      const updated = await updatePart(
        token,
        part.id,
        buildPayload()
      );
      onSaved(updated);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to update the inventory part"
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
          disabled={isSaving}
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
          disabled={isSaving}
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
            disabled={isSaving}
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
            disabled={isSaving}
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
          disabled={isSaving}
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
        disabled={isSaving}
      />
    );
  }

  return (
    <div
      className="add-part-backdrop edit-part-backdrop"
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
        className="add-part-modal edit-part-modal card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-part-title"
        data-part-metadata-edit-version="part-metadata-edit-v143"
        data-drawer-transition-version="part-metadata-edit-drawer-transition-v144"
        data-decimal-trim-version="part-metadata-edit-decimal-trim-v146"
      >
        <form onSubmit={handleSubmit}>
          <header className="add-part-header">
            <div>
              <p className="eyebrow">Inventory record</p>
              <h2 id="edit-part-title">Edit details</h2>
              <p>
                Update identification, catalogue values, alerts, and
                specifications. Stock quantities remain unchanged.
              </p>
            </div>
            <button
              className="add-part-close"
              type="button"
              onClick={onClose}
              disabled={isSaving}
              aria-label="Close Edit details dialog"
              title="Close"
            >
              ×
            </button>
          </header>

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
                    The template is fixed for this edit workflow.
                  </span>
                </div>
              </div>
              <div className="edit-part-template-summary">
                <span>Part type</span>
                <strong>{partType.name}</strong>
                <small>
                  Type changes require a separate migration-safe workflow.
                </small>
              </div>
            </section>

            <section className="add-part-section">
              <div className="add-part-section-heading">
                <div>
                  <strong>Identification</strong>
                  <span>
                    Keep either a display name or part number.
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
                    ) => {
                      setName(event.target.value);
                      setError(null);
                    }}
                    placeholder="Example: Bench stock 2N2222A"
                    maxLength={220}
                    autoFocus
                    disabled={isSaving}
                  />
                </label>

                <label>
                  <span>Part number / model</span>
                  <input
                    value={partNumber}
                    onChange={(
                      event: ChangeEvent<HTMLInputElement>
                    ) => {
                      setPartNumber(event.target.value);
                      setError(null);
                    }}
                    placeholder="Example: 2N2222A"
                    maxLength={160}
                    spellCheck={false}
                    disabled={isSaving}
                  />
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
                        setError(null);
                      }}
                      disabled={manufacturersLoading || isSaving}
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
                      disabled={isSaving}
                    >
                      {showManufacturerCreator ? "Hide" : "Add new"}
                    </button>
                  </div>

                  {showManufacturerCreator ? (
                    <div className="add-part-manufacturer-create">
                      <input
                        value={newManufacturerName}
                        onChange={(
                          event: ChangeEvent<HTMLInputElement>
                        ) => {
                          setNewManufacturerName(event.target.value);
                          setManufacturerError(null);
                        }}
                        placeholder="Manufacturer name"
                        maxLength={180}
                        disabled={isCreatingManufacturer || isSaving}
                      />
                      <button
                        type="button"
                        onClick={() => void handleCreateManufacturer()}
                        disabled={
                          isCreatingManufacturer
                          || isSaving
                          || !newManufacturerName.trim()
                        }
                      >
                        {isCreatingManufacturer ? "Saving…" : "Save"}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setShowManufacturerCreator(false);
                          setNewManufacturerName("");
                          setManufacturerError(null);
                        }}
                        disabled={isCreatingManufacturer || isSaving}
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
                  onChange={(value) => {
                    setPackageName(value);
                    setError(null);
                  }}
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
              </div>

              <label className="add-part-wide-control">
                <span>Description</span>
                <textarea
                  value={description}
                  onChange={(
                    event: ChangeEvent<HTMLTextAreaElement>
                  ) => {
                    setDescription(event.target.value);
                    setError(null);
                  }}
                  placeholder="Optional identification or usage details"
                  rows={3}
                  maxLength={5000}
                  disabled={isSaving}
                />
              </label>
            </section>

            <section className="add-part-section">
              <div className="add-part-section-heading">
                <div>
                  <strong>Purchase and stock alerts</strong>
                  <span>
                    Quantity changes stay in the separate stock workflow.
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
                    ) => {
                      setUnitPrice(event.target.value);
                      setError(null);
                    }}
                    placeholder="0.00"
                    disabled={isSaving}
                  />
                </label>

                <label>
                  <span>Purchase link</span>
                  <input
                    type="url"
                    value={purchaseLink}
                    onChange={(
                      event: ChangeEvent<HTMLInputElement>
                    ) => {
                      setPurchaseLink(event.target.value);
                      setError(null);
                    }}
                    placeholder="https://..."
                    maxLength={2000}
                    disabled={isSaving}
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
                      setError(null);
                    }}
                    disabled={isSaving}
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
                      ) => {
                        setLowStockThreshold(event.target.value);
                        setError(null);
                      }}
                      placeholder="0"
                      disabled={isSaving}
                    />
                  </label>
                ) : null}
              </div>
            </section>

            <section className="add-part-section">
              <div className="add-part-section-heading">
                <div>
                  <strong>{partType.name} fields</strong>
                  <span>
                    {visibleTemplateFields.length}
                    {" "}additional specification fields
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
                        {field.is_required ? <b>Required</b> : null}
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
                  ) => {
                    setNotes(event.target.value);
                    setError(null);
                  }}
                  placeholder="Supplier, project, storage, or handling notes"
                  rows={3}
                  maxLength={10000}
                  disabled={isSaving}
                />
              </label>
            </section>
          </div>

          <footer className="add-part-actions">
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
              disabled={isSaving || manufacturersLoading}
            >
              {isSaving ? "Saving…" : "Save changes"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  );
}
