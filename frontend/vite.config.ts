import fs from "node:fs";
import { randomBytes } from "node:crypto";
import { loadEnv } from "vite";
import { defineConfig, configDefaults } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootEnvDir = path.resolve(__dirname, "..");
const LOCAL_OPERATOR_HEADER = "X-Local-Operator-Token";

function uniqueOrigins(...values: Array<string | undefined>) {
  return values
    .flatMap((value) => {
      if (!value) return [];
      try {
        return [new URL(value).origin];
      } catch {
        return [];
      }
    })
    .filter((value, index, origins) => origins.indexOf(value) === index);
}

function parseAllowedHosts(value: string | undefined): string[] {
  const configured = value
    ?.split(",")
    .map((host) => host.trim())
    .filter(Boolean);
  return ["localhost", "127.0.0.1", "::1", ...(configured ?? [])];
}

function resolveLocalOperatorToken(env: Record<string, string | undefined>) {
  const directToken = env.LOCAL_OPERATOR_TOKEN?.trim();
  if (directToken) {
    return directToken;
  }

  const tokenFile = env.LOCAL_OPERATOR_TOKEN_FILE?.trim();
  if (!tokenFile) {
    return undefined;
  }

  const tokenPath = path.isAbsolute(tokenFile) ? tokenFile : path.resolve(rootEnvDir, tokenFile);
  fs.mkdirSync(path.dirname(tokenPath), { recursive: true });

  const readToken = () => {
    const token = fs.readFileSync(tokenPath, "utf8").trim();
    if (!token) {
      throw new Error(`Local operator token file is empty: ${tokenPath}`);
    }
    fs.chmodSync(tokenPath, 0o600);
    return token;
  };

  try {
    return readToken();
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    if (code !== "ENOENT") {
      throw error;
    }
  }

  const generatedToken = randomBytes(32).toString("base64url");
  try {
    const fd = fs.openSync(tokenPath, "wx", 0o600);
    try {
      fs.writeFileSync(fd, `${generatedToken}\n`, "utf8");
    } finally {
      fs.closeSync(fd);
    }
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    if (code !== "EEXIST") {
      throw error;
    }
  }

  return readToken();
}

export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, rootEnvDir, ""), ...process.env };
  const apiTargetUrl = env.API_TARGET_URL;
  const viteApiUrl = env.VITE_API_URL;
  const localOperatorToken = resolveLocalOperatorToken(env);
  const apiConnectOrigins = uniqueOrigins(
    apiTargetUrl,
    viteApiUrl,
    "http://localhost:8000",
    "http://127.0.0.1:8000",
  );
  const allowedHosts = parseAllowedHosts(env.VITE_ALLOWED_HOSTS);
  const configureApiProxy = (proxy: {
    on: (event: "error" | "proxyReq" | "proxyRes", handler: (...args: unknown[]) => void) => void;
  }) => {
    proxy.on("error", (err, req) => {
      console.error("[vite-proxy] error:", (req as { url?: string }).url, (err as Error).message);
    });
    proxy.on("proxyReq", (proxyReq, req) => {
      if (localOperatorToken) {
        (
          proxyReq as {
            setHeader: (name: string, value: string) => void;
          }
        ).setHeader(LOCAL_OPERATOR_HEADER, localOperatorToken);
      }
      console.log("[vite-proxy] → forwarding", (req as { url?: string }).url);
    });
    proxy.on("proxyRes", (proxyRes, req) => {
      console.log(
        "[vite-proxy] ← response",
        (req as { url?: string }).url,
        (proxyRes as { statusCode?: number }).statusCode,
      );
    });
  };
  const securityHeaders = {
    "Content-Security-Policy": [
      "default-src 'self'",
      "base-uri 'self'",
      "object-src 'none'",
      "frame-ancestors 'none'",
      "script-src 'self'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      `connect-src 'self' ${apiConnectOrigins.join(" ")}`,
      "frame-src https://video.ibm.com",
      "worker-src 'self' blob:",
      "form-action 'self'",
    ].join("; "),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
  };

  return {
    envDir: rootEnvDir,
    plugins: [
      react(),
      // Dev-only: trace all /api requests reaching Vite's middleware
      {
        name: "api-trace",
        configureServer(server) {
          server.middlewares.use((req, _res, next) => {
            if (req.url?.startsWith("/api/")) {
              console.log(
                `[vite-middleware] ${req.method} ${req.url} from ${req.socket.remoteAddress}`,
              );
            }
            next();
          });
        },
      },
    ],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            react: ["react", "react-dom", "react/jsx-runtime"],
            router: ["@tanstack/react-router"],
            query: ["@tanstack/react-query"],
            visx: [
              "@visx/responsive",
              "@visx/group",
              "@visx/shape",
              "@visx/scale",
              "@visx/axis",
              "@visx/grid",
            ],
            grid: ["react-grid-layout"],
            icons: ["lucide-react"],
          },
        },
      },
    },
    server: {
      port: 5173,
      host: true,
      allowedHosts,
      proxy: {
        "/api": {
          target: apiTargetUrl ?? "http://api:8000",
          // Keep the browser host so the API trusted-host policy accepts local dev requests.
          changeOrigin: false,
          configure: configureApiProxy,
        },
      },
    },
    preview: {
      port: 4173,
      host: true,
      allowedHosts,
      headers: securityHeaders,
      proxy: {
        "/api": {
          target: apiTargetUrl ?? "http://localhost:8000",
          changeOrigin: true,
          configure: configureApiProxy,
        },
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      testTimeout: 10000,
      setupFiles: ["./src/test/setup.ts"],
      exclude: [...configDefaults.exclude, "test/playwright/**/*", "scripts/**/*.test.mjs"],
      coverage: {
        provider: "v8",
        reporter: ["text", "json-summary", "html", "lcov"],
        reportsDirectory: "./coverage",
        exclude: [
          ...(configDefaults.coverage.exclude ?? []),
          "src/test/**",
          "src/types/api.ts",
          "test/playwright/**",
        ],
        thresholds: {
          statements: 50,
          branches: 40,
          functions: 45,
          lines: 50,
        },
      },
    },
  };
});
