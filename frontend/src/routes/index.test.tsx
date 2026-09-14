import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@tanstack/react-router", async () => {
  const actual =
    await vi.importActual<typeof import("@tanstack/react-router")>("@tanstack/react-router");

  return {
    ...actual,
    Link: ({
      to,
      className,
      children,
    }: {
      to: string;
      className?: string;
      children?: ReactNode;
    }) => (
      <a href={to} className={className}>
        {children}
      </a>
    ),
  };
});

import { NotFoundPage, parseRunsSearch } from "./index";

describe("parseRunsSearch", () => {
  it("accepts current keys and filters invalid values", () => {
    expect(
      parseRunsSearch({
        statuses: ["RUNNING", "FAILED"],
        molecule_ids: ["mol-1"],
        methods: ["vqe", "qse"],
        backend_target: "ibm_runtime",
        chemical_accurate: "true",
        sort: "runtime",
        order: "desc",
        page: 3,
      }),
    ).toEqual({
      statuses: ["RUNNING", "FAILED"],
      molecule_ids: ["mol-1"],
      methods: ["vqe", "qse"],
      backend_target: "ibm_runtime",
      chemical_accurate: true,
      sort: "runtime",
      order: "desc",
      page: 3,
    });

    expect(
      parseRunsSearch({
        statuses: "COMPLETED",
        molecule_id: "mol-legacy",
        method: "sqd",
        backend_target: "not-a-target",
        chemical_accurate: "false",
        sort: "not-a-sort",
        order: "sideways",
        page: "2",
      }),
    ).toEqual({
      statuses: ["COMPLETED"],
      molecule_ids: ["mol-legacy"],
      methods: ["sqd"],
      backend_target: undefined,
      chemical_accurate: false,
      sort: undefined,
      order: undefined,
      page: undefined,
    });
  });

  it("drops empty and non-list values", () => {
    expect(
      parseRunsSearch({
        statuses: [],
        molecule_ids: 42,
        methods: "",
        chemical_accurate: null,
      }),
    ).toEqual({
      statuses: undefined,
      molecule_ids: undefined,
      methods: undefined,
      backend_target: undefined,
      chemical_accurate: undefined,
      sort: undefined,
      order: undefined,
      page: undefined,
    });
  });
});

describe("NotFoundPage", () => {
  it("renders a back link to the dashboard", () => {
    render(<NotFoundPage />);

    expect(screen.getByRole("heading", { name: /page not found/i })).toBeInTheDocument();
    expect(screen.getByText(/this page is coming soon/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to dashboard/i })).toHaveAttribute("href", "/");
  });
});
