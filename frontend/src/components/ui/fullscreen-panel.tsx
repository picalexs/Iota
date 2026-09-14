import type { ReactNode } from "react";
import { Minimize2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

type FullscreenPanelProps = Readonly<{
  open: boolean;
  onClose: () => void;
  title: string;
  headerActions?: ReactNode;
  bodyClassName?: string;
  children: ReactNode;
}>;

export function FullscreenPanel({
  open,
  onClose,
  title,
  headerActions,
  bodyClassName,
  children,
}: FullscreenPanelProps) {
  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) onClose();
      }}
    >
      <DialogContent
        className="flex flex-col p-4 !left-12 !right-0 !top-14 !translate-x-5 !translate-y-0"
        style={{
          width: "calc(100vw - 6rem)",
          height: "calc(100vh - 3.5rem - 1rem)",
          maxWidth: "none",
          maxHeight: "none",
        }}
        aria-describedby={undefined}
        showCloseButton={false}
      >
        <DialogHeader>
          <div className="flex flex-wrap items-center gap-4">
            <DialogTitle>{title}</DialogTitle>
            {headerActions ? (
              <div className="flex items-center gap-2 shrink-0">{headerActions}</div>
            ) : null}
            <button
              type="button"
              onClick={onClose}
              className="ml-auto rounded-md p-1.5 transition-colors hover:bg-accent shrink-0"
              aria-label="Close fullscreen"
            >
              <Minimize2 className="size-4" />
            </button>
          </div>
        </DialogHeader>
        <div className={cn("min-h-0 flex-1 overflow-auto", bodyClassName)}>{children}</div>
      </DialogContent>
    </Dialog>
  );
}
