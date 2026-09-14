import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import {
  importMoleculeFromPubChem,
  importMoleculeFromXyz,
  previewMoleculeFromPubChem,
  previewMoleculeFromXyz,
  searchPubChem,
} from "@/api/molecules";
import { getApiErrorMessage, getErrorMessage, isApiErrorLike } from "@/lib/error-handler";
import type { MoleculeImportPreviewResponse, PubChemSearchResult, UUID } from "@/types/run";

export type MoleculeImportMode = "pubchem" | "xyz";
export type PubChemImportStep = "search" | "configure";

interface UsePubChemImportOptions {
  readonly onImported: (moleculeId: UUID) => void;
}

function parseInteger(value: string, fallback: number): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) ? parsed : fallback;
}

export function usePubChemImport({ onImported }: UsePubChemImportOptions) {
  const searchRequestIdRef = useRef(0);
  const previewRequestIdRef = useRef(0);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [mode, setMode] = useState<MoleculeImportMode>("pubchem");
  const [step, setStep] = useState<PubChemImportStep>("search");
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<PubChemSearchResult[]>([]);
  const [searchResultsUpdating, setSearchResultsUpdating] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<PubChemSearchResult | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState<MoleculeImportPreviewResponse | null>(null);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [xyzName, setXyzName] = useState("");
  const [xyzText, setXyzText] = useState("");
  const [xyzCharge, setXyzCharge] = useState("0");
  const [xyzMultiplicity, setXyzMultiplicity] = useState("1");

  function reset() {
    setMode("pubchem");
    setStep("search");
    setQuery("");
    setSearching(false);
    setSearchResults([]);
    setSearchResultsUpdating(false);
    setSearchError(null);
    setSelectedCandidate(null);
    setDisplayName("");
    setPreviewing(false);
    setPreview(null);
    setImporting(false);
    setImportError(null);
    setXyzName("");
    setXyzText("");
    setXyzCharge("0");
    setXyzMultiplicity("1");
  }

  function open(searchQuery?: string) {
    reset();
    setDialogOpen(true);
    if (searchQuery) {
      setQuery(searchQuery);
    }
  }

  function close() {
    setDialogOpen(false);
    reset();
  }

  function updateMode(nextMode: MoleculeImportMode) {
    setMode(nextMode);
    setImportError(null);
    setPreview(null);
    if (nextMode === "pubchem") {
      setStep("search");
    }
  }

  function updateDisplayName(nextName: string) {
    setDisplayName(nextName);
    setPreview(null);
    setImportError(null);
  }

  const search = useCallback(async () => {
    const trimmedQuery = query.trim();
    if (!trimmedQuery) return;

    const currentRequestId = ++searchRequestIdRef.current;

    setSearching(true);
    setSearchResultsUpdating(true);
    setSearchError(null);

    try {
      const data = await searchPubChem(trimmedQuery);
      if (currentRequestId !== searchRequestIdRef.current) return;

      if (data.results.length === 0) {
        setSearchError("No compounds found. Try a different name or spelling.");
        setSearchResults([]);
      } else {
        setSearchResults(data.results);
      }
    } catch (error) {
      if (currentRequestId === searchRequestIdRef.current) {
        setSearchError(getApiErrorMessage(error, "Search failed"));
      }
    } finally {
      if (currentRequestId === searchRequestIdRef.current) {
        setSearching(false);
        setSearchResultsUpdating(false);
      }
    }
  }, [query]);

  const previewSelectedCandidate = useCallback(
    async (candidate: PubChemSearchResult, nextDisplayName: string) => {
      const currentRequestId = ++previewRequestIdRef.current;
      const trimmedDisplayName = nextDisplayName.trim();

      setPreviewing(true);
      setImportError(null);

      try {
        const data = await previewMoleculeFromPubChem({
          name: candidate.name,
          ...(trimmedDisplayName ? { display_name: trimmedDisplayName } : {}),
        });
        if (currentRequestId !== previewRequestIdRef.current) return;
        setPreview(data);
      } catch (error) {
        if (currentRequestId === previewRequestIdRef.current) {
          setPreview(null);
          setImportError(getApiErrorMessage(error, "Preview failed"));
        }
      } finally {
        if (currentRequestId === previewRequestIdRef.current) {
          setPreviewing(false);
        }
      }
    },
    [],
  );

  function selectCandidate(candidate: PubChemSearchResult) {
    setSelectedCandidate(candidate);
    setDisplayName(candidate.name);
    setPreview(null);
    setImportError(null);
    setStep("configure");
  }

  async function importSelected() {
    if (!selectedCandidate) return;

    setImporting(true);
    setImportError(null);

    try {
      const trimmedDisplayName = displayName.trim();
      const result = await importMoleculeFromPubChem({
        name: selectedCandidate.name,
        ...(trimmedDisplayName ? { display_name: trimmedDisplayName } : {}),
      });
      const requestedName = trimmedDisplayName || selectedCandidate.name;
      const resolvedName = result.name;
      const reusedExisting = requestedName.toLowerCase() !== resolvedName.toLowerCase();

      if (reusedExisting) {
        toast.success("Molecule already exists", {
          description: `Opened existing molecule "${resolvedName}" from the library.`,
        });
      } else {
        toast.success("Import successful", {
          description: `"${resolvedName}" has been added to the library.`,
        });
      }

      setDialogOpen(false);
      onImported(result.id);
    } catch (error) {
      if (isApiErrorLike(error)) {
        if (error.status === 409) {
          setImportError("This molecule already exists in the library.");
        } else if (error.status === 404) {
          setImportError("No 3D structure found in PubChem for this compound.");
        } else {
          setImportError(error.message);
        }
      } else {
        setImportError(getErrorMessage(error, "Import failed"));
      }
    } finally {
      setImporting(false);
    }
  }

  async function previewXyz() {
    const trimmedXyz = xyzText.trim();
    if (!trimmedXyz) {
      setImportError("Paste XYZ coordinates before previewing.");
      return;
    }

    setPreviewing(true);
    setImportError(null);
    setPreview(null);

    try {
      const data = await previewMoleculeFromXyz({
        xyz: trimmedXyz,
        ...(xyzName.trim() ? { name: xyzName.trim() } : {}),
        charge: parseInteger(xyzCharge, 0),
        multiplicity: parseInteger(xyzMultiplicity, 1),
        derive_active_space: true,
      });
      setPreview(data);
      if (!xyzName.trim()) {
        setXyzName(data.name);
      }
    } catch (error) {
      setImportError(getApiErrorMessage(error, "XYZ preview failed"));
    } finally {
      setPreviewing(false);
    }
  }

  async function importXyz() {
    const trimmedName = xyzName.trim();
    const trimmedXyz = xyzText.trim();
    if (!trimmedName || !trimmedXyz) {
      setImportError("Provide a molecule name and XYZ coordinates before importing.");
      return;
    }
    if (preview?.source === "xyz" && preview.commit_action === "name_conflict") {
      setImportError("Choose a different molecule name before importing.");
      return;
    }

    setImporting(true);
    setImportError(null);

    try {
      const result = await importMoleculeFromXyz({
        name: trimmedName,
        xyz: trimmedXyz,
        charge: parseInteger(xyzCharge, 0),
        multiplicity: parseInteger(xyzMultiplicity, 1),
        derive_active_space: true,
      });
      toast.success("Import successful", {
        description: `"${result.name}" has been added to the library.`,
      });
      setDialogOpen(false);
      onImported(result.id);
    } catch (error) {
      setImportError(getApiErrorMessage(error, "XYZ import failed"));
    } finally {
      setImporting(false);
    }
  }

  useEffect(() => {
    if (query.trim().length < 2) {
      setSearchResults([]);
      setSearchResultsUpdating(false);
      setSearchError(null);
      return;
    }

    const timer = setTimeout(() => {
      void search();
    }, 400);

    return () => clearTimeout(timer);
  }, [query, search]);

  useEffect(() => {
    if (mode !== "pubchem" || step !== "configure" || !selectedCandidate) {
      return;
    }

    const timer = setTimeout(() => {
      void previewSelectedCandidate(selectedCandidate, displayName);
    }, 250);

    return () => clearTimeout(timer);
  }, [displayName, mode, previewSelectedCandidate, selectedCandidate, step]);

  return {
    dialogOpen,
    mode,
    step,
    query,
    searching,
    searchResults,
    searchResultsUpdating,
    searchError,
    selectedCandidate,
    displayName,
    previewing,
    preview,
    importing,
    importError,
    xyzName,
    xyzText,
    xyzCharge,
    xyzMultiplicity,
    setDialogOpen,
    setMode: updateMode,
    setStep,
    setQuery,
    setSearchError,
    setDisplayName: updateDisplayName,
    setImportError,
    setXyzName,
    setXyzText,
    setXyzCharge,
    setXyzMultiplicity,
    open,
    close,
    reset,
    search,
    selectCandidate,
    importSelected,
    previewXyz,
    importXyz,
  };
}
