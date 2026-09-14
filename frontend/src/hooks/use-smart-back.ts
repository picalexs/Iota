import { useRouter } from "@tanstack/react-router";

/**
 * Returns a callback that navigates back via browser history when possible,
 * falling back to a specified route when there is no history to pop.
 *
 * List state is preserved because TanStack Router encodes filter/pagination
 * state in URL search params — history.back() restores those params.
 */
export function useSmartBack(fallback: { to: string }, options?: { forceFallback?: boolean }) {
  const router = useRouter();
  return () => {
    if (options?.forceFallback) {
      void router.navigate(fallback);
      return;
    }

    if (
      typeof router.history.canGoBack === "function"
        ? router.history.canGoBack()
        : globalThis.history.length > 1
    ) {
      router.history.back();
    } else {
      void router.navigate(fallback);
    }
  };
}
