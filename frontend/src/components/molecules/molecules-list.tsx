import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { ListChecks, Trash2 } from "lucide-react";

import { useBulkDeleteShortcut } from "@/components/bulk-actions/use-bulk-delete-shortcut";
import { BulkSelectionBar } from "@/components/bulk-actions/bulk-selection-bar";
import { useBulkSelection } from "@/components/bulk-actions/use-bulk-selection";
import type { MoleculeListParams } from "@/types/run";
import { useFetchMoleculeSummaries, useInvalidateMoleculesList } from "@/hooks";
import { Card, CardContent } from "@/components/ui/card";
import { PageErrorState, getErrorPresentation } from "@/components/ui/page-error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import {
  EmptyMoleculesState,
  MoleculesPagination,
  PubChemSearchPrompt,
} from "./molecules-list/molecules-list-state";
import {
  MoleculeCard,
  MOLECULE_TABLE_GRID,
  MOLECULE_TABLE_GRID_WITH_SELECTION,
  MoleculeSortHeader,
  type MoleculeSortField,
  type SortOrder,
} from "./molecules-list/molecule-card";
import { MoleculesToolbar } from "./molecules-list/molecules-toolbar";
import { MoleculeDeleteDialog } from "./molecules-list/molecule-delete-dialog";
import { useMoleculeBulkDelete } from "./molecules-list/use-molecule-bulk-delete";
import { usePubChemImport } from "./molecules-list/use-pubchem-import";

const MOLECULE_LIST_LIMIT = 50;
const EMPTY_MOLECULES: NonNullable<ReturnType<typeof useFetchMoleculeSummaries>["data"]>["items"] =
  [];

function SkeletonRow() {
  return (
    <div
      className={`grid min-h-[49px] ${MOLECULE_TABLE_GRID} items-center gap-4 border-b px-4 py-3 last:border-0`}
    >
      <div>
        <Skeleton className="h-4 w-28" />
      </div>
      <div>
        <Skeleton className="ml-auto h-4 w-16" />
      </div>
      <div>
        <Skeleton className="ml-auto h-4 w-8" />
      </div>
    </div>
  );
}

function sortMolecules(
  rawMolecules: typeof EMPTY_MOLECULES,
  sortField: MoleculeSortField,
  sortOrder: SortOrder,
) {
  const items = [...rawMolecules];

  items.sort((a, b) => {
    const cmp = sortField === "atoms" ? a.atom_count - b.atom_count : a.name.localeCompare(b.name);
    return sortOrder === "asc" ? cmp : -cmp;
  });

  return items;
}

function getEditButtonLabel(isEditing: boolean): string {
  return isEditing ? "Done Editing" : "Edit";
}

function getDeleteActionLabel(selectedCount: number): string {
  return selectedCount > 0 ? `Delete (${selectedCount})` : "Delete";
}

function getMoleculeTableGridClass(selectionMode: boolean): string {
  return selectionMode ? MOLECULE_TABLE_GRID_WITH_SELECTION : MOLECULE_TABLE_GRID;
}

