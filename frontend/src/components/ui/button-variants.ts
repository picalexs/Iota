import { cva } from "class-variance-authority";

export const buttonVariants = cva(
  "inline-flex cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-md border text-sm font-medium transition-[background-color,border-color,color,box-shadow] duration-150 ease-out disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:border-accent-2/60 focus-visible:ring-focus-strong focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive",
  {
    variants: {
      variant: {
        default:
          "border-primary/35 bg-primary text-primary-foreground shadow-[var(--shadow-button-primary)] hover:bg-primary/92 hover:shadow-[var(--shadow-elevation-raised)] active:bg-primary/95 active:shadow-[var(--shadow-button-primary-pressed)]",
        destructive:
          "border-destructive/35 bg-destructive text-white hover:bg-destructive/92 active:bg-destructive/95 active:shadow-[inset_0_1px_2px_rgb(0_0_0_/_0.16)] dark:bg-destructive/70",
        outline:
          "border-input bg-surface-raised text-foreground shadow-none hover:border-interactive-hover-border hover:bg-interactive-hover active:border-interactive-pressed-border active:bg-surface-pressed",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground shadow-none hover:bg-interactive-hover active:bg-surface-pressed",
        ghost:
          "border-transparent bg-transparent shadow-none hover:bg-accent hover:text-accent-foreground active:bg-accent/90 dark:hover:bg-accent/60",
        link: "border-transparent bg-transparent text-primary shadow-none underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2 has-[>svg]:px-3",
        xs: "h-6 gap-1 rounded-md px-2 text-xs has-[>svg]:px-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-8 rounded-md gap-1.5 px-3 has-[>svg]:px-2.5",
        lg: "h-10 rounded-md px-6 has-[>svg]:px-4",
        icon: "size-9",
        "icon-xs": "size-6 rounded-md [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-8",
        "icon-lg": "size-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);
