import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const vitestCli = fileURLToPath(new URL("../node_modules/vitest/vitest.mjs", import.meta.url));
const args = process.argv.slice(2);

const child = spawn(process.execPath, [vitestCli, ...args], {
  env: {
    ...process.env,
    TZ: process.env.TZ ?? "Europe/Bucharest",
  },
  stdio: "inherit",
});

child.on("error", (error) => {
  console.error(`Unable to start Vitest: ${error.message}`);
  process.exitCode = 1;
});

child.on("exit", (code, signal) => {
  process.exitCode = code ?? (signal ? 1 : 0);
});
