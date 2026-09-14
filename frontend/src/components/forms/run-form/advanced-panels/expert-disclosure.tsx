import type { ReactNode } from "react";
import { useState } from "react";
import { ChevronDown } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ExpertDisclosureProps {
  title?: string;
  description?: string;
  children: ReactNode;
}

export function ExpertDisclosure({
  title = "Expert controls",
  description = "Optional parameters for fine-grained tuning.",
  children,
}: ExpertDisclosureProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-xl border border-border/70 bg-card p-4 dark:bg-muted/20">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">{title}</p>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          className="gap-1.5"
        >
          {open ? "Hide" : "Show"}
          <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} />
        </Button>
      </div>
      {open ? <div className="mt-4 grid gap-4">{children}</div> : null}
    </div>
  );
}
