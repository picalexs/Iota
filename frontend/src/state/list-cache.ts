export interface CachedEntry<T> {
  data?: T;
  updatedAt?: number;
  inFlight?: Promise<T>;
}

const listCache = new Map<string, CachedEntry<unknown>>();

function toCacheKeyParam(value: unknown): string {
  if (value === null) return "null";
  if (value === undefined) return "undefined";
  if (typeof value === "object") {
    return JSON.stringify(value) ?? "unserializable-object";
  }
  if (typeof value === "string") return value;
  if (typeof value === "number") return `${value}`;
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "bigint") return `${value}`;
  if (typeof value === "symbol") return value.toString();
  if (typeof value === "function") return value.name ? `function:${value.name}` : "function";
  return "unknown";
}

export function buildCacheKey(scope: string, params: Record<string, unknown> = {}): string {
  const parts = Object.entries(params)
    .filter(([, value]) => value !== undefined)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => `${key}=${toCacheKeyParam(value)}`);

  return parts.length > 0 ? `${scope}?${parts.join("&")}` : scope;
}

export function getCachedEntry<T>(key: string): CachedEntry<T> | undefined {
  const entry = listCache.get(key);
  if (!entry) return undefined;
  return entry as CachedEntry<T>;
}

export function getCachedData<T>(key: string): T | undefined {
  return getCachedEntry<T>(key)?.data;
}

export async function fetchWithListCache<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  const existing = getCachedEntry<T>(key);
  if (existing?.inFlight) {
    return existing.inFlight;
  }

  const entry: CachedEntry<T> = existing ?? {};
  const inFlightPromise = fetcher();
  entry.inFlight = inFlightPromise;
  listCache.set(key, entry);

  try {
    const data = await inFlightPromise;
    entry.data = data;
    entry.updatedAt = Date.now();
    return data;
  } finally {
    const current = getCachedEntry<T>(key);
    if (current?.inFlight === inFlightPromise) {
      delete current.inFlight;
      listCache.set(key, current);
    }
  }
}

export function clearListCache(): void {
  listCache.clear();
}
