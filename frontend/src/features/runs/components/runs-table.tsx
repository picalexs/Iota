import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { PageErrorState, getErrorPresentation } from "@/components/ui/page-error-state";
import { PageJumpControl } from "@/components/ui/page-jump-control";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { GRID_TABLET_BREAKPOINT } from "@/lib/layout-constants";
import type { RunSummaryResponse, UUID } from "@/types/run";
import {
  getRunsTableGrid,
  RUNS_TABLE_COLUMN_COUNT,
  RUNS_TABLE_COLUMN_COUNT_WITH_SELECTION,
  truncateId,
} from "./runs-list-row-utils";
import { RunsListRow, RunsMobileCard, type RunRowAction } from "./runs-list-row";
import type { SortField, SortOrder } from "../state/filters";

function SkeletonRow({ selectionMode = false }: { readonly selectionMode?: boolean }) {
  const rowGridClassName = getRunsTableGrid(selectionMode);

  return (
    <tr
      className={`grid min-h-[57px] ${rowGridClassName} items-center gap-4 border-b px-4 py-3 last:border-0`}
    >
      {selectionMode ? (
        <td className="flex justify-center">
          <Skeleton className="size-4 rounded-sm" />
        </td>
      ) : null}
      <td>
        <Skeleton className="h-4 w-24" />
      </td>
      <td className="flex min-w-0 flex-col gap-1.5">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-3 w-20" />
      </td>
      <td>
        <Skeleton className="h-5 w-14" />
      </td>
      <td>
        <Skeleton className="mx-auto size-4 rounded-full" />
      </td>
      <td>
        <Skeleton className="h-4 w-14" />
      </td>
      <td>
        <Skeleton className="h-4 w-20" />
      </td>
      <td>
        <Skeleton className="h-4 w-20" />
      </td>
      <td>
        <Skeleton className="h-4 w-32" />
      </td>
      <td className="flex justify-end">
        <Skeleton className="size-8 rounded-md" />
      </td>
    </tr>
  );
}

interface SortHeaderProps {
  readonly label: string;
  readonly field: SortField;
  readonly sortField: SortField;
  readonly sortOrder: SortOrder;
  readonly onSort: (field: SortField) => void;
}

function SortHeader({ label, field, sortField, sortOrder, onSort }: SortHeaderProps) {
  const isActive = sortField === field;
  return (
    <button
      type="button"
      aria-label={`Sort by ${label}`}
      onClick={() => onSort(field)}
      className="flex items-center gap-1 text-xs font-medium text-muted-foreground uppercase tracking-wide hover:text-foreground transition-colors"
    >
      {label}
      <SortIcon active={isActive} order={sortOrder} />
    </button>
  );
}

function SortIcon({ active, order }: { readonly active: boolean; readonly order: SortOrder }) {
  if (active && order === "asc") {
    return <ArrowUp className="size-3" />;
  }
  if (active) {
    return <ArrowDown className="size-3" />;
  }
  return <ArrowUpDown className="size-3 opacity-40" />;
}

export function useCompactRunsLayout() {
  const [compact, setCompact] = useState(false);

  useEffect(() => {
    const mediaQuery = globalThis.matchMedia(`(max-width: ${GRID_TABLET_BREAKPOINT - 1}px)`);
    const syncLayout = () => {
      setCompact(globalThis.innerWidth < GRID_TABLET_BREAKPOINT);
    };

    syncLayout();
    mediaQuery.addEventListener("change", syncLayout);
    return () => mediaQuery.removeEventListener("change", syncLayout);
  }, []);

  return compact;
}

