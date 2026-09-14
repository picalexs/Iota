import { fireEvent, render, screen } from "@testing-library/react";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { MoleculeCard } from "./molecule-card";

const mocks = vi.hoisted(() => ({
  preloadMoleculeDetailPageModule: vi.fn(),
  preloadMoleculeViewer3D: vi.fn(),
}));

vi.mock("@tanstack/react-router", () => ({
  Link: ({
    children,
    to,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement> & { children: ReactNode; to: string }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/routes/lazy-pages", () => ({
  preloadMoleculeDetailPageModule: mocks.preloadMoleculeDetailPageModule,
}));

vi.mock("@/components/molecules/molecule-viewer-3d-preload", () => ({
  preloadMoleculeViewer3D: mocks.preloadMoleculeViewer3D,
}));

describe("MoleculeCard", () => {
  it("preloads the molecule detail page and 3D viewer before navigation interactions", () => {
    render(
      <MoleculeCard
        molecule={{
          id: "d0e01306-5546-449f-945d-141d0390b568",
          name: "Water",
          formula: "H2O",
          atom_count: 3,
          charge: 0,
          iupac_name: null,
          run_count: 0,
        }}
      />,
    );

    const row = screen.getByRole("link", { name: "Water" });

    fireEvent.focus(row);
    fireEvent.mouseEnter(row);
    fireEvent.mouseDown(row);
    fireEvent.touchStart(row);

    expect(mocks.preloadMoleculeDetailPageModule).toHaveBeenCalledTimes(4);
    expect(mocks.preloadMoleculeViewer3D).toHaveBeenCalledTimes(4);
  });
});
