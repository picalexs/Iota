type LogLevel = "debug" | "info" | "warn" | "error";

type LogContext = Record<string, unknown> | undefined;

function shouldLog(level: LogLevel): boolean {
  return level === "warn" || level === "error" || import.meta.env.DEV;
}

function serializeLogValue(value: unknown): unknown {
  if (value instanceof Error) {
    return serializeError(value);
  }

  return value;
}

function serializeError(error: unknown): Record<string, unknown> | undefined {
  if (!(error instanceof Error)) {
    return error === undefined ? undefined : { value: error };
  }

  const extraProperties = Object.fromEntries(
    Object.getOwnPropertyNames(error)
      .filter((key) => !["name", "message", "stack"].includes(key))
      .map((key) => [key, serializeLogValue(Reflect.get(error, key))]),
  );

  return {
    name: error.name,
    message: error.message,
    stack: error.stack,
    ...extraProperties,
  };
}

function consoleMethodForLevel(level: LogLevel): (...data: unknown[]) => void {
  switch (level) {
    case "debug":
      return globalThis.console.debug;
    case "info":
      return globalThis.console.info;
    case "warn":
      return globalThis.console.warn;
    default:
      return globalThis.console.error;
  }
}

function log(level: LogLevel, scope: string, message: string, context?: LogContext): void {
  if (!shouldLog(level)) return;

  const payload = context && Object.keys(context).length > 0 ? context : undefined;
  const consoleMethod = consoleMethodForLevel(level);

  if (payload) {
    consoleMethod(`[${scope}] ${message}`, payload);
  } else {
    consoleMethod(`[${scope}] ${message}`);
  }
}

export function logAppDebug(scope: string, message: string, context?: LogContext): void {
  log("debug", scope, message, context);
}

export function logAppWarning(scope: string, message: string, context?: LogContext): void {
  log("warn", scope, message, context);
}

export function logAppError(
  scope: string,
  message: string,
  error?: unknown,
  context?: LogContext,
): void {
  const errorContext = serializeError(error);
  log("error", scope, message, {
    ...context,
    ...(errorContext ? { error: errorContext } : {}),
  });
}
