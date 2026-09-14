import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(frontendRoot, "..");
const trackedOutputPath = resolve(frontendRoot, "src/types/generated-api.ts");
const checkOnly = process.argv.includes("--check");
const configuredInput = process.env.OPENAPI_INPUT;
const configuredPython = process.env.PYTHON;
const pythonCommand = configuredPython
  ? resolve(process.cwd(), configuredPython)
  : existsSync(resolve(repositoryRoot, ".venv/bin/python"))
    ? resolve(repositoryRoot, ".venv/bin/python")
    : "python3";
const npxCommand = process.platform === "win32" ? "npx.cmd" : "npx";

let temporaryDirectory;
let schemaPath = configuredInput ? resolve(process.cwd(), configuredInput) : null;
let outputPath = trackedOutputPath;

try {
  if (checkOnly) {
    temporaryDirectory = mkdtempSync(resolve(tmpdir(), "quantum-vqe-openapi-check-"));
    outputPath = resolve(temporaryDirectory, "generated-api.ts");
  }

  if (!schemaPath) {
    temporaryDirectory ??= mkdtempSync(resolve(tmpdir(), "quantum-vqe-openapi-"));
    schemaPath = resolve(temporaryDirectory, "openapi.json");
    execFileSync(
      pythonCommand,
      [resolve(repositoryRoot, "scripts/contracts/export-openapi.py"), "--output", schemaPath],
      { cwd: repositoryRoot, stdio: "inherit" },
    );
  }

  execFileSync(
    npxCommand,
    ["--no-install", "openapi-typescript", schemaPath, "-o", outputPath],
    { cwd: frontendRoot, stdio: "inherit" },
  );

  if (checkOnly) {
    const expected = readFileSync(trackedOutputPath, "utf8");
    const generated = readFileSync(outputPath, "utf8");
    if (expected !== generated) {
      throw new Error(
        "Generated API types are stale. Run 'npm run generate:types' from frontend and review the diff.",
      );
    }
    console.log("Generated API types are up to date");
  }
} finally {
  if (temporaryDirectory) {
    rmSync(temporaryDirectory, { recursive: true, force: true });
  }
}
