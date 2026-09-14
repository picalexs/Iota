import type { KeyboardEvent, MouseEvent, ReactNode } from "react";
import { elevatedSurfaceClassName, selectableSurfaceClassName } from "@/lib/interactive-styles";
import { cn } from "@/lib/utils";

type SelectableCardProps = Readonly<{
  selected?: boolean;
  children: ReactNode;
  as?: "button" | "div";
  disabled?: boolean;
  id?: string;
  className?: string;
  type?: "button" | "submit" | "reset";
  onClick?: (event: MouseEvent<HTMLElement>) => void;
  onKeyDown?: (event: KeyboardEvent<HTMLElement>) => void;
}>;

export function SelectableCard({
  selected = false,
  as = "button",
  className,
  children,
  type = "button",
  disabled,
  onClick,
  onKeyDown,
  ...props
}: SelectableCardProps) {
  const cardClassName = cn(
    "group/selectable-card relative flex w-full rounded-xl p-4 text-left",
    elevatedSurfaceClassName,
    selectableSurfaceClassName,
    disabled && "cursor-not-allowed opacity-60",
    className,
  );

  if (as === "div") {
    return (
      <label data-selected={selected ? "true" : "false"} className={cardClassName}>
        <input
          {...props}
          type="checkbox"
          checked={selected}
          disabled={disabled}
          readOnly
          className="sr-only"
          onClick={disabled ? undefined : (event) => onClick?.(event)}
          onKeyDown={onKeyDown}
        />
        {children}
      </label>
    );
  }

  return (
    <button
      type={type}
      disabled={disabled}
      data-selected={selected ? "true" : "false"}
      className={cardClassName}
      onClick={onClick}
      onKeyDown={onKeyDown}
      {...props}
    >
      {children}
    </button>
  );
}
