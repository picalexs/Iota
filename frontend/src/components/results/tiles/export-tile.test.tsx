import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterAll, afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ExportDropdown } from "./export-tile";
import type { RunEventResponse, RunResponse, RunResultResponse } from "@/types/run";

const run: RunResponse = {
  id: "aaaaaaaa-0000-0000-0000-000000000001",
  molecule_id: "bbbbbbbb-0000-0000-0000-000000000001",
  status: "COMPLETED",
  algorithm: "vqe",
  mode: "advanced",
  backend_target: "statevector",
  config_json: { algorithm: "vqe" },
  ibm_job_id: null,
  client_request_id: null,
  versions: null,
  metadata: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const result: RunResultResponse = {
  run_id: run.id,
  energy: -1.137,
  iterations: 2,
  optimal_parameters: [0.25, -0.5],
  converged: true,
  algorithm_metrics: {
    convergence_trace: [-1, -1.137],
    parameter_l2_norm_trace: [0.1, 0.2],
  },
  created_at: "2026-01-01T00:00:00Z",
};

const events: RunEventResponse[] = [
  {
    id: 1,
    run_id: run.id,
    sequence: 1,
    type: "iteration_update",
    payload: { iteration: 1, energy: -1, delta_energy: 0.1, parameter_l2_norm: 0.1 },
    created_at: "2026-01-01T00:00:01Z",
  },
];

function openMenu() {
  render(<ExportDropdown run={run} result={result} events={events} />);
  fireEvent.click(screen.getByRole("button", { name: /export/i }));
  return screen.getByRole("dialog");
}

describe("ExportDropdown", () => {
  const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  const createObjectURL = vi.fn((_: Blob | MediaSource) => "blob:export");
  const revokeObjectURL = vi.fn();

  function createdBlob(index: number): Blob {
    const blob = createObjectURL.mock.calls[index]?.[0];
    if (!(blob instanceof Blob)) {
      throw new TypeError(`Expected createObjectURL call ${index} to receive a Blob`);
    }
    return blob;
  }

  beforeEach(() => {
    createObjectURL.mockClear();
    revokeObjectURL.mockClear();
    clickSpy.mockClear();
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL,
      revokeObjectURL,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  afterAll(() => {
    clickSpy.mockRestore();
  });

  it("downloads a JSON bundle and closes the menu", async () => {
    const menu = openMenu();

    fireEvent.click(within(menu).getByRole("button", { name: /json bundle/i }));

    expect(clickSpy).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:export");
    await expect(createdBlob(0).text()).resolves.toContain('"events"');
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("downloads convergence and parameter CSV files", async () => {
    const menu = openMenu();

    fireEvent.click(within(menu).getByRole("button", { name: /csv \(convergence trace\)/i }));

    await expect(createdBlob(0).text()).resolves.toContain(
      "iteration,energy_ha,delta_energy,parameter_l2_norm",
    );

    fireEvent.click(screen.getByRole("button", { name: /export/i }));
    fireEvent.click(screen.getByRole("button", { name: /csv \(optimal parameters\)/i }));

    await expect(createdBlob(1).text()).resolves.toContain("index,value_radians\n0,0.25\n1,-0.5");
  });

  it("exports visible SVG plots with slugged tile and plot names", () => {
    const dashboardRoot = document.createElement("div");
    dashboardRoot.dataset.resultsDashboardRoot = "";
    dashboardRoot.innerHTML = `
      <section data-dashboard-tile data-tile-title="Energy Δ Plot">
        <figure>
          <svg aria-label="Best value vs CASCI"><path /></svg>
        </figure>
      </section>
      <svg aria-label="Raw spectrum"></svg>
    `;
    document.body.appendChild(dashboardRoot);

    const menu = openMenu();
    fireEvent.click(within(menu).getByRole("button", { name: /svg \(all visible plots\)/i }));

    expect(clickSpy).toHaveBeenCalledTimes(2);
    expect(createObjectURL).toHaveBeenCalledTimes(2);

    dashboardRoot.remove();
  });
});
