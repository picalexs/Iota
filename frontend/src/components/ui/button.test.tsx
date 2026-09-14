import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "./button";

describe("Button", () => {
  it("uses state-only transitions instead of hover movement", () => {
    const { container } = render(<Button>Click me</Button>);
    const buttonElement = container.querySelector("button");
    const className = buttonElement?.className || "";

    expect(buttonElement).toBeTruthy();
    expect(className).toContain("transition-[background-color,border-color,color,box-shadow]");
    expect(className).toContain("duration-150");
    expect(className).not.toContain("hover:scale");
    expect(className).not.toContain("active:scale");
    expect(className).not.toContain("hover:-translate");
  });

  it("keeps the default button expressive with subtle tokenized elevation", () => {
    const { container } = render(<Button variant="default">Primary</Button>);
    const buttonElement = container.querySelector("button");
    const className = buttonElement?.className || "";

    expect(className).toContain("shadow-[var(--shadow-button-primary)]");
    expect(className).toContain("hover:shadow-[var(--shadow-elevation-raised)]");
    expect(className).toContain("active:shadow-[var(--shadow-button-primary-pressed)]");
    expect(className).not.toContain("rgba(79,111,214");
  });

  it("keeps standard variants flat enough to rely on tone and borders", () => {
    const { container } = render(
      <div>
        <Button variant="secondary">Secondary</Button>
        <Button variant="outline">Outline</Button>
        <Button variant="destructive">Delete</Button>
      </div>,
    );

    const classNames = Array.from(container.querySelectorAll("button")).map(
      (button) => button.className,
    );

    for (const className of classNames) {
      expect(className).not.toContain("hover:scale");
      expect(className).not.toContain("active:scale");
      expect(className).not.toContain("hover:-translate");
    }
  });

  it("uses a dedicated focus ring that stays separate from selection styling", () => {
    const { container } = render(<Button variant="outline">Focus me</Button>);
    const buttonElement = container.querySelector("button");
    const className = buttonElement?.className || "";

    expect(className).toContain("focus-visible:ring-focus-strong");
    expect(className).toContain("focus-visible:border-accent-2/60");
    expect(className).not.toContain("data-[selected=true]");
  });

  it("keeps ghost and link variants flat", () => {
    const { container } = render(
      <div>
        <Button variant="ghost">Ghost</Button>
        <Button variant="link">Link</Button>
      </div>,
    );

    const classNames = Array.from(container.querySelectorAll("button")).map(
      (button) => button.className,
    );

    expect(classNames[0]).toContain("shadow-none");
    expect(classNames[1]).toContain("shadow-none");
  });

  it("matches snapshot", () => {
    const { container } = render(
      <div>
        <Button>Default</Button>
        <Button variant="secondary">Secondary</Button>
        <Button variant="destructive">Destructive</Button>
        <Button variant="outline">Outline</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="link">Link</Button>
      </div>,
    );

    expect(container.firstChild).toMatchSnapshot();
  });
});
