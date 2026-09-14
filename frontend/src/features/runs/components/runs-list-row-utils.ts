import type { UUID } from "@/types/run";

export const RUNS_TABLE_GRID =
  "grid-cols-[9rem_minmax(0,1fr)_7rem_5rem_7rem_9rem_8rem_minmax(0,12rem)_3rem]";
export const RUNS_TABLE_GRID_WITH_SELECTION =
  "grid-cols-[2.25rem_9rem_minmax(0,1fr)_7rem_5rem_7rem_9rem_8rem_minmax(0,12rem)_3rem]";
export const RUNS_TABLE_COLUMN_COUNT = 9;
export const RUNS_TABLE_COLUMN_COUNT_WITH_SELECTION = 10;

export function getRunsTableGrid(selectionMode: boolean): string {
  return selectionMode ? RUNS_TABLE_GRID_WITH_SELECTION : RUNS_TABLE_GRID;
}

export function truncateId(id: UUID): string {
  return `${id.slice(0, 8)}…`;
}
