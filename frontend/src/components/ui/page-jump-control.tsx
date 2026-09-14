import { useRef, useState, type SyntheticEvent } from "react";

import { Input } from "@/components/ui/input";

type PageJumpControlProps = Readonly<{
  currentPage: number;
  totalPages: number;
  disabled?: boolean;
  onPageChange: (page: number) => void;
  ariaLabel?: string;
}>;

function clampPage(page: number, totalPages: number) {
  return Math.min(Math.max(page, 1), Math.max(totalPages, 1));
}

export function PageJumpControl({
  currentPage,
  totalPages,
  disabled = false,
  onPageChange,
  ariaLabel = "Go to page",
}: PageJumpControlProps) {
  const [draftPage, setDraftPage] = useState(String(currentPage));
  const currentPageRef = useRef(currentPage);
  if (currentPageRef.current !== currentPage) {
    currentPageRef.current = currentPage;
    setDraftPage(String(currentPage));
  }

  function commitPage() {
    const parsedPage = Number.parseInt(draftPage, 10);
    if (!Number.isFinite(parsedPage)) {
      setDraftPage(String(currentPage));
      return;
    }

    const nextPage = clampPage(parsedPage, totalPages);
    setDraftPage(String(nextPage));
    if (nextPage !== currentPage) {
      onPageChange(nextPage);
    }
  }

  function handleSubmit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    commitPage();
  }

  return (
    <form
      className="flex items-center gap-1.5 text-xs text-muted-foreground"
      onSubmit={handleSubmit}
    >
      <Input
        aria-label={ariaLabel}
        className="h-8 w-14 px-2 text-center text-xs tabular-nums"
        disabled={disabled}
        inputMode="numeric"
        pattern="[0-9]*"
        value={draftPage}
        onBlur={commitPage}
        onChange={(event) => setDraftPage(event.target.value.replace(/\D/g, ""))}
        onFocus={(event) => event.target.select()}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            setDraftPage(String(currentPage));
            event.currentTarget.blur();
          }
        }}
      />
      <span className="tabular-nums">/ {totalPages}</span>
    </form>
  );
}
