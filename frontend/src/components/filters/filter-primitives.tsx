import { Check, ChevronDown, X } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CommandItem } from "@/components/ui/command";
import { cn } from "@/lib/utils";

export type FilterTriggerButtonProps = Readonly<
  Omit<ComponentProps<typeof Button>, "children"> & {
    label: string;
    ariaLabel: string;
    activeCount?: number;
    badgeClassName?: string;
  }
>;

export function FilterTriggerButton({
  label,
  ariaLabel,
  activeCount,
  badgeClassName,
  ...buttonProps
}: FilterTriggerButtonProps) {
  return (
    <Button
      {...buttonProps}
      variant="outline"
      size="sm"
      className={cn("h-8 gap-1 text-xs", buttonProps.className)}
      aria-label={ariaLabel}
    >
      {label}
      {activeCount !== undefined && activeCount > 0 ? (
        <Badge
          variant="secondary"
          className={cn("rounded-sm px-1 font-mono text-xs", badgeClassName)}
        >
          {activeCount}
        </Badge>
      ) : null}
      <ChevronDown className="size-3 opacity-50" />
    </Button>
  );
}

export interface SelectionIndicatorProps {
  readonly selected: boolean;
  readonly className?: string;
  readonly selectedClassName?: string;
  readonly unselectedClassName?: string;
}

export function SelectionIndicator({
  selected,
  className,
  selectedClassName,
  unselectedClassName,
}: SelectionIndicatorProps) {
  return (
    <div
      className={cn(
        "mr-2 flex size-4 items-center justify-center rounded-sm border transition-colors",
        selected
          ? "border-interactive-selected-border bg-interactive-selected text-interactive-selected-foreground shadow-[var(--shadow-interactive-selected)]"
          : "border-border/70 bg-background text-muted-foreground opacity-70",
        selected ? selectedClassName : unselectedClassName,
        className,
      )}
    >
      {selected ? <Check className="size-3" /> : null}
    </div>
  );
}

export interface FilterOptionItemProps {
  readonly selected: boolean;
  readonly onSelect: () => void;
  readonly value?: string;
  readonly className?: string;
  readonly indicatorClassName?: string;
  readonly selectedIndicatorClassName?: string;
  readonly unselectedIndicatorClassName?: string;
  readonly children: ReactNode;
}

export function FilterOptionItem({
  selected,
  onSelect,
  value,
  className,
  indicatorClassName,
  selectedIndicatorClassName,
  unselectedIndicatorClassName,
  children,
}: FilterOptionItemProps) {
  return (
    <CommandItem value={value} onSelect={onSelect} className={cn("text-xs", className)}>
      <SelectionIndicator
        selected={selected}
        className={indicatorClassName}
        selectedClassName={selectedIndicatorClassName}
        unselectedClassName={unselectedIndicatorClassName}
      />
      {children}
    </CommandItem>
  );
}

export type ClearFiltersButtonProps = Readonly<
  Omit<ComponentProps<typeof Button>, "children" | "onClick"> & {
    label: string;
    ariaLabel: string;
    onClear: () => void;
    icon?: ReactNode;
  }
>;

export function ClearFiltersButton({
  label,
  ariaLabel,
  onClear,
  icon,
  variant = "ghost",
  size = "sm",
  type = "button",
  ...buttonProps
}: ClearFiltersButtonProps) {
  return (
    <Button
      {...buttonProps}
      type={type}
      variant={variant}
      size={size}
      className={cn("h-8 text-xs", buttonProps.className)}
      aria-label={ariaLabel}
      onClick={onClear}
    >
      {label}
      {icon}
    </Button>
  );
}

export interface ActiveFilterChipProps {
  readonly label: string;
  readonly ariaLabel: string;
  readonly onRemove: () => void;
}

export function ActiveFilterChip({ label, ariaLabel, onRemove }: ActiveFilterChipProps) {
  return (
    <Badge variant="secondary" className="h-7 gap-1 rounded-sm text-xs font-normal">
      {label}
      <button
        type="button"
        onClick={onRemove}
        className="ml-0.5 rounded-sm opacity-60 hover:opacity-100"
        aria-label={ariaLabel}
      >
        <X className="size-3" />
      </button>
    </Badge>
  );
}
