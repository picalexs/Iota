export type LoadingContextType = "route-loading" | "search" | "load-more" | "mutation";

export const LOADING_POLICY = {
  SKELETON_CONTEXTS: ["route-loading"] as const satisfies readonly LoadingContextType[],

  SPINNER_CONTEXTS: [
    "search",
    "load-more",
    "mutation",
  ] as const satisfies readonly LoadingContextType[],

  description:
    "Route loading uses skeleton-first UI to minimize layout shift and perceived latency. " +
    "Search, load-more, and mutation actions use spinners for immediate feedback on explicit user actions.",
} as const;

export function shouldUseSkeleton(context: LoadingContextType): boolean {
  return (LOADING_POLICY.SKELETON_CONTEXTS as readonly LoadingContextType[]).includes(context);
}

export function shouldUseSpinner(context: LoadingContextType): boolean {
  return (LOADING_POLICY.SPINNER_CONTEXTS as readonly LoadingContextType[]).includes(context);
}
