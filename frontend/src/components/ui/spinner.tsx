import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Spinner({ className, ...props }: Readonly<HTMLAttributes<HTMLSpanElement>>) {
  return (
    <span
      aria-hidden="true"
      data-slot="spinner"
      className={cn(
        "inline-flex size-4 shrink-0 items-center justify-center align-middle",
        className,
      )}
      {...props}
    >
      <svg className="size-full" viewBox="0 0 24 24">
        <circle
          cx="12"
          cy="12"
          r="8"
          fill="none"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="3"
          strokeDasharray="32 18.3"
        >
          <animate
            attributeName="stroke-dashoffset"
            dur="0.85s"
            repeatCount="indefinite"
            values="0;-50.3"
          />
        </circle>
      </svg>
    </span>
  );
}
