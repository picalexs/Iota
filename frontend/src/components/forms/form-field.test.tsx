import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { FormField } from "./form-field";
import { Input } from "@/components/ui/input";

describe("FormField", () => {
  it("renders label with correct text", () => {
    render(
      <FormField label="Test Label" htmlFor="test-input">
        <Input id="test-input" />
      </FormField>,
    );

    const label = screen.getByText("Test Label");
    expect(label).toBeInTheDocument();
  });

  it("shows required indicator (*) when required=true", () => {
    render(
      <FormField label="Required Field" htmlFor="test-input" required>
        <Input id="test-input" />
      </FormField>,
    );

    const requiredIndicator = screen.getByText("*");
    expect(requiredIndicator).toBeInTheDocument();
  });

  it("renders children (field control)", () => {
    render(
      <FormField label="Test Label" htmlFor="test-input">
        <Input id="test-input" placeholder="test-placeholder" />
      </FormField>,
    );

    const input = screen.getByPlaceholderText("test-placeholder");
    expect(input).toBeInTheDocument();
  });

  it("shows error message when error prop provided", () => {
    render(
      <FormField label="Test Label" htmlFor="test-input" error="This field is required">
        <Input id="test-input" />
      </FormField>,
    );

    const errorMessage = screen.getByText("This field is required");
    expect(errorMessage).toBeInTheDocument();
  });

  it("connects label to field with htmlFor/id", () => {
    render(
      <FormField label="Test Label" htmlFor="test-input">
        <Input id="test-input" />
      </FormField>,
    );

    const label = screen.getByText("Test Label") as HTMLLabelElement;
    expect(label.htmlFor).toBe("test-input");
  });

  it("error message has role='alert' for accessibility", () => {
    render(
      <FormField label="Test Label" htmlFor="test-input" error="This field is required">
        <Input id="test-input" />
      </FormField>,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveTextContent("This field is required");
  });

  it("does not show error message when no error provided", () => {
    const { container } = render(
      <FormField label="Test Label" htmlFor="test-input">
        <Input id="test-input" />
      </FormField>,
    );

    const alert = container.querySelector('[role="alert"]');
    expect(alert).not.toBeInTheDocument();
  });
});
