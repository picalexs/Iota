import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface FormSectionProps {
  index: number;
  title: string;
  description?: string;
  status?: "ok" | "warning" | "error";
  children: ReactNode;
  className?: string;
}

const CHIP_COLORS: Record<NonNullable<FormSectionProps["status"]> | "idle", string> = {
  error: "bg-destructive text-destructive-foreground border-destructive",
  warning: "bg-yellow-500 text-white border-yellow-500",
  ok: "bg-green-500 text-white border-green-500",
  idle: "bg-background text-foreground border-border",
};

export function FormSection({
  index,
  title,
  description,
  status,
  children,
  className,
}: FormSectionProps) {
  const statusKey = status ?? "idle";
  const chipColor = CHIP_COLORS[statusKey];

  return (
    <div className={cn("flex flex-col gap-5", className)}>
      <div className="flex items-start gap-4">
        <div
          data-status={statusKey}
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-sm font-semibold",
            chipColor,
          )}
        >
          {index}
        </div>
        <div className="flex flex-col gap-1">
          <h2 className="text-sm font-semibold leading-none">{title}</h2>
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
        </div>
      </div>
      <hr className="border-border/70" />
      <div className="flex flex-col gap-4 pl-12 pr-3 sm:pr-12">{children}</div>
    </div>
  );
}
