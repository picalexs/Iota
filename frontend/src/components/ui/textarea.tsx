import * as React from "react";

import { controlSurfaceClassName, focusRingClassName } from "@/lib/interactive-styles";
import { cn } from "@/lib/utils";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "placeholder:text-muted-foreground selection:bg-primary selection:text-primary-foreground min-h-24 w-full rounded-md border px-3 py-2 text-sm outline-none disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
        controlSurfaceClassName,
        focusRingClassName,
        "aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
