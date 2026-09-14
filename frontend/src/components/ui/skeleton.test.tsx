import { render } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { Skeleton } from "./skeleton";

describe("Skeleton Component", () => {
  beforeEach(() => {
    // Reset matchMedia mock before each test
    Object.defineProperty(globalThis, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders with skeleton slot identifier", () => {
    const { container } = render(<Skeleton />);
    const skeleton = container.querySelector('[data-slot="skeleton"]');
    expect(skeleton).toBeInTheDocument();
  });

  it("applies animate-pulse by default", () => {
    const { container } = render(<Skeleton />);
    const skeleton = container.querySelector('[data-slot="skeleton"]');
    expect(skeleton).toHaveClass("animate-pulse");
    expect(skeleton).toHaveClass("skeleton-shimmer");
  });

  it("applies custom className alongside defaults", () => {
    const { container } = render(<Skeleton className="h-4 w-full" />);
    const skeleton = container.querySelector('[data-slot="skeleton"]');
    expect(skeleton).toHaveClass("h-4");
    expect(skeleton).toHaveClass("w-full");
    expect(skeleton).toHaveClass("animate-pulse");
    expect(skeleton).toHaveClass("skeleton-shimmer");
  });

  it("respects prefers-reduced-motion media query", () => {
    // Mock matchMedia to simulate prefers-reduced-motion: reduce
    const mockMatchMedia = vi.fn().mockImplementation((query) => {
      if (query === "(prefers-reduced-motion: reduce)") {
        return {
          matches: true,
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        };
      }
      return {
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      };
    });

    Object.defineProperty(globalThis, "matchMedia", {
      writable: true,
      value: mockMatchMedia,
    });

    const { container } = render(<Skeleton />);
    const skeleton = container.querySelector('[data-slot="skeleton"]');

    // Should NOT have animate-pulse when prefers-reduced-motion is detected
    expect(skeleton).not.toHaveClass("animate-pulse");
    expect(skeleton).not.toHaveClass("skeleton-shimmer");
  });

  it("uses accessible animation approach (not aria-hidden)", () => {
    const { container } = render(<Skeleton />);
    const skeleton = container.querySelector('[data-slot="skeleton"]');
    // Skeletons should be visible to screen readers (not aria-hidden)
    expect(skeleton).not.toHaveAttribute("aria-hidden", "true");
  });

  it("applies accent background color", () => {
    const { container } = render(<Skeleton />);
    const skeleton = container.querySelector('[data-slot="skeleton"]');
    expect(skeleton).toHaveClass("bg-accent");
  });
});
