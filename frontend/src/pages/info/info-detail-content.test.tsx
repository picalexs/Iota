import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { InfoEntry } from "@/content/info/types";
import { InfoDetailContent } from "./info-detail-content";

describe("InfoDetailContent", () => {
  it("renders display equations, embedded videos, and references", () => {
    const entry: InfoEntry = {
      id: "test-entry",
      title: "Test Entry",
      summary: "A compact reference entry for component coverage.",
      blocks: [
        {
          kind: "text",
          heading: "Controls",
          body: "The `reps` setting controls layered ansatz depth.",
        },
        {
          kind: "equation",
          label: "Objective",
          latex: String.raw`E(\theta) = \langle \psi | H | \psi \rangle`,
          displayText: "E(θ) = ⟨ψ|H|ψ⟩",
        },
        {
          kind: "video",
          src: "https://video.ibm.com/embed/recorded/134325519?showtitle=false",
          title: "IBM Quantum overview of VQE",
          href: "https://quantum.cloud.ibm.com/learning/en/courses/quantum-diagonalization-algorithms/vqe",
          linkLabel: "Open IBM VQE lesson",
        },
      ],
      references: [
        {
          label: "IBM Quantum Learning - VQE lesson",
          href: "https://quantum.cloud.ibm.com/learning/en/courses/quantum-diagonalization-algorithms/vqe",
        },
      ],
    };

    const { container } = render(<InfoDetailContent entry={entry} />);

    expect(screen.getByText("Objective")).toBeInTheDocument();
    expect(screen.getByText("reps", { selector: "code" })).toBeInTheDocument();
    expect(container.querySelector(".info-equation .katex-display")).not.toBeNull();

    const iframe = screen.getByTitle("IBM Quantum overview of VQE");
    expect(iframe).toHaveAttribute(
      "src",
      "https://video.ibm.com/embed/recorded/134325519?showtitle=false",
    );
    expect(iframe).toHaveAttribute("sandbox", "allow-same-origin allow-scripts allow-presentation");
    expect(iframe).toHaveAttribute("allow", "autoplay; encrypted-media; picture-in-picture");

    expect(screen.getByRole("link", { name: "Open IBM VQE lesson" })).toHaveAttribute(
      "href",
      "https://quantum.cloud.ibm.com/learning/en/courses/quantum-diagonalization-algorithms/vqe",
    );
    expect(screen.getByRole("link", { name: /IBM Quantum Learning - VQE lesson/ })).toHaveAttribute(
      "href",
      "https://quantum.cloud.ibm.com/learning/en/courses/quantum-diagonalization-algorithms/vqe",
    );
  });

  it("does not turn LaTeX link commands into anchors", () => {
    const entry: InfoEntry = {
      id: "untrusted-latex",
      title: "Untrusted LaTeX",
      summary: "Guards the equation rendering path.",
      blocks: [
        {
          kind: "equation",
          label: "Injection attempt",
          latex: "\\href{javascript:alert(1)}{click} + \\url{javascript:alert(2)}",
        },
      ],
    };

    const { container } = render(<InfoDetailContent entry={entry} />);

    const equation = container.querySelector(".info-equation");
    expect(equation).not.toBeNull();
    expect(equation?.querySelectorAll("a")).toHaveLength(0);
    expect(equation?.querySelectorAll("[href], [src], [xlink\\:href]")).toHaveLength(0);
    expect(equation?.textContent).toContain(String.raw`\href`);
  });
});
