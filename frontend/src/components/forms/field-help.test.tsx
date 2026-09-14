import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FieldHelp } from "./field-help";

vi.mock("../ui/tooltip", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

describe("FieldHelp", () => {
  it("links to the glossary anchor in a new tab", () => {
    render(<FieldHelp short="Quick explanation" anchor="basis_set" label="Basis set" />);

    expect(screen.getByRole("link", { name: /learn more about basis set/i })).toHaveAttribute(
      "href",
      "/help/parameters#basis_set",
    );
    expect(screen.getByRole("link", { name: /learn more about basis set/i })).toHaveAttribute(
      "target",
      "_blank",
    );
  });

  it("can link directly to a long-form reference page", () => {
    render(
      <FieldHelp
        short="Open the detailed ansatz notes"
        href="/info/components/ansatzes"
        label="Ansatz"
      />,
    );

    expect(screen.getByRole("link", { name: /learn more about ansatz/i })).toHaveAttribute(
      "href",
      "/info/components/ansatzes",
    );
  });

  it("renders the short tooltip copy", async () => {
    render(<FieldHelp short="Quick explanation" anchor="basis_set" label="Basis set" />);

    expect(await screen.findByText("Quick explanation")).toBeInTheDocument();
  });
});
