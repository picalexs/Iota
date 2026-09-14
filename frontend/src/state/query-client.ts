import { QueryClient } from "@tanstack/react-query";
import { DEFAULT_QUERY_OPTIONS } from "@/hooks/query-options";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        ...DEFAULT_QUERY_OPTIONS,
        refetchOnWindowFocus: true,
        refetchOnMount: false,
      },
      mutations: {
        retry: DEFAULT_QUERY_OPTIONS.retry,
      },
    },
  });
}
