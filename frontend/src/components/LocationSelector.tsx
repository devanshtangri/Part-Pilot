import {
  useEffect,
  useMemo,
  useState
} from "react";
import type { ChangeEvent } from "react";

import {
  createLocation,
  getLocations
} from "../services/locationsClient";
import type { LocationOption } from "../types/locations";

import "./LocationSelector.css";


interface LocationSelectorProps {
  token: string;
  value: number | null;
  onChange: (locationId: number | null) => void;
  disabled?: boolean;
}


function sortLocations(
  locations: LocationOption[]
): LocationOption[] {
  return [...locations].sort((left, right) =>
    left.name.localeCompare(
      right.name,
      undefined,
      { sensitivity: "base" }
    )
  );
}


// PATCH 160: shared reusable location selector
export function LocationSelector({
  token,
  value,
  onChange,
  disabled = false
}: LocationSelectorProps) {
  const [locations, setLocations] =
    useState<LocationOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreator, setShowCreator] = useState(false);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const selectedLocation = useMemo(
    () =>
      locations.find((location) => location.id === value)
      ?? null,
    [locations, value]
  );

  useEffect(() => {
    let cancelled = false;

    setLoading(true);
    setError(null);
    getLocations(token)
      .then((collection) => {
        if (!cancelled) {
          setLocations(sortLocations(collection.locations));
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setError(
            caught instanceof Error
              ? caught.message
              : "Unable to load locations"
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  async function handleCreateLocation() {
    const cleanedName = newName.trim();

    if (!cleanedName) {
      setError("Enter a location name.");
      return;
    }

    setCreating(true);
    setError(null);
    try {
      const created = await createLocation(token, {
        name: cleanedName,
        note: null
      });
      setLocations((current) =>
        sortLocations([
          ...current.filter((item) => item.id !== created.id),
          created
        ])
      );
      onChange(created.id);
      setNewName("");
      setShowCreator(false);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to create the location"
      );
    } finally {
      setCreating(false);
    }
  }

  return (
    <label
      className="location-selector"
      data-location-assignment-version="location-assignment-v160"
    >
      <span>Location</span>
      <div className="location-selector-control">
        <select
          value={value ?? ""}
          onChange={(
            event: ChangeEvent<HTMLSelectElement>
          ) => {
            onChange(
              event.target.value
                ? Number(event.target.value)
                : null
            );
            setError(null);
          }}
          disabled={disabled || loading || creating}
          aria-label="Inventory location"
        >
          <option value="">
            {loading ? "Loading locations…" : "Not specified"}
          </option>
          {locations.map((location) => (
            <option key={location.id} value={location.id}>
              {location.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => {
            setShowCreator((current) => !current);
            setError(null);
          }}
          disabled={disabled || creating}
        >
          {showCreator ? "Hide" : "Add new"}
        </button>
      </div>

      {selectedLocation?.note ? (
        <small className="location-selector-note">
          {selectedLocation.note}
        </small>
      ) : null}

      {showCreator ? (
        <div className="location-selector-create">
          <input
            value={newName}
            onChange={(
              event: ChangeEvent<HTMLInputElement>
            ) => {
              setNewName(event.target.value);
              setError(null);
            }}
            placeholder="Example: Drawer A3"
            maxLength={180}
            disabled={disabled || creating}
          />
          <button
            type="button"
            onClick={() => void handleCreateLocation()}
            disabled={
              disabled
              || creating
              || !newName.trim()
            }
          >
            {creating ? "Saving…" : "Save"}
          </button>
          <button
            type="button"
            onClick={() => {
              setShowCreator(false);
              setNewName("");
              setError(null);
            }}
            disabled={disabled || creating}
          >
            Cancel
          </button>
        </div>
      ) : null}

      {error ? (
        <small
          className="location-selector-error"
          role="alert"
        >
          {error}
        </small>
      ) : null}

      <small>
        Optional reusable storage position for this inventory record.
      </small>
    </label>
  );
}
