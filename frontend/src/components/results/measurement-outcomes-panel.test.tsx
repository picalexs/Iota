import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it } from "vitest";

import { ThemeProvider } from "@/context/theme-context";
import { MeasurementOutcomesPanel } from "./measurement-outcomes-panel";

function renderWithTheme(
  ui: ReactElement,
  theme: "light" | "dark" = "light",
  storageKey = `measurement-panel-theme-${theme}`,
) {
  return render(
    <ThemeProvider defaultTheme={theme} storageKey={storageKey}>
      {ui}
    </ThemeProvider>,
  );
}

describe("MeasurementOutcomesPanel", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("shows circuit tabs for the representative artifact and switches artifacts through the selector", async () => {
    const user = userEvent.setup();

    renderWithTheme(
      <MeasurementOutcomesPanel
        stateKey="measurement-switching"
        outcomes={[
          { bitstring: "1100", probability: 0.7, count: 70 },
          { bitstring: "0011", probability: 0.3, count: 30 },
        ]}
        artifactSelectorLabel="Recovery iter"
        artifacts={[
          {
            id: "iter-1",
            iteration: 1,
            label: "Recovery iter 1",
            representative: true,
            logical: {
              qasm: "OPENQASM 3.0; // iter 1",
              diagram_svg: "<svg><text>iter-1</text></svg>",
              qubits: 4,
              classical_bits: 4,
              style: "iqp",
            },
            transpiled: {
              qasm: "OPENQASM 3.0; // iter 1 transpiled",
              diagram_svg: "<svg><text>iter-1-transpiled</text></svg>",
              qubits: 4,
              classical_bits: 4,
              style: "iqp",
            },
          },
          {
            id: "iter-2",
            iteration: 2,
            label: "Recovery iter 2",
            logical: {
              qasm: "OPENQASM 3.0; // iter 2",
              diagram_svg: "<svg><text>iter-2</text></svg>",
              qubits: 4,
              classical_bits: 4,
              style: "iqp",
            },
          },
        ]}
      />,
    );

    expect(screen.getByRole("button", { name: "Outcomes" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bits" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Circuit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Qiskit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Transpiled" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Circuit diagram" })).toHaveAttribute(
      "src",
      expect.stringContaining("iter-1"),
    );

    await user.click(screen.getByRole("button", { name: "Qiskit" }));
    expect(screen.getByText(/Rebuild the stored OpenQASM 3 program/)).toBeInTheDocument();
    expect(
      screen.getByText(/from qiskit import qasm3[\s\S]*OPENQASM 3\.0; \/\/ iter 1/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/circuit = qasm3\.loads\(program\)[\s\S]*circuit\.draw\(output="mpl"\)/),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByRole("option", { name: "Recovery iter 2" }));

    expect(screen.queryByRole("button", { name: "Transpiled" })).not.toBeInTheDocument();
    expect(screen.getByText(/OPENQASM 3\.0; \/\/ iter 2/)).toBeInTheDocument();
  });

  it("falls back to stored QASM when a transpiled preview has no SVG", async () => {
    const user = userEvent.setup();

    renderWithTheme(
      <MeasurementOutcomesPanel
        stateKey="measurement-transpiled-fallback"
        outcomes={[{ bitstring: "11", probability: 1, count: 8 }]}
        artifacts={[
          {
            id: "iter-1",
            iteration: 1,
            representative: true,
            logical: {
              qasm: "OPENQASM 3.0; // logical",
              diagram_svg: "<svg><text>logical</text></svg>",
              qubits: 2,
              classical_bits: 2,
              style: "iqp",
            },
            transpiled: {
              qasm: "OPENQASM 3.0; // transpiled-only",
              qubits: 2,
              classical_bits: 2,
              style: "iqp",
            },
          },
        ]}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Transpiled" }));

    expect(
      screen.getByText(/SVG rendering was not persisted for this circuit/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/OPENQASM 3\.0; \/\/ transpiled-only/)).toBeInTheDocument();
    expect(screen.queryByText("Circuit diagram not available")).not.toBeInTheDocument();
  });

  it("rejects risky persisted SVG previews and falls back to stored QASM", async () => {
    const user = userEvent.setup();

    renderWithTheme(
      <MeasurementOutcomesPanel
        stateKey="measurement-sanitized-fallback"
        outcomes={[{ bitstring: "11", probability: 1, count: 8 }]}
        artifacts={[
          {
            id: "iter-1",
            iteration: 1,
            representative: true,
            logical: {
              qasm: "OPENQASM 3.0; // sanitized-fallback",
              diagram_svg: '<svg><script>alert("x")</script><text>unsafe</text></svg>',
              qubits: 2,
              classical_bits: 2,
              style: "iqp",
            },
          },
        ]}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Circuit" }));

    expect(screen.queryByRole("img", { name: "Circuit diagram" })).not.toBeInTheDocument();
    expect(
      screen.getByText(/SVG rendering was not persisted for this circuit/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/OPENQASM 3\.0; \/\/ sanitized-fallback/)).toBeInTheDocument();
  });

  it("rejects encoded SVG URL handlers and event attributes", async () => {
    const user = userEvent.setup();

    renderWithTheme(
      <MeasurementOutcomesPanel
        stateKey="measurement-encoded-svg"
        outcomes={[{ bitstring: "11", probability: 1, count: 8 }]}
        artifacts={[
          {
            id: "encoded-url",
            iteration: 1,
            representative: true,
            logical: {
              qasm: "OPENQASM 3.0; // encoded-url-fallback",
              diagram_svg:
                '<svg xmlns:xlink="http://www.w3.org/1999/xlink"><a xlink:href="java&#x73;cript:alert(1)"><text>unsafe</text></a></svg>',
              qubits: 2,
              classical_bits: 2,
              style: "iqp",
            },
          },
          {
            id: "event-attribute",
            iteration: 2,
            logical: {
              qasm: "OPENQASM 3.0; // event-fallback",
              diagram_svg: '<svg><text onclick="alert(1)">unsafe</text></svg>',
              qubits: 2,
              classical_bits: 2,
              style: "iqp",
            },
          },
        ]}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Circuit" }));

    expect(screen.queryByRole("img", { name: "Circuit diagram" })).not.toBeInTheDocument();
    expect(screen.getByText(/OPENQASM 3\.0; \/\/ encoded-url-fallback/)).toBeInTheDocument();

    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByRole("option", { name: "event-attribute" }));

    expect(screen.queryByRole("img", { name: "Circuit diagram" })).not.toBeInTheDocument();
    expect(screen.getByText(/OPENQASM 3\.0; \/\/ event-fallback/)).toBeInTheDocument();
  });

  it("renders matplotlib-style SVG previews after stripping harmless metadata", async () => {
    const user = userEvent.setup();

    renderWithTheme(
      <MeasurementOutcomesPanel
        stateKey="measurement-matplotlib-svg"
        outcomes={[{ bitstring: "11", probability: 1, count: 8 }]}
        artifacts={[
          {
            id: "matplotlib-preview",
            representative: true,
            logical: {
              qasm: "OPENQASM 3.0; // matplotlib-safe",
              diagram_svg: `
                <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="32" height="32" viewBox="0 0 32 32">
                  <metadata>
                    <rdf:RDF xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:cc="http://creativecommons.org/ns#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
                      <cc:Work>
                        <dc:type rdf:resource="http://purl.org/dc/dcmitype/StillImage" />
                      </cc:Work>
                    </rdf:RDF>
                  </metadata>
                  <defs>
                    <path id="glyph" d="M 2 2 L 30 2 L 30 30 L 2 30 z" />
                    <style type="text/css">*{stroke-linejoin: round; stroke-linecap: butt}</style>
                  </defs>
                  <use xlink:href="#glyph" style="fill: #4f6bd8" />
                </svg>
              `,
              qubits: 2,
              classical_bits: 2,
              style: "iqp",
            },
          },
        ]}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Circuit" }));

    expect(screen.getByRole("img", { name: "Circuit diagram" })).toBeInTheDocument();
    expect(
      screen.queryByText(/SVG rendering was not persisted for this circuit/i),
    ).not.toBeInTheDocument();
  });

  it("adapts the circuit preview surface to the active theme", async () => {
    const lightView = renderWithTheme(
      <MeasurementOutcomesPanel
        stateKey="measurement-theme-light"
        outcomes={[]}
        artifacts={[
          {
            id: "iter-1",
            representative: true,
            logical: {
              qasm: "OPENQASM 3.0; // themed",
              diagram_svg: "<svg><text>themed</text></svg>",
              qubits: 2,
              classical_bits: 2,
              style: "iqp",
            },
          },
        ]}
      />,
      "light",
      "measurement-panel-theme-light",
    );

    expect(screen.getByTestId("circuit-preview-surface")).toHaveClass("bg-slate-100/85");

    lightView.unmount();

    renderWithTheme(
      <MeasurementOutcomesPanel
        stateKey="measurement-theme-dark"
        outcomes={[]}
        artifacts={[
          {
            id: "iter-1",
            representative: true,
            logical: {
              qasm: "OPENQASM 3.0; // themed",
              diagram_svg: "<svg><text>themed</text></svg>",
              qubits: 2,
              classical_bits: 2,
              style: "iqp",
            },
          },
        ]}
      />,
      "dark",
      "measurement-panel-theme-dark",
    );

    expect(screen.getByTestId("circuit-preview-surface")).toHaveClass("bg-[#0f141b]");
  });

  it("restores the selected artifact tab and iteration from local storage", async () => {
    const user = userEvent.setup();
    const artifacts = [
      {
        id: "iter-1",
        iteration: 1,
        label: "Iter 1",
        representative: true,
        logical: {
          qasm: "OPENQASM 3.0; // iter 1",
          diagram_svg: "<svg><text>iter-1</text></svg>",
          qubits: 4,
          classical_bits: 4,
          style: "iqp",
        },
      },
      {
        id: "iter-2",
        iteration: 2,
        label: "Iter 2",
        logical: {
          qasm: "OPENQASM 3.0; // iter 2",
          diagram_svg: "<svg><text>iter-2</text></svg>",
          qubits: 4,
          classical_bits: 4,
          style: "iqp",
        },
      },
    ];

    const firstView = renderWithTheme(
      <MeasurementOutcomesPanel
        stateKey="measurement-persisted-selection"
        outcomes={[{ bitstring: "1100", probability: 1, count: 1 }]}
        artifactSelectorLabel="Recovery iter"
        artifacts={artifacts}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Circuit" }));
    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByRole("option", { name: "Iter 2" }));
    expect(screen.getByRole("img", { name: "Circuit diagram" })).toHaveAttribute(
      "src",
      expect.stringContaining("iter-2"),
    );

    firstView.unmount();

    renderWithTheme(
      <MeasurementOutcomesPanel
        stateKey="measurement-persisted-selection"
        outcomes={[{ bitstring: "1100", probability: 1, count: 1 }]}
        artifactSelectorLabel="Recovery iter"
        artifacts={artifacts}
      />,
    );

    expect(screen.getByRole("img", { name: "Circuit diagram" })).toHaveAttribute(
      "src",
      expect.stringContaining("iter-2"),
    );
  });
});
