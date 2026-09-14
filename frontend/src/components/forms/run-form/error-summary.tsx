import { useCallback } from "react";

interface ErrorSummaryProps {
  errors: Record<string, string>;
  /** Map of field key → element ID to scroll to */
  fieldIds?: Record<string, string>;
}

export function ErrorSummary({ errors, fieldIds }: ErrorSummaryProps) {
  const entries = Object.entries(errors);

  const scrollToField = useCallback(
    (field: string) => {
      const id = fieldIds?.[field] ?? field;
      const el = document.getElementById(id);
      if (el) {
        el.scrollIntoView({ block: "center", behavior: "smooth" });
        el.focus({ preventScroll: true });
      }
    },
    [fieldIds],
  );

  if (entries.length === 0) return null;

  return (
    <div
      role="alert"
      className="rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm"
    >
      <p className="font-medium text-destructive">
        Please fix the following errors before submitting:
      </p>
      <ul className="mt-2 list-inside list-disc space-y-1">
        {entries.map(([field, message]) => (
          <li key={field}>
            <button
              type="button"
              className="text-destructive underline-offset-2 hover:underline"
              onClick={() => scrollToField(field)}
            >
              {message}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
