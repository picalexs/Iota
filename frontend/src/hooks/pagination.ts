/** Shared pagination rules for APIs that return items plus a total count. */

export interface PaginationRequest {
  limit: number;
  offset: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

export interface FetchAllPagesOptions<T, K> {
  pageSize: number;
  getKey: (item: T) => K;
}

/**
 * Fetch all pages while keeping the last value for duplicate item keys.
 *
 * The API total is authoritative when it says that more items exist. A short
 * page ends the walk only when it also reaches the reported total. This keeps
 * pagination safe when a server total changes while the collection is read.
 */
export async function fetchAllPages<T, K>(
  fetchPage: (params: PaginationRequest) => Promise<PaginatedResponse<T>>,
  { pageSize, getKey }: FetchAllPagesOptions<T, K>,
): Promise<T[]> {
  if (!Number.isInteger(pageSize) || pageSize <= 0) {
    throw new RangeError("pageSize must be a positive integer");
  }

  const itemsByKey = new Map<K, T>();
  let offset = 0;
  let total = Number.POSITIVE_INFINITY;

  while (offset < total) {
    const page = await fetchPage({ limit: pageSize, offset });
    const pageItems = page.items;
    const nextOffset = offset + pageItems.length;

    for (const item of pageItems) {
      itemsByKey.set(getKey(item), item);
    }

    if (pageItems.length === 0 || nextOffset <= offset) {
      break;
    }

    total = Number.isFinite(page.total) ? Math.max(0, page.total) : nextOffset;
    offset = nextOffset;

    if (pageItems.length < pageSize && offset >= total) {
      break;
    }
  }

  return Array.from(itemsByKey.values());
}
