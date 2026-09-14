export const defaultSurfaceClassName = "border-border/80 bg-surface-default shadow-none";

export const containerSurfaceClassName =
  "border-border/85 bg-card shadow-[var(--shadow-surface-panel)]";

export const panelSurfaceClassName =
  "border-sidebar-border/85 bg-sidebar shadow-[var(--shadow-surface-panel)]";

export const elevatedSurfaceClassName =
  "border-border/80 bg-surface-raised shadow-[var(--shadow-elevation-raised)]";

export const overlaySurfaceSmClassName =
  "border-border/80 bg-surface-overlay shadow-[var(--shadow-elevation-overlay-sm)]";

export const overlaySurfaceMdClassName =
  "border-border/80 bg-surface-overlay-strong shadow-[var(--shadow-elevation-overlay-md)]";

export const focusRingClassName =
  "focus-visible:outline-none focus-visible:border-accent-2/60 focus-visible:ring-focus-strong focus-visible:ring-[3px]";

export const controlSurfaceClassName =
  "border-input bg-surface-raised shadow-none transition-[background-color,border-color,color,box-shadow] duration-200 hover:border-interactive-hover-border hover:bg-interactive-hover active:border-interactive-pressed-border active:bg-surface-pressed";

export const selectableSurfaceClassName = `${focusRingClassName} transition-[background-color,border-color,box-shadow,color] duration-200 hover:border-interactive-hover-border hover:bg-interactive-hover hover:shadow-[var(--shadow-interactive-hover)] data-[selected=true]:border-interactive-selected-border data-[selected=true]:bg-interactive-selected data-[selected=true]:text-interactive-selected-foreground data-[selected=true]:shadow-[var(--shadow-interactive-selected)] active:border-interactive-pressed-border active:bg-interactive-pressed`;

export const prominentSurfaceHoverClassName =
  "transition-[background-color,border-color,box-shadow,color] duration-200 hover:border-primary/45 hover:bg-surface-raised-hover hover:shadow-[var(--shadow-elevation-overlay-sm)]";

export const selectableCardIconClassName =
  "rounded-lg bg-primary/10 p-2 text-primary transition-colors group-data-[selected=true]/selectable-card:bg-primary group-data-[selected=true]/selectable-card:text-primary-foreground";

export const segmentedSelectionClassName = `${focusRingClassName} transition-[background-color,border-color,box-shadow,color] duration-200 hover:border-interactive-hover-border hover:bg-interactive-hover hover:text-foreground hover:shadow-[var(--shadow-interactive-hover)] data-[selected=true]:z-10 data-[selected=true]:border-interactive-selected-border data-[selected=true]:bg-interactive-selected data-[selected=true]:text-interactive-selected-foreground data-[selected=true]:shadow-[var(--shadow-interactive-selected)] active:border-interactive-pressed-border active:bg-interactive-pressed`;
