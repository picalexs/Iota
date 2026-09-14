import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useBulkDeleteShortcut } from "./use-bulk-delete-shortcut";

describe("useBulkDeleteShortcut", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("calls the delete handler when Delete is pressed", () => {
    const onDelete = vi.fn();

    renderHook(() => useBulkDeleteShortcut({ enabled: true, onDelete }));

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Delete", bubbles: true }));

    expect(onDelete).toHaveBeenCalledTimes(1);
  });

  it("ignores Delete while focus is in an input", () => {
    const onDelete = vi.fn();
    const input = document.createElement("input");
    document.body.append(input);
    input.focus();

    renderHook(() => useBulkDeleteShortcut({ enabled: true, onDelete }));

    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Delete", bubbles: true }));

    expect(onDelete).not.toHaveBeenCalled();
  });

  it("does nothing when disabled", () => {
    const onDelete = vi.fn();

    renderHook(() => useBulkDeleteShortcut({ enabled: false, onDelete }));

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Delete", bubbles: true }));

    expect(onDelete).not.toHaveBeenCalled();
  });
});
