import type { ComponentProps } from "react";
import { useMemo } from "react";
import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: Readonly<ComponentProps<"div">>) {
  /**
   * Respect prefers-reduced-motion for accessibility.
   * Users with motion sensitivity should see a static skeleton, not a pulsing one.
   */
  const shouldAnimate = useMemo(() => {
    if (typeof globalThis.matchMedia !== "function") return true;
    const prefersReducedMotion = globalThis.matchMedia("(prefers-reduced-motion: reduce)").matches;
    return !prefersReducedMotion;
  }, []);

  return (
    <div
      data-slot="skeleton"
      className={cn(
        "bg-accent rounded-md",
        shouldAnimate && "animate-pulse skeleton-shimmer",
        className,
      )}
      {...props}
    />
  );
}

export { Skeleton };
