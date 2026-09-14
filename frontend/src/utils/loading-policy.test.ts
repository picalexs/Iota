import { describe, it, expect } from "vitest";
import { shouldUseSkeleton, shouldUseSpinner, LOADING_POLICY } from "./loading-policy";

describe("Loading Policy Contract", () => {
  describe("shouldUseSkeleton", () => {
    it("returns true for route-loading context", () => {
      expect(shouldUseSkeleton("route-loading")).toBe(true);
    });

    it("returns false for search context", () => {
      expect(shouldUseSkeleton("search")).toBe(false);
    });

    it("returns false for load-more context", () => {
      expect(shouldUseSkeleton("load-more")).toBe(false);
    });

    it("returns false for mutation context", () => {
      expect(shouldUseSkeleton("mutation")).toBe(false);
    });
  });

  describe("shouldUseSpinner", () => {
    it("returns false for route-loading context", () => {
      expect(shouldUseSpinner("route-loading")).toBe(false);
    });

    it("returns true for search context", () => {
      expect(shouldUseSpinner("search")).toBe(true);
    });

    it("returns true for load-more context", () => {
      expect(shouldUseSpinner("load-more")).toBe(true);
    });

    it("returns true for mutation context", () => {
      expect(shouldUseSpinner("mutation")).toBe(true);
    });
  });

  describe("LOADING_POLICY constants", () => {
    it("defines context types for skeleton-first routes", () => {
      expect(LOADING_POLICY.SKELETON_CONTEXTS).toContain("route-loading");
      expect(LOADING_POLICY.SKELETON_CONTEXTS).not.toContain("search");
      expect(LOADING_POLICY.SKELETON_CONTEXTS).not.toContain("load-more");
    });

    it("defines context types for spinner actions", () => {
      expect(LOADING_POLICY.SPINNER_CONTEXTS).toContain("search");
      expect(LOADING_POLICY.SPINNER_CONTEXTS).toContain("load-more");
      expect(LOADING_POLICY.SPINNER_CONTEXTS).toContain("mutation");
      expect(LOADING_POLICY.SPINNER_CONTEXTS).not.toContain("route-loading");
    });

    it("provides policy description for documentation", () => {
      expect(LOADING_POLICY.description).toBeDefined();
      expect(LOADING_POLICY.description).toContain("skeleton");
      expect(LOADING_POLICY.description).toContain("spinner");
    });
  });
});
