import { isBackendTarget } from "@/types/run-status";

// Matches UUID shape without restricting version or variant bits.
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function validateMoleculeId(value: string | null): string | null {
  if (!value) {
    return "Molecule selection is required";
  }

  if (!UUID_REGEX.test(value)) {
    return "Molecule ID must be a valid UUID";
  }

  return null;
}

export function validateAnsatz(value: string): string | null {
  if (!value || value.trim() === "") {
    return "Ansatz is required";
  }

  return null;
}

export function validateOptimizer(value: string): string | null {
  if (!value || value.trim() === "") {
    return "Optimizer is required";
  }

  return null;
}

// The default ceiling mirrors backend/app/services/validation_service.py.
export function validateMaxIterations(value: number, max = 5000): string | null {
  if (!Number.isFinite(value) || !Number.isInteger(value)) {
    return "Max iterations must be a valid integer";
  }

  if (value < 1) {
    return "Max iterations must be at least 1";
  }

  if (value > max) {
    return `Max iterations cannot exceed ${max}`;
  }

  return null;
}

// Run-form schema and server-side validation refine backend availability.
export function validateBackend(value: string | null): string | null {
  if (!value || value.trim() === "") {
    return "Backend is required";
  }

  const normalized = value.trim();

  if (!isBackendTarget(normalized)) {
    return "Select Statevector, Aer simulator, or IBM Runtime";
  }

  return null;
}
