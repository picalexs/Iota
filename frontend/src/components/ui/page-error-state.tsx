import type { ReactNode } from "react";
import { RefreshCw, RotateCcw, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { isApiUnavailableError } from "@/lib/error-handler";
import { cn } from "@/lib/utils";

type ErrorPresentation = {
  title: string;
  description: string;
  detail: string | null;
};

export function getErrorPresentation(error: unknown, context = "this page"): ErrorPresentation {
  const detail = error instanceof Error ? error.message : null;

  if (isApiUnavailableError(error)) {
    return {
      title: "The API is unavailable right now",
      description: `The frontend is still running, but ${context} cannot load live data until the backend responds again.`,
      detail,
    };
  }

  return {
    title: `We couldn't load ${context}`,
    description: "Try again in a moment. If the problem keeps coming back, reload the page.",
    detail,
  };
}

type PageErrorStateProps = {
  title: string;
  description: string;
  detail?: string | null;
  onRetry?: (() => void) | null;
  retryLabel?: string;
  reloadLabel?: string;
  onReload?: (() => void) | null;
  actions?: ReactNode;
  className?: string;
};

export function PageErrorState({
  title,
  description,
  detail = null,
  onRetry = null,
  retryLabel = "Try again",
  reloadLabel = "Reload page",
  onReload = () => globalThis.location.reload(),
  actions,
  className,
}: PageErrorStateProps) {
  const hasActions = Boolean(actions || onRetry || onReload);

  return (
    <section
      role="alert"
      className={cn(
        "rounded-2xl border border-border/70 bg-card p-5 shadow-[var(--shadow-elevation-raised)] dark:bg-muted/20",
        className,
      )}
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-start gap-4">
          <div className="flex size-11 shrink-0 items-center justify-center rounded-2xl border border-amber-500/25 bg-amber-500/10 text-amber-700 dark:border-amber-400/25 dark:bg-amber-400/10 dark:text-amber-200">
            <TriangleAlert className="size-5" />
          </div>
          <div className="min-w-0 flex-1 space-y-2">
            <div className="inline-flex w-fit rounded-full border border-amber-500/25 bg-amber-500/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-800 dark:border-amber-400/25 dark:bg-amber-400/10 dark:text-amber-200">
              Connection issue
            </div>
            <div className="space-y-1">
              <h2 className="text-lg font-semibold text-foreground">{title}</h2>
              <p className="max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p>
            </div>
          </div>
        </div>

        {detail ? (
          <p className="rounded-xl border border-border/60 bg-surface-raised/70 px-3 py-2 text-xs text-muted-foreground dark:bg-background/40">
            {detail}
          </p>
        ) : null}

        {hasActions ? (
          <div className="flex flex-wrap gap-2">
            {onRetry ? (
              <Button type="button" variant="outline" onClick={onRetry}>
                <RefreshCw className="size-4" />
                {retryLabel}
              </Button>
            ) : null}
            {onReload ? (
              <Button type="button" onClick={onReload}>
                <RotateCcw className="size-4" />
                {reloadLabel}
              </Button>
            ) : null}
            {actions}
          </div>
        ) : null}
      </div>
    </section>
  );
}
