import "./benchmark-page.test-mocks";

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  benchmarkEntry,
  getRunResult,
  mockBenchmarkDetail,
  renderBenchmarkPage,
  resetBenchmarkPageTestState,
  runResult,
  savedBenchmarkWithEntries,
} from "./benchmark-page.test-support";

beforeEach(resetBenchmarkPageTestState);

describe("BenchmarkPage results", () => {
  it("summarizes not-accurate completed rows separately from correlation recovery", async () => {
    (getRunResult as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...runResult,
      energy: -1,
      converged: true,
    });
    mockBenchmarkDetail(savedBenchmarkWithEntries([benchmarkEntry()]));

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await waitFor(() =>
      expect(screen.getByLabelText("Not chemically accurate")).toBeInTheDocument(),
    );
    expect(screen.getByLabelText("Not chemically accurate")).toBeInTheDocument();
    expect(screen.getByText("137.00 mHa")).toBeInTheDocument();
  });

  it("updates benchmark verdicts when the benchmark threshold is edited", async () => {
    (getRunResult as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...runResult,
      energy: -1.127,
      converged: true,
    });
    mockBenchmarkDetail(
      savedBenchmarkWithEntries([
        benchmarkEntry({
          status: "idle",
        }),
      ]),
    );

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await waitFor(() =>
      expect(screen.getByLabelText("Not chemically accurate")).toBeInTheDocument(),
    );

    const chemicalAccuracyInput = screen.getByDisplayValue("1.6");
    fireEvent.change(chemicalAccuracyInput, {
      target: { value: "20" },
    });
    fireEvent.blur(chemicalAccuracyInput);

    await waitFor(() => expect(screen.getByLabelText("Chemically accurate")).toBeInTheDocument());
  });

  it("filters benchmark rows by chemical-accuracy verdict", async () => {
    (getRunResult as ReturnType<typeof vi.fn>).mockImplementation((requestedRunId: string) =>
      Promise.resolve({
        ...runResult,
        run_id: requestedRunId,
        energy: requestedRunId.startsWith("aaaaaa") ? -1.1372 : -1.12,
      }),
    );
    mockBenchmarkDetail(
      savedBenchmarkWithEntries([
        benchmarkEntry({
          id: "h2:vqe",
          status: "completed",
          runId: "aaaaaa00-0000-0000-0000-000000000001",
          energy: -1.1372,
          currentEnergy: -1.1372,
          converged: true,
        }),
        benchmarkEntry({
          id: "h2:qse",
          algorithm: "qse",
          status: "completed",
          runId: "bbbbbb00-0000-0000-0000-000000000001",
          energy: -1.12,
          currentEnergy: -1.12,
          converged: true,
        }),
      ]),
    );

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await waitFor(() => expect(screen.getByText("Algorithm Benchmark")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("aaaaaa...")).toBeInTheDocument());
    expect(screen.getByText("bbbbbb...")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Accurate" }));

    await waitFor(() => expect(screen.getByText("aaaaaa...")).toBeInTheDocument());
    expect(screen.queryByText("bbbbbb...")).not.toBeInTheDocument();
  });
});
