import {
  useEffect,
  useMemo,
  useState
} from "react";
import type {
  ChangeEvent,
  KeyboardEvent
} from "react";

import {
  createPackage,
  getPackages
} from "../services/packagesClient";
import type { PackageOption } from "../types/packages";

import "./PackageSelector.css";


interface PackageSelectorProps {
  token: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}


function sortPackages(
  packages: PackageOption[]
): PackageOption[] {
  return [...packages].sort((left, right) =>
    left.name.localeCompare(
      right.name,
      undefined,
      {
        numeric: true,
        sensitivity: "base"
      }
    )
  );
}


export function PackageSelector({
  token,
  value,
  onChange,
  disabled = false
}: PackageSelectorProps) {
  const [packages, setPackages] =
    useState<PackageOption[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] =
    useState<string | null>(null);
  const [showCreator, setShowCreator] = useState(false);
  const [newPackageName, setNewPackageName] = useState("");
  const [createError, setCreateError] =
    useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const selectedValueExists = useMemo(
    () =>
      !value
      || packages.some(
        (packageOption) => packageOption.name === value
      ),
    [packages, value]
  );

  useEffect(() => {
    let cancelled = false;

    setIsLoading(true);
    setLoadError(null);

    getPackages(token)
      .then((collection) => {
        if (!cancelled) {
          setPackages(sortPackages(collection.packages));
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setLoadError(
            caught instanceof Error
              ? caught.message
              : "Unable to load package options"
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  async function handleCreatePackage() {
    const cleanedName = newPackageName.trim();

    if (!cleanedName) {
      setCreateError("Enter a package or form-factor name.");
      return;
    }

    setIsCreating(true);
    setCreateError(null);

    try {
      const created = await createPackage(token, cleanedName);

      setPackages((current) =>
        sortPackages([
          ...current.filter(
            (item) => item.id !== created.id
          ),
          created
        ])
      );
      onChange(created.name);
      setNewPackageName("");
      setShowCreator(false);
    } catch (caught) {
      setCreateError(
        caught instanceof Error
          ? caught.message
          : "Unable to create the package option"
      );
    } finally {
      setIsCreating(false);
    }
  }

  function handleCreatorKeyDown(
    event: KeyboardEvent<HTMLInputElement>
  ) {
    if (event.key !== "Enter") {
      return;
    }

    event.preventDefault();
    void handleCreatePackage();
  }

  return (
    <div
      className="add-part-package-field"
      data-package-selector-version="add-part-package-selector-v129"
    >
      <span>Package / form factor</span>

      <div className="add-part-package-control">
        <select
          value={value}
          onChange={(
            event: ChangeEvent<HTMLSelectElement>
          ) => {
            onChange(event.target.value);
            setCreateError(null);
          }}
          disabled={disabled || isLoading}
          aria-label="Package or form factor"
        >
          <option value="">
            {isLoading
              ? "Loading package options..."
              : "Not specified"}
          </option>

          {!selectedValueExists && value ? (
            <option value={value}>{value}</option>
          ) : null}

          {packages.map((packageOption) => (
            <option
              key={packageOption.id}
              value={packageOption.name}
            >
              {packageOption.name}
              {packageOption.is_builtin ? "" : " — Custom"}
            </option>
          ))}
        </select>

        <button
          type="button"
          onClick={() => {
            setShowCreator((current) => !current);
            setCreateError(null);
          }}
          disabled={disabled || isCreating}
          aria-expanded={showCreator}
        >
          {showCreator ? "Cancel" : "Add new"}
        </button>
      </div>

      <small>
        Select a reusable electronics package, footprint, or module format.
      </small>

      {loadError ? (
        <div
          className="add-part-package-error"
          role="alert"
        >
          {loadError}
        </div>
      ) : null}

      {showCreator ? (
        <div className="add-part-package-creator">
          <input
            value={newPackageName}
            onChange={(
              event: ChangeEvent<HTMLInputElement>
            ) => {
              setNewPackageName(event.target.value);
              setCreateError(null);
            }}
            onKeyDown={handleCreatorKeyDown}
            placeholder="Example: DFN-8"
            maxLength={120}
            autoFocus
            disabled={disabled || isCreating}
          />
          <button
            type="button"
            onClick={() => void handleCreatePackage()}
            disabled={
              disabled
              || isCreating
              || !newPackageName.trim()
            }
          >
            {isCreating ? "Adding..." : "Add package"}
          </button>
        </div>
      ) : null}

      {createError ? (
        <div
          className="add-part-package-error"
          role="alert"
        >
          {createError}
        </div>
      ) : null}
    </div>
  );
}