export function MoleculesList() {
  const navigate = useNavigate();
  const {
    q: urlQuery = "",
    page: urlPage = 1,
    sort: urlSort,
    order: urlOrder,
  } = useSearch({ from: "/molecules" });

  const sortField: MoleculeSortField = urlSort ?? "name";
  const sortOrder: SortOrder = urlOrder ?? "asc";
  const currentPage = urlPage;
  const invalidateMoleculesList = useInvalidateMoleculesList();

  const [searchQuery, setSearchQuery] = useState(urlQuery);
  const [debouncedQuery, setDebouncedQuery] = useState(urlQuery);
  const [deleteConfirmationOpen, setDeleteConfirmationOpen] = useState(false);
  const [deleteAssociatedRuns, setDeleteAssociatedRuns] = useState(false);
  const pubChemImport = usePubChemImport({
    onImported: (moleculeId) => {
      void navigate({ to: "/molecules/$moleculeId", params: { moleculeId } });
    },
  });

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  useEffect(() => {
    if (debouncedQuery === urlQuery) {
      return;
    }

    void navigate({
      to: "/molecules",
      search: (prev) => ({
        q: debouncedQuery || undefined,
        page: 1,
        sort: prev.sort as MoleculeSortField | undefined,
        order: prev.order,
      }),
      replace: true,
    });
  }, [debouncedQuery, navigate, urlQuery]);

  const moleculesParams = useMemo<MoleculeListParams>(
    () => ({
      q: debouncedQuery || undefined,
      limit: MOLECULE_LIST_LIMIT,
      offset: (currentPage - 1) * MOLECULE_LIST_LIMIT,
    }),
    [debouncedQuery, currentPage],
  );

  const moleculesQuery = useFetchMoleculeSummaries(moleculesParams);
  const isLoading = moleculesQuery.isLoading;
  const error = moleculesQuery.error;
  const rawMolecules = moleculesQuery.data?.items ?? EMPTY_MOLECULES;
  const total = moleculesQuery.data?.total ?? 0;

  const molecules = useMemo(
    () => sortMolecules(rawMolecules, sortField, sortOrder),
    [rawMolecules, sortField, sortOrder],
  );
  const bulkSelection = useBulkSelection(molecules.map((molecule) => molecule.id));
  const selectedMolecules = molecules.filter((molecule) =>
    bulkSelection.selectedIdSet.has(molecule.id),
  );
  const selectedAssociatedRunCount = selectedMolecules.reduce(
    (total, molecule) => total + molecule.run_count,
    0,
  );
  const {
    actionError,
    clearActionError,
    clearDeleteProgress,
    deleteInProgress,
    deleteProgress,
    deleteSelected,
  } = useMoleculeBulkDelete({
    selectedMolecules,
    deleteAssociatedRuns,
    invalidateMoleculesList,
    replaceSelection: bulkSelection.replaceSelection,
    onDeleteSuccess: () => setDeleteConfirmationOpen(false),
  });

  async function openDeleteConfirmation() {
    clearActionError();
    await moleculesQuery.refetch();
    setDeleteConfirmationOpen(true);
  }

  useBulkDeleteShortcut({
    enabled:
      bulkSelection.isEditing &&
      bulkSelection.selectedCount > 0 &&
      !deleteConfirmationOpen &&
      !deleteInProgress,
    onDelete: () => {
      void openDeleteConfirmation();
    },
  });

  const totalPages = Math.ceil(total / MOLECULE_LIST_LIMIT);
  const pageStart = total > 0 ? (currentPage - 1) * MOLECULE_LIST_LIMIT + 1 : 0;
  const pageEnd = Math.min(currentPage * MOLECULE_LIST_LIMIT, total);
  const canGoPrevious = currentPage > 1;
  const canGoNext = currentPage < totalPages;

  function updateSort(field: MoleculeSortField) {
    let order: SortOrder = "asc";
    if (sortField === field) {
      order = sortOrder === "asc" ? "desc" : "asc";
    }

    void navigate({
      to: "/molecules",
      search: (prev) => ({
        q: prev.q,
        sort: field,
        order,
        page: 1,
      }),
    });
  }

  function goToPage(page: number) {
    void navigate({
      to: "/molecules",
      search: (prev) => ({
        q: prev.q,
        sort: prev.sort as MoleculeSortField | undefined,
        order: prev.order,
        page,
      }),
    });
  }

  return (
    <>
      <Card aria-busy={isLoading || deleteInProgress}>
        <MoleculesToolbar
          searchQuery={searchQuery}
          onSearchQueryChange={setSearchQuery}
          importState={pubChemImport}
          actionSlot={
            molecules.length > 0 ? (
              <Button
                type="button"
                variant={bulkSelection.isEditing ? "secondary" : "outline"}
                size="sm"
                onClick={() => bulkSelection.toggleEditing()}
                aria-pressed={bulkSelection.isEditing}
              >
                <ListChecks className="size-3.5" />
                {getEditButtonLabel(bulkSelection.isEditing)}
              </Button>
            ) : null
          }
        />

        <CardContent className="p-0">
          <div aria-label="Molecules library" className="border-t">
            {bulkSelection.isEditing ? (
              <BulkSelectionBar
                itemLabel="molecules"
                totalVisibleCount={molecules.length}
                selectedCount={bulkSelection.selectedCount}
                allVisibleSelected={bulkSelection.allVisibleSelected}
                someVisibleSelected={bulkSelection.someVisibleSelected}
                onToggleSelectAllVisible={(selected) => {
                  clearActionError();
                  bulkSelection.setAllVisibleSelected(selected);
                }}
                onClearSelection={() => {
                  clearActionError();
                  bulkSelection.clearSelection();
                }}
                actionError={actionError}
                actions={[
                  {
                    key: "delete",
                    label: getDeleteActionLabel(bulkSelection.selectedCount),
                    icon: Trash2,
                    variant: "destructive",
                    disabled: bulkSelection.selectedCount === 0 || deleteInProgress,
                    onClick: () => {
                      void openDeleteConfirmation();
                    },
                  },
                ]}
              />
            ) : null}
            <div
              className={`grid ${getMoleculeTableGridClass(bulkSelection.isEditing)} gap-4 items-center border-b bg-muted/40 px-4 py-2`}
            >
              {bulkSelection.isEditing ? (
                <span className="text-center text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Select
                </span>
              ) : null}
              <MoleculeSortHeader
                label="Name"
                field="name"
                sortField={sortField}
                sortOrder={sortOrder}
                onSort={updateSort}
              />
              <span className="text-right text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Formula
              </span>
              <MoleculeSortHeader
                label="Atoms"
                field="atoms"
                sortField={sortField}
                sortOrder={sortOrder}
                align="right"
                onSort={updateSort}
              />
            </div>

            {isLoading && (
              <div aria-label="Loading molecules">
                <SkeletonRow />
                <SkeletonRow />
                <SkeletonRow />
              </div>
            )}

            {error && (
              <div className="px-4 py-6">
                <PageErrorState
                  {...getErrorPresentation(error, "the molecules library")}
                  onRetry={() => void moleculesQuery.refetch()}
                  className="p-4"
                />
              </div>
            )}

            {!isLoading && !error && molecules.length === 0 && (
              <EmptyMoleculesState
                debouncedQuery={debouncedQuery}
                onImport={() => pubChemImport.open()}
                onSearchPubChem={(query) => pubChemImport.open(query)}
              />
            )}

            {!isLoading && !error && molecules.length > 0 && debouncedQuery.trim().length > 0 && (
              <PubChemSearchPrompt
                debouncedQuery={debouncedQuery}
                onSearchPubChem={(query) => pubChemImport.open(query)}
              />
            )}

            {!isLoading && !error && molecules.length > 0 && (
              <>
                <div>
                  {molecules.map((molecule) => (
                    <MoleculeCard
                      key={molecule.id}
                      molecule={molecule}
                      selectionMode={bulkSelection.isEditing}
                      selected={bulkSelection.selectedIdSet.has(molecule.id)}
                      onToggleSelected={() => {
                        clearActionError();
                        bulkSelection.toggleSelected(molecule.id);
                      }}
                    />
                  ))}
                </div>

                {totalPages > 1 && (
                  <MoleculesPagination
                    currentPage={currentPage}
                    totalPages={totalPages}
                    pageStart={pageStart}
                    pageEnd={pageEnd}
                    total={total}
                    canGoPrevious={canGoPrevious}
                    canGoNext={canGoNext}
                    isLoading={isLoading}
                    onPageChange={goToPage}
                  />
                )}
              </>
            )}
          </div>
        </CardContent>
      </Card>

      <MoleculeDeleteDialog
        open={deleteConfirmationOpen}
        onOpenChange={setDeleteConfirmationOpen}
        onClose={() => {
          clearDeleteProgress();
          setDeleteAssociatedRuns(false);
        }}
        selectedCount={bulkSelection.selectedCount}
        selectedAssociatedRunCount={selectedAssociatedRunCount}
        deleteAssociatedRuns={deleteAssociatedRuns}
        onDeleteAssociatedRunsChange={setDeleteAssociatedRuns}
        deleteProgress={deleteProgress}
        onConfirm={deleteSelected}
        loading={deleteInProgress}
      />
    </>
  );
}

export default MoleculesList;
