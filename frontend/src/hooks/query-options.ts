export const DEFAULT_QUERY_OPTIONS = {
  staleTime: 1000 * 60 * 5,
  gcTime: 1000 * 60 * 10,
  retry: false,
} as const;

export function keepPreviousQueryData<TData>(previousData: TData | undefined): TData | undefined {
  return previousData;
}
