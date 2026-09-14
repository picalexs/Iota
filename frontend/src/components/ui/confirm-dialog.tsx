import { useState, type ReactNode } from "react";
import { Button } from "./button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "./dialog";
import { Spinner } from "./spinner";
import { cn } from "@/lib/utils";
import { shouldUseSpinner } from "@/utils/loading-policy";

export type ConfirmDialogProps = Readonly<{
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children?: ReactNode;
  status?: string;
  confirmText?: string;
  cancelText?: string;
  variant?: "default" | "destructive";
  onConfirm: () => void | Promise<void>;
  loading?: boolean;
  disabled?: boolean;
}>;

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  status,
  confirmText = "Confirm",
  cancelText = "Cancel",
  variant = "default",
  onConfirm,
  loading = false,
  disabled = false,
}: ConfirmDialogProps) {
  const [isLoading, setIsLoading] = useState(false);

  async function handleConfirm() {
    setIsLoading(true);
    try {
      await onConfirm();
      onOpenChange(false);
    } catch {
      // keep dialog open; caller is responsible for surfacing the error
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton
        className={cn("w-full max-w-sm rounded-lg p-6", "sm:max-w-sm")}
      >
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <div className="flex flex-col gap-1">
              <DialogTitle className="text-lg font-semibold leading-none">{title}</DialogTitle>
              <DialogDescription
                className={cn(!description && "sr-only", "text-sm text-muted-foreground")}
              >
                {description ?? "Please confirm this action."}
              </DialogDescription>
              {children}
              {status && (
                <p role="status" aria-live="polite" className="text-sm font-medium text-foreground">
                  {status}
                </p>
              )}
            </div>
          </div>

          <div className="grid gap-2 pt-2 sm:grid-cols-2">
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isLoading || loading || disabled}
              className="h-auto min-h-9 w-full whitespace-normal px-4 py-2 text-center"
            >
              {cancelText}
            </Button>
            <Button
              variant={variant}
              onClick={() => void handleConfirm()}
              disabled={isLoading || loading || disabled}
              className="h-auto min-h-9 w-full justify-center whitespace-normal px-4 py-2 text-center"
            >
              {isLoading || loading ? (
                <>
                  {shouldUseSpinner("mutation") ? <Spinner /> : null}
                  <span>{confirmText}</span>
                </>
              ) : (
                confirmText
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default ConfirmDialog;