export interface RunsTableProps {
  readonly isLoading: boolean;
  readonly error: unknown;
  readonly mobile: boolean;
  readonly selectionMode: boolean;
  readonly selectedRunIds: ReadonlySet<UUID>;
  readonly runs: RunSummaryResponse[];
  readonly moleculeMap: Map<UUID, string>;
  readonly pendingRowActions: Partial<Record<UUID, RunRowAction>>;
  readonly pendingRowDeletes: Partial<Record<UUID, true>>;
  readonly onToggleRunSelection: (runId: UUID) => void;
  readonly onRunAction: (run: RunSummaryResponse, action: RunRowAction) => void | Promise<void>;
  readonly onDeleteRun: (run: RunSummaryResponse) => void | Promise<void>;
  readonly onRetry: () => void;
  readonly sortField: SortField;
  readonly sortOrder: SortOrder;
  readonly onSort: (field: SortField) => void;
}

export function RunsTable({
  isLoading,
  error,
  mobile,
  selectionMode,
  selectedRunIds,
  runs,
  moleculeMap,
  pendingRowActions,
  pendingRowDeletes,
  onToggleRunSelection,
  onRunAction,
  onDeleteRun,
  onRetry,
  sortField,
  sortOrder,
  onSort,
}: RunsTableProps) {
  if (mobile) {
    return (
      <RunsMobileList
        isLoading={isLoading}
        error={error}
        selectionMode={selectionMode}
        selectedRunIds={selectedRunIds}
        runs={runs}
        moleculeMap={moleculeMap}
        pendingRowActions={pendingRowActions}
        pendingRowDeletes={pendingRowDeletes}
        onToggleRunSelection={onToggleRunSelection}
        onRunAction={onRunAction}
        onDeleteRun={onDeleteRun}
        onRetry={onRetry}
      />
    );
  }

  return (
    <table aria-label="Quantum runs" className="w-full border-collapse">
      <RunsTableHeader
        selectionMode={selectionMode}
        sortField={sortField}
        sortOrder={sortOrder}
        onSort={onSort}
      />
      <RunsTableBody
        isLoading={isLoading}
        error={error}
        selectionMode={selectionMode}
        selectedRunIds={selectedRunIds}
        runs={runs}
        moleculeMap={moleculeMap}
        pendingRowActions={pendingRowActions}
        pendingRowDeletes={pendingRowDeletes}
        onToggleRunSelection={onToggleRunSelection}
        onRunAction={onRunAction}
        onDeleteRun={onDeleteRun}
        onRetry={onRetry}
      />
    </table>
  );
}

