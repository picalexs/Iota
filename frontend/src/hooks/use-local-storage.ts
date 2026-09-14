import { useState, useEffect, type Dispatch, type SetStateAction } from "react";
import { logAppWarning } from "@/lib/app-logger";

export function useLocalStorage<T>(key: string, defaultValue: T): [T, Dispatch<SetStateAction<T>>] {
  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = globalThis.localStorage.getItem(key);
      return item ? JSON.parse(item) : defaultValue;
    } catch {
      return defaultValue;
    }
  });

  useEffect(() => {
    try {
      globalThis.localStorage.setItem(key, JSON.stringify(storedValue));
    } catch (err) {
      logAppWarning("storage.local", `Failed to write local storage key '${key}'.`, {
        error: err instanceof Error ? { name: err.name, message: err.message } : err,
      });
    }
  }, [key, storedValue]);

  return [storedValue, setStoredValue];
}

export default useLocalStorage;
