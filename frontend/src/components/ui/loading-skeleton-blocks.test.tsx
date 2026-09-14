import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TableSkeletonRow, DetailCardSkeleton, SkeletonCardGrid } from "./loading-skeleton-blocks";

describe("loading-skeleton-blocks", () => {
  it("renders table skeleton row with requested cell count", () => {
    render(
      <table>
        <tbody>
          <TableSkeletonRow
            gridClassName="grid-cols-[1fr_1fr_auto]"
            cellWidths={["w-24", "w-16", "w-8"]}
            rightAlignedIndices={[2]}
          />
        </tbody>
      </table>,
    );

    const row = screen.getByRole("row");
    expect(row).toBeInTheDocument();
    expect(screen.getAllByRole("cell")).toHaveLength(3);
    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons).toHaveLength(3);
  });

  it("renders detail card skeleton with heading and content lines", () => {
    render(<DetailCardSkeleton lineWidths={["w-full", "w-1/2"]} />);

    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    // 1 title line + 2 content lines
    expect(skeletons).toHaveLength(3);
  });

  it("renders card grid skeleton with configured number of cards", () => {
    render(<SkeletonCardGrid cardCount={4} />);

    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons).toHaveLength(4);
  });
});
