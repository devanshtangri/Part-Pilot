import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import { getPartTypes } from "../services/partTypesClient";
import type {
  PartType,
  PartTypeCollection,
  PartTypeField
} from "../types/partTypes";

type FilterMode = "all" | "builtin" | "custom";

const FIELD_TYPE_LABELS: Record<string, string> = {
  text: "Text",
  number: "Number",
  boolean: "Yes / No",
  dropdown: "Dropdown",
  url: "URL",
  unit_value: "Unit-aware value"
};

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

export function PartManager() {
  const { token } = useAuth();
  const [collection, setCollection] =
    useState<PartTypeCollection | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [filter, setFilter] = useState<FilterMode>("all");
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <section className="page-stack part-manager-page">
      <header className="page-header part-manager-header">
        <div>
          <p className="eyebrow">Phase 4</p>
          <h1>Part Manager</h1>
          <p>
            Browse the built-in electronics-aware templates that define the
            fields available when parts are created.
          </p>
        </div>
        <span className="status-pill">Read-only foundation</span>
      </header>

      {collection ? (
        <div className="part-manager-stats">
          <div className="card">
            <span className="card-label">Part types</span>
            <strong>{collection.total}</strong>
          </div>
          <div className="card">
            <span className="card-label">Built-in</span>
            <strong>{collection.builtin_count}</strong>
          </div>
          <div className="card">
            <span className="card-label">Custom</span>
            <strong>{collection.custom_count}</strong>
          </div>
          <div className="card">
            <span className="card-label">Template fields</span>
            <strong>{collection.total_fields}</strong>
          </div>
        </div>
      ) : null}

      <div className="part-manager-toolbar">
        <label className="part-manager-search">
          <span className="sr-only">Search part types and fields</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
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
      </div>

      {isLoading ? (
        <div className="empty-state">
          <strong>Loading part templates...</strong>
          <p>Reading seeded part types and their custom fields.</p>
        </div>
      ) : null}

      {error ? (
        <div className="empty-state">
          <strong>Part Manager could not load</strong>
          <p>{error}</p>
        </div>
      ) : null}

      {!isLoading && !error && collection ? (
        <div className="part-manager-layout">
          <aside className="part-type-list" aria-label="Part types">
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
                    selectedId === partType.id ? "active" : ""
                  }`}
                  onClick={() => setSelectedId(partType.id)}
                >
                  <span>
                    <strong>{partType.name}</strong>
                    <small>{partType.field_count} fields</small>
                  </span>
                  <span
                    className={`type-origin ${
                      partType.is_builtin ? "builtin" : "custom"
                    }`}
                  >
                    {partType.is_builtin ? "Built-in" : "Custom"}
                  </span>
                </button>
              ))
            ) : (
              <div className="part-type-list-empty">
                No part types match this filter.
              </div>
            )}
          </aside>

          <article className="part-type-detail">
            {selectedType ? (
              <>
                <header className="part-type-detail-header">
                  <div>
                    <div className="detail-title-row">
                      <h2>{selectedType.name}</h2>
                      <span
                        className={`type-origin ${
                          selectedType.is_builtin ? "builtin" : "custom"
                        }`}
                      >
                        {selectedType.is_builtin ? "Built-in" : "Custom"}
                      </span>
                    </div>
                    <p>
                      {selectedType.description ||
                        `Template slug: ${selectedType.slug}`}
                    </p>
                  </div>
                  <div className="template-version">
                    Template v{selectedType.template_version}
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

                <div className="template-field-list">
                  {selectedType.fields.length > 0 ? (
                    selectedType.fields.map((field) => (
                      <div className="template-field-row" key={field.id}>
                        <div className="template-field-copy">
                          <div>
                            <strong>{field.label}</strong>
                            {field.is_required ? (
                              <span className="required-badge">Required</span>
                            ) : null}
                          </div>
                          <code>{field.field_key}</code>
                          {field.help_text ? <p>{field.help_text}</p> : null}
                        </div>

                        <div className="template-field-meta">
                          <span>{fieldTypeLabel(field.field_type)}</span>
                          {fieldSummary(field) ? (
                            <small>{fieldSummary(field)}</small>
                          ) : null}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="part-type-list-empty">
                      This type has no template fields yet.
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="part-type-list-empty">
                Select a part type to inspect its template.
              </div>
            )}
          </article>
        </div>
      ) : null}
    </section>
  );
}
