import { describe, expect, it } from "vitest";
import { DEFAULT_QUERY_OPTIONS, keepPreviousQueryData } from "./query-options";

describe("shared query options", () => {
  it("keeps the application cache contract in one place", () => {
    expect(DEFAULT_QUERY_OPTIONS).toEqual({
      staleTime: 1000 * 60 * 5,
      gcTime: 1000 * 60 * 10,
      retry: false,
    });
  });

  it("returns previous data for transition placeholders", () => {
    const previousData = { items: ["H2"] };

    expect(keepPreviousQueryData(previousData)).toBe(previousData);
    expect(keepPreviousQueryData(undefined)).toBeUndefined();
  });
});
