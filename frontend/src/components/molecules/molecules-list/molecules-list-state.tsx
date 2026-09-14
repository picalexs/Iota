import { ChevronLeft, ChevronRight, Download, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { PageJumpControl } from "@/components/ui/page-jump-control";

interface EmptyMoleculesStateProps {
  readonly debouncedQuery: string;
  readonly onImport: () => void;
  readonly onSearchPubChem: (query: string) => void;
}

export function EmptyMoleculesState({
  debouncedQuery,
  onImport,
  onSearchPubChem,
}: EmptyMoleculesStateProps) {
  if (debouncedQuery.trim().length === 0) {
    return (
      <div className="px-4 py-12 text-center flex flex-col items-center gap-4">
        <p className="text-muted-foreground text-sm">
          No molecules found. Start by importing from PubChem.
        </p>
        <Button onClick={onImport} variant="outline" size="sm">
          <Plus className="size-3.5 mr-2" />
          Add Molecule
        </Button>
      </div>
    );
  }

  return (
    <div className="px-4 py-12 text-center flex flex-col items-center gap-4">
      <p className="text-muted-foreground text-sm">
        No local molecules match your search for "{debouncedQuery}".
      </p>
      <Button onClick={() => onSearchPubChem(debouncedQuery)} variant="outline" size="sm">
        <Download className="size-3.5 mr-2" />
        Search PubChem for "{debouncedQuery}"
      </Button>
    </div>
  );
}

interface PubChemSearchPromptProps {
  readonly debouncedQuery: string;
  readonly onSearchPubChem: (query: string) => void;
}

export function PubChemSearchPrompt({ debouncedQuery, onSearchPubChem }: PubChemSearchPromptProps) {
  return (
    <div className="px-4 py-3 border-t bg-muted/20">
      <p className="text-xs text-muted-foreground mb-2">Can't find what you're looking for?</p>
      <Button onClick={() => onSearchPubChem(debouncedQuery)} variant="outline" size="sm">
        <Download className="size-3.5 mr-2" />
        Search PubChem for "{debouncedQuery}"
      </Button>
    </div>
  );
}

interface MoleculesPaginationProps {
  readonly currentPage: number;
  readonly totalPages: number;
  readonly pageStart: number;
  readonly pageEnd: number;
  readonly total: number;
  readonly canGoPrevious: boolean;
  readonly canGoNext: boolean;
  readonly isLoading: boolean;
  readonly onPageChange: (page: number) => void;
}

export function MoleculesPagination({
  currentPage,
  totalPages,
  pageStart,
  pageEnd,
  total,
  canGoPrevious,
  canGoNext,
  isLoading,
  onPageChange,
}: MoleculesPaginationProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3">
      <p className="text-xs text-muted-foreground">
        Showing {pageStart}-{pageEnd} of {total}
      </p>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 px-2 text-xs"
          onClick={() => onPageChange(Math.max(1, currentPage - 1))}
          disabled={!canGoPrevious || isLoading}
          aria-label="Previous page"
        >
          <ChevronLeft className="size-4" />
          Previous
        </Button>
        <PageJumpControl
          ariaLabel="Go to molecule page"
          currentPage={currentPage}
          disabled={isLoading}
          totalPages={totalPages}
          onPageChange={onPageChange}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 px-2 text-xs"
          onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
          disabled={!canGoNext || isLoading}
          aria-label="Next page"
        >
          Next
          <ChevronRight className="size-4" />
        </Button>
      </div>
    </div>
  );
}
