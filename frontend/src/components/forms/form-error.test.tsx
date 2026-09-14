import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { FormError } from "./form-error";

describe("FormError", () => {
  it("renders nothing when message is empty", () => {
    const { container } = render(<FormError message="" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when message is null", () => {
    const { container } = render(<FormError message={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when message is undefined", () => {
    const { container } = render(<FormError message={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders error message when provided", () => {
    render(<FormError message="This is an error" />);
    expect(screen.getByText("This is an error")).toBeInTheDocument();
  });

  it("has role='alert' for accessibility", () => {
    render(<FormError message="Error message" />);
    const alert = screen.getByRole("alert");
    expect(alert).toBeInTheDocument();
  });

  it("has correct styling classes", () => {
    const { container } = render(<FormError message="Error" />);
    const paragraph = container.querySelector("p");
    expect(paragraph).toHaveClass("text-destructive", "text-sm");
  });

  it("accepts optional className prop", () => {
    const { container } = render(<FormError message="Error" className="custom-class" />);
    const paragraph = container.querySelector("p");
    expect(paragraph).toHaveClass("custom-class");
  });
});
