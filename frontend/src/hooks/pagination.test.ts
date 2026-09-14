import { describe, expect, it, vi } from "vitest";
import { fetchAllPages } from "./pagination";

describe("fetchAllPages", () => {
  it("walks pages using the number of returned items", async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce({ items: [{ id: "one" }, { id: "two" }], total: 3 })
      .mockResolvedValueOnce({ items: [{ id: "three" }], total: 3 });

    await expect(
      fetchAllPages<{ id: string }, string>(fetchPage, { pageSize: 2, getKey: (item) => item.id }),
    ).resolves.toEqual([{ id: "one" }, { id: "two" }, { id: "three" }]);
    expect(fetchPage).toHaveBeenNthCalledWith(1, { limit: 2, offset: 0 });
    expect(fetchPage).toHaveBeenNthCalledWith(2, { limit: 2, offset: 2 });
  });

  it("keeps the latest duplicate item and stops at a short final page", async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce({
        items: [
          { id: "one", value: 1 },
          { id: "two", value: 2 },
        ],
        total: 4,
      })
      .mockResolvedValueOnce({ items: [{ id: "two", value: 3 }], total: 3 });

    await expect(
      fetchAllPages<{ id: string; value: number }, string>(fetchPage, {
        pageSize: 2,
        getKey: (item) => item.id,
      }),
    ).resolves.toEqual([
      { id: "one", value: 1 },
      { id: "two", value: 3 },
    ]);
    expect(fetchPage).toHaveBeenCalledTimes(2);
  });

  it("stops on an empty page without making another request", async () => {
    const fetchPage = vi.fn().mockResolvedValue({ items: [], total: 10 });

    await expect(
      fetchAllPages<{ id: string }, string>(fetchPage, {
        pageSize: 50,
        getKey: (item) => item.id,
      }),
    ).resolves.toEqual([]);
    expect(fetchPage).toHaveBeenCalledOnce();
  });

  it("rejects an invalid page size before calling the API", async () => {
    const fetchPage = vi.fn();

    await expect(
      fetchAllPages<{ id: string }, string>(fetchPage, { pageSize: 0, getKey: (item) => item.id }),
    ).rejects.toThrow("pageSize must be a positive integer");
    expect(fetchPage).not.toHaveBeenCalled();
  });
});
