import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Command } from "@/components/ui/command";
import {
  ActiveFilterChip,
  ClearFiltersButton,
  FilterOptionItem,
  FilterTriggerButton,
  SelectionIndicator,
} from "./filter-primitives";

describe("filter primitives", () => {
  it("renders an accessible trigger with its active count", () => {
    render(
      <FilterTriggerButton
        label="Status"
        ariaLabel="Filter by status"
        activeCount={2}
        onClick={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Filter by status" })).toHaveTextContent("Status2");
  });

  it("invokes an option handler from a command item", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();

    render(
      <Command>
        <FilterOptionItem selected onSelect={onSelect}>
          Running
        </FilterOptionItem>
      </Command>,
    );

    await user.click(screen.getByRole("option", { name: "Running" }));

    expect(onSelect).toHaveBeenCalledOnce();
  });

  it("supports removing an active chip and renders selection state", async () => {
    const user = userEvent.setup();
    const onRemove = vi.fn();

    const { rerender } = render(
      <>
        <ActiveFilterChip label="Running" ariaLabel="Remove Running filter" onRemove={onRemove} />
        <SelectionIndicator selected />
      </>,
    );

    await user.click(screen.getByRole("button", { name: "Remove Running filter" }));
    expect(onRemove).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Remove Running filter" })).toBeInTheDocument();

    rerender(
      <>
        <ActiveFilterChip label="Running" ariaLabel="Remove Running filter" onRemove={onRemove} />
        <SelectionIndicator selected={false} />
      </>,
    );
    expect(screen.getByRole("button", { name: "Remove Running filter" })).toBeInTheDocument();
  });

  it("provides a typed clear-all action with an explicit accessible name", async () => {
    const user = userEvent.setup();
    const onClear = vi.fn();

    render(
      <ClearFiltersButton label="Show all" ariaLabel="Show all chart points" onClear={onClear} />,
    );

    await user.click(screen.getByRole("button", { name: "Show all chart points" }));

    expect(onClear).toHaveBeenCalledOnce();
  });
});
