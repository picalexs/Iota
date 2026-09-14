import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, fireEvent, render, waitFor } from "@testing-library/react";
import { MoleculeViewer3D } from "./molecule-viewer-3d";
import type { AtomSchema } from "@/types/run";

const viewerMock = {
  addModel: vi.fn(),
  setStyle: vi.fn(),
  zoomTo: vi.fn(),
  zoom: vi.fn(),
  render: vi.fn(),
  clear: vi.fn(),
  setBackgroundColor: vi.fn(),
  getView: vi.fn(() => [0, 0, 0, 10, 0, 0, 0, 1]),
  resize: vi.fn(),
  spin: vi.fn(),
};

// Mock 3Dmol library
vi.mock("3dmol", () => ({
  default: {
    createViewer: vi.fn(() => viewerMock),
  },
}));

describe("MoleculeViewer3D", () => {
  const mockAtoms: AtomSchema[] = [
    { symbol: "H", x: 0, y: 0, z: 0 },
    { symbol: "H", x: 0, y: 0, z: 0.74 },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders a div with data-testid='molecule-viewer-3d'", () => {
    const { getByTestId } = render(<MoleculeViewer3D atoms={mockAtoms} />);

    expect(getByTestId("molecule-viewer-3d")).toBeTruthy();
  });

  it("accepts atoms prop", () => {
    const { getByTestId } = render(<MoleculeViewer3D atoms={mockAtoms} />);

    const container = getByTestId("molecule-viewer-3d");
    expect(container).toBeTruthy();
  });

  it("accepts style prop", () => {
    const { getByTestId } = render(<MoleculeViewer3D atoms={mockAtoms} style="space-filling" />);

    const container = getByTestId("molecule-viewer-3d");
    expect(container).toBeTruthy();
  });

  it("has correct className when provided", () => {
    const testClass = "test-class";
    const { getByTestId } = render(<MoleculeViewer3D atoms={mockAtoms} className={testClass} />);

    const container = getByTestId("molecule-viewer-3d");
    expect(container).toHaveClass(testClass);
  });

  it("renders in light mode with isDark={false}", () => {
    const { getByTestId } = render(<MoleculeViewer3D atoms={mockAtoms} isDark={false} />);
    expect(getByTestId("molecule-viewer-3d")).toBeTruthy();
  });

  it("renders in dark mode with isDark={true}", () => {
    const { getByTestId } = render(<MoleculeViewer3D atoms={mockAtoms} isDark={true} />);
    expect(getByTestId("molecule-viewer-3d")).toBeTruthy();
  });

  it("updates when isDark prop changes", () => {
    const { rerender, getByTestId } = render(<MoleculeViewer3D atoms={mockAtoms} isDark={false} />);
    expect(getByTestId("molecule-viewer-3d")).toBeTruthy();

    rerender(<MoleculeViewer3D atoms={mockAtoms} isDark={true} />);
    expect(getByTestId("molecule-viewer-3d")).toBeTruthy();
  });

  it("zooms in slightly after fitting the default 3D view", async () => {
    render(<MoleculeViewer3D atoms={mockAtoms} />);

    await waitFor(() => {
      expect(viewerMock.zoomTo).toHaveBeenCalled();
      expect(viewerMock.zoom).toHaveBeenCalledWith(1.18);
    });
  });

  it("pauses on hover and resumes auto-rotation after an idle delay", async () => {
    vi.useFakeTimers();
    const { getByTestId } = render(<MoleculeViewer3D atoms={mockAtoms} />);
    const container = getByTestId("molecule-viewer-3d");

    await act(async () => {
      await Promise.resolve();
    });
    expect(viewerMock.spin).toHaveBeenCalledWith("vy", expect.any(Number), true);

    fireEvent.pointerEnter(container);
    expect(viewerMock.spin).toHaveBeenLastCalledWith(false);

    fireEvent.pointerLeave(container);

    act(() => {
      vi.advanceTimersByTime(1800);
    });

    expect(viewerMock.spin).toHaveBeenLastCalledWith("vy", expect.any(Number), true);
  });
});
