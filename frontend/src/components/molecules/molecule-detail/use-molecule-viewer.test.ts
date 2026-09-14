import { afterAll, afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { downloadViewerImage, downloadXyz } from "./use-molecule-viewer";
import type { AtomSchema } from "@/types/run";

const atoms: AtomSchema[] = [
  { symbol: "H", x: 0, y: 0, z: 0 },
  { symbol: "O", x: 0, y: 0, z: 0.96 },
];

describe("molecule viewer downloads", () => {
  const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  const createObjectURL = vi.fn((_: Blob | MediaSource) => "blob:molecule");
  const revokeObjectURL = vi.fn();

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

  it("downloads XYZ files with sanitized molecule names", async () => {
    downloadXyz("  Water / optimized!  ", atoms);

    expect(clickSpy).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:molecule");
    const blob = createObjectURL.mock.calls[0]?.[0] as unknown as Blob;
    await expect(blob.text()).resolves.toContain("2\nMolecule\nH");
  });

  it("downloads a 2D SVG snapshot when an SVG is present", async () => {
    const container = document.createElement("div");
    container.innerHTML = `<svg><circle cx="1" cy="1" r="1" /></svg>`;

    downloadViewerImage("H₂ Molecule", "2d", container);

    expect(clickSpy).toHaveBeenCalledOnce();
    const blob = createObjectURL.mock.calls[0]?.[0] as unknown as Blob;
    await expect(blob.text()).resolves.toContain("<svg");
  });

  it("skips missing containers or missing 2D SVGs", () => {
    downloadViewerImage("No container", "2d", null);
    downloadViewerImage("No svg", "2d", document.createElement("div"));

    expect(clickSpy).not.toHaveBeenCalled();
    expect(createObjectURL).not.toHaveBeenCalled();
  });

  it("downloads a 3D canvas snapshot when a canvas produces a blob", () => {
    const container = document.createElement("div");
    const canvas = document.createElement("canvas");
    const imageBlob = new Blob(["png"], { type: "image/png" });
    canvas.toBlob = vi.fn((callback: BlobCallback) => callback(imageBlob));
    container.appendChild(canvas);

    downloadViewerImage("Canvas molecule", "3d", container);

    expect(clickSpy).toHaveBeenCalledOnce();
    expect(createObjectURL).toHaveBeenCalledWith(imageBlob);
  });

  it("skips 3D snapshots when the canvas cannot produce a blob", () => {
    const container = document.createElement("div");
    const canvas = document.createElement("canvas");
    canvas.toBlob = vi.fn((callback: BlobCallback) => callback(null));
    container.appendChild(canvas);

    downloadViewerImage("Canvas molecule", "3d", container);

    expect(clickSpy).not.toHaveBeenCalled();
    expect(createObjectURL).not.toHaveBeenCalled();
  });
});
