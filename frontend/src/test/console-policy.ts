import { afterEach, beforeEach, vi } from "vitest";

type ConsoleMethod = "error" | "warn";
type ConsoleMatcher = string | RegExp;

interface ConsoleCall {
  method: ConsoleMethod;
  args: unknown[];
}

const methods: ConsoleMethod[] = ["error", "warn"];
let calls: ConsoleCall[] = [];
let allowedCalls: Array<{ method: ConsoleMethod; matcher: ConsoleMatcher }> = [];
let spies: Partial<Record<ConsoleMethod, ReturnType<typeof vi.spyOn>>> = {};

function callText(args: unknown[]): string {
  return args
    .map((argument) => {
      if (typeof argument === "string") return argument;
      try {
        return JSON.stringify(argument);
      } catch {
        return String(argument);
      }
    })
    .join(" ");
}

function matches(matcher: ConsoleMatcher, args: unknown[]): boolean {
  const text = callText(args);
  if (typeof matcher === "string") return text.includes(matcher);
  matcher.lastIndex = 0;
  return matcher.test(text);
}

/** Allow one expected error or warning in the current test. */
export function allowConsoleCall(method: ConsoleMethod, matcher: ConsoleMatcher): void {
  allowedCalls.push({ method, matcher });
}

beforeEach(() => {
  calls = [];
  allowedCalls = [];

  for (const method of methods) {
    spies[method] = vi.spyOn(globalThis.console, method).mockImplementation((...args) => {
      calls.push({ method, args });
    });
  }
});

afterEach(() => {
  const unexpectedCalls = calls.filter((call) => {
    const allowedIndex = allowedCalls.findIndex(
      (allowedCall) => allowedCall.method === call.method && matches(allowedCall.matcher, call.args),
    );
    if (allowedIndex === -1) return true;

    allowedCalls.splice(allowedIndex, 1);
    return false;
  });

  try {
    if (unexpectedCalls.length > 0) {
      const details = unexpectedCalls
        .map((call) => `${call.method}: ${callText(call.args)}`)
        .join("\n");
      throw new Error(`Unexpected console output:\n${details}`);
    }
  } finally {
    for (const method of methods) {
      spies[method]?.mockRestore();
    }
    spies = {};
    calls = [];
    allowedCalls = [];
  }
});
