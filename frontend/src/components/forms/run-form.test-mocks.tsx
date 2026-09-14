import { forwardRef } from "react";
import { vi } from "vitest";

const runFormTestMocks = vi.hoisted(() => ({
  invalidateQueries: vi.fn(),
  navigate: vi.fn(),
}));

export function getRunFormTestMocks() {
  return runFormTestMocks;
}

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return {
    ...actual,
    useQueryClient: () => ({
      invalidateQueries: runFormTestMocks.invalidateQueries,
    }),
  };
});

vi.mock("@/api/molecules", () => ({
  fetchMolecules: vi.fn(),
  fetchBasisSets: vi.fn(),
}));

vi.mock("@/api/runs", () => ({
  createRun: vi.fn(),
  fetchRunConfigMetadata: vi.fn(),
  validateRunRequest: vi
    .fn()
    .mockResolvedValue({ valid: true, errors: [], warnings: [], estimate: null }),
}));

vi.mock("@/api/backends", () => ({
  fetchBackendCapabilities: vi.fn(),
  forceRefreshBackendCapabilities: vi.fn(),
  getBackendCapabilitiesCached: vi.fn().mockReturnValue(null),
  startBackendCapabilitiesAutoRefresh: vi.fn(),
  previewTranspilation: vi.fn(),
}));

vi.mock("@/api/profiles", () => ({
  listIbmCredentialProfiles: vi.fn(),
  testIbmCredentialProfile: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("./field-help", () => ({
  FieldHelp: () => <span data-testid="field-help" />,
}));

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => runFormTestMocks.navigate,
  Link: forwardRef<
    HTMLAnchorElement,
    React.AnchorHTMLAttributes<HTMLAnchorElement> & {
      to?: string;
      hash?: string;
      params?: Record<string, string>;
      state?: unknown;
    }
  >(({ children, to, hash, params, state: _state, ...props }, ref) => {
    const basePath = Object.entries(params ?? {}).reduce(
      (path, [key, value]) => path.replace(`$${key}`, value),
      to ?? "#",
    );
    const href = hash ? `${basePath}#${hash}` : basePath;

    return (
      <a ref={ref} href={href} {...props}>
        {children}
      </a>
    );
  }),
}));
