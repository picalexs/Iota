import { describe, expect, it } from "vitest";

import { buildBenchmarkBars } from "./benchmarks";

describe("buildBenchmarkBars", () => {
  it("places the method result between HF and FCI/Exact", () => {
    const bars = buildBenchmarkBars(-1.12, { hf: -1, fci: -1.14 }, "vqe");

    expect(bars.map((bar) => bar.label)).toEqual(["HF", "VQE result", "FCI/Exact"]);
    expect(bars[1]).toMatchObject({ energy: -1.12, isResult: true });
  });
});