function RunsMobileSkeletonList({ selectionMode = false }: { readonly selectionMode?: boolean }) {
  const skeletonRowKeys = ["mobile-skeleton-1", "mobile-skeleton-2", "mobile-skeleton-3"];

  return (
    <div className="space-y-3 px-4 py-4" aria-label="Loading runs">
      {skeletonRowKeys.map((key) => (
        <div key={key} className="rounded-xl border border-border/70 bg-card px-4 py-3 shadow-sm">
          <div className="flex items-start gap-3">
            {selectionMode ? <Skeleton className="mt-0.5 size-4 rounded-sm" /> : null}
            <div className="min-w-0 flex-1 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1 space-y-2">
                  <Skeleton className="h-4 w-28" />
                  <Skeleton className="h-3 w-24" />
                  <Skeleton className="h-3 w-32" />
                </div>
                {selectionMode ? null : <Skeleton className="size-8 rounded-md" />}
              </div>
              <div className="flex flex-wrap gap-2">
                <Skeleton className="h-5 w-20 rounded-full" />
                <Skeleton className="h-5 w-32 rounded-full" />
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-full" />
                <Skeleton className="col-span-2 h-9 w-full" />
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function RunsMobileList({
  isLoading,
  error,
  selectionMode,
  selectedRunIds,
  runs,
  moleculeMap,
  pendingRowActions,
  pendingRowDeletes,
  onToggleRunSelection,
  onRunAction,
  onDeleteRun,
  onRetry,
}: Pick<
  RunsTableProps,
  | "isLoading"
  | "error"
  | "selectionMode"
  | "selectedRunIds"
  | "runs"
  | "moleculeMap"
  | "pendingRowActions"
  | "pendingRowDeletes"
  | "onToggleRunSelection"
  | "onRunAction"
  | "onDeleteRun"
  | "onRetry"
>) {
  if (isLoading) {
    return <RunsMobileSkeletonList selectionMode={selectionMode} />;
  }

  if (error) {
    return (
      <div className="px-4 py-6">
        <PageErrorState
          {...getErrorPresentation(error, "the runs history")}
          onRetry={onRetry}
          className="p-4"
        />
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="px-4 py-6">
        <RunsMobileEmptyState />
      </div>
    );
  }

  return (
    <ul aria-label="Quantum runs" className="space-y-3 px-4 py-4">
      {runs.map((run) => (
        <RunsMobileCard
          key={run.id}
          run={run}
          moleculeName={resolveMoleculeName(run, moleculeMap)}
          pendingAction={pendingRowActions[run.id] ?? null}
          pendingDelete={pendingRowDeletes[run.id] === true}
          selectionMode={selectionMode}
          selected={selectedRunIds.has(run.id)}
          onToggleSelected={() => onToggleRunSelection(run.id)}
          onAction={(action) => onRunAction(run, action)}
          onDelete={() => onDeleteRun(run)}
        />
      ))}
    </ul>
  );
}

function RunsTableHeader({
  selectionMode,
  sortField,
  sortOrder,
  onSort,
}: Pick<RunsTableProps, "selectionMode" | "sortField" | "sortOrder" | "onSort">) {
  const rowGridClassName = getRunsTableGrid(selectionMode);

  return (
    <thead>
      <tr className={`grid ${rowGridClassName} gap-4 items-center border-b bg-muted/40 px-4 py-2`}>
        {selectionMode ? (
          <th
            scope="col"
            className="text-center text-xs font-medium uppercase tracking-wide text-muted-foreground"
          >
            Select
          </th>
        ) : null}
        <th
          scope="col"
          className="text-left text-xs font-medium uppercase tracking-wide text-muted-foreground"
        >
          Run ID
        </th>
        <th scope="col" className="text-left">
          <SortHeader
            label="Molecule"
            field="molecule"
            sortField={sortField}
            sortOrder={sortOrder}
            onSort={onSort}
          />
        </th>
        <th scope="col" className="text-left">
          <SortHeader
            label="Status"
            field="status"
            sortField={sortField}
            sortOrder={sortOrder}
            onSort={onSort}
          />
        </th>
        <th
          scope="col"
          className="text-center text-xs font-medium uppercase tracking-wide text-muted-foreground"
        >
          Chemical Accurate
        </th>
        <th scope="col" className="text-left">
          <SortHeader
            label="Method"
            field="algorithm"
            sortField={sortField}
            sortOrder={sortOrder}
            onSort={onSort}
          />
        </th>
        <th scope="col" className="text-left">
          <SortHeader
            label="Backend"
            field="backend"
            sortField={sortField}
            sortOrder={sortOrder}
            onSort={onSort}
          />
        </th>
        <th scope="col" className="text-left">
          <SortHeader
            label="Runtime"
            field="runtime"
            sortField={sortField}
            sortOrder={sortOrder}
            onSort={onSort}
          />
        </th>
        <th scope="col" className="text-left">
          <SortHeader
            label="Created"
            field="created_at"
            sortField={sortField}
            sortOrder={sortOrder}
            onSort={onSort}
          />
        </th>
        <th
          scope="col"
          className="text-right text-xs font-medium uppercase tracking-wide text-muted-foreground"
        >
          <span className="sr-only">Actions</span>
        </th>
      </tr>
    </thead>
  );
}

function RunsTableBody({
  isLoading,
  error,
  selectionMode,
  selectedRunIds,
  runs,
  moleculeMap,
  pendingRowActions,
  pendingRowDeletes,
  onToggleRunSelection,
  onRunAction,
  onDeleteRun,
  onRetry,
}: Pick<
  RunsTableProps,
  | "isLoading"
  | "error"
  | "selectionMode"
  | "selectedRunIds"
  | "runs"
  | "moleculeMap"
  | "pendingRowActions"
  | "pendingRowDeletes"
  | "onToggleRunSelection"
  | "onRunAction"
  | "onDeleteRun"
  | "onRetry"
>) {
  const columnCount = selectionMode
    ? RUNS_TABLE_COLUMN_COUNT_WITH_SELECTION
    : RUNS_TABLE_COLUMN_COUNT;

  if (isLoading) {
    return (
      <tbody aria-label="Loading runs">
        <SkeletonRow selectionMode={selectionMode} />
        <SkeletonRow selectionMode={selectionMode} />
        <SkeletonRow selectionMode={selectionMode} />
      </tbody>
    );
  }

  if (error) {
    return (
      <tbody>
        <tr>
          <td colSpan={columnCount} className="px-4 py-6">
            <PageErrorState
              {...getErrorPresentation(error, "the runs history")}
              onRetry={onRetry}
              className="p-4"
            />
          </td>
        </tr>
      </tbody>
    );
  }

  if (runs.length === 0) {
    return (
      <tbody>
        <RunsEmptyState columnCount={columnCount} />
      </tbody>
    );
  }

  return (
    <tbody>
      {runs.map((run) => (
        <RunsListRow
          key={run.id}
          run={run}
          moleculeName={resolveMoleculeName(run, moleculeMap)}
          pendingAction={pendingRowActions[run.id] ?? null}
          pendingDelete={pendingRowDeletes[run.id] === true}
          selectionMode={selectionMode}
          selected={selectedRunIds.has(run.id)}
          onToggleSelected={() => onToggleRunSelection(run.id)}
          onAction={(action) => onRunAction(run, action)}
          onDelete={() => onDeleteRun(run)}
        />
      ))}
    </tbody>
  );
}

function resolveMoleculeName(run: RunSummaryResponse, moleculeMap: Map<UUID, string>) {
  return run.molecule_name ?? moleculeMap.get(run.molecule_id) ?? truncateId(run.molecule_id);
}

function RunsEmptyState({ columnCount }: { readonly columnCount: number }) {
  return (
    <tr>
      <td colSpan={columnCount}>
        <div className="flex flex-col items-center gap-4 px-4 py-12 text-center">
          <p className="text-muted-foreground text-sm">
            No runs yet. Create your first quantum run.
          </p>
          <Button asChild variant="outline" size="sm">
            <Link to="/runs/new">
              <Plus className="size-3.5 mr-2" />
              New Run
            </Link>
          </Button>
        </div>
      </td>
    </tr>
  );
}

function RunsMobileEmptyState() {
  return (
    <div className="flex flex-col items-center gap-4 rounded-xl border border-dashed border-border/70 px-4 py-10 text-center">
      <p className="text-muted-foreground text-sm">No runs yet. Create your first quantum run.</p>
      <Button asChild variant="outline" size="sm">
        <Link to="/runs/new">
          <Plus className="size-3.5 mr-2" />
          New Run
        </Link>
      </Button>
    </div>
  );
}

export interface MoleculeLookupNoticeProps {
  readonly show: boolean;
}

export function MoleculeLookupNotice({ show }: MoleculeLookupNoticeProps) {
  if (show) {
    return (
      <div className="border-t px-4 py-2 text-xs text-muted-foreground">
        Molecule labels are temporarily unavailable; run IDs are still shown.
      </div>
    );
  }

  return null;
}

export interface RunsPaginationProps {
  readonly show: boolean;
  readonly page: number;
  readonly totalPages: number;
  readonly onPageChange: (page: number) => void;
}

export function RunsPagination({ show, page, totalPages, onPageChange }: RunsPaginationProps) {
  if (show) {
    return (
      <div className="flex flex-wrap items-center justify-end gap-3 border-t px-4 py-3">
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 px-2 text-xs"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            aria-label="Previous runs page"
          >
            <ChevronLeft className="size-4" />
            Previous
          </Button>
          <PageJumpControl
            ariaLabel="Go to runs page"
            currentPage={page}
            totalPages={totalPages}
            onPageChange={onPageChange}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 px-2 text-xs"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
            aria-label="Next runs page"
          >
            Next
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>
    );
  }

  return null;
}
