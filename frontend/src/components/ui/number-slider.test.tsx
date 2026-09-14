import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { NumberSlider } from "./number-slider";

describe("NumberSlider", () => {
  it("renders slider and numeric input", () => {
    render(
      <NumberSlider id="iterations" value={10} onChange={vi.fn()} min={1} max={100} step={1} />,
    );

    expect(screen.getByRole("spinbutton")).toHaveValue(10);
  });

  it("commits clamped numeric input on blur", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <NumberSlider id="iterations" value={10} onChange={onChange} min={1} max={100} step={1} />,
    );

    const input = screen.getByRole("spinbutton");
    await user.clear(input);
    await user.type(input, "200");
    await user.tab();

    expect(onChange).toHaveBeenCalledWith(100);
  });
});
