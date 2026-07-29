import { defineConfig } from "vitest/config";
import { loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, "..", "");
  const backendHost = env.BACKEND_HOST ?? "127.0.0.1";
  const backendPort = env.BACKEND_PORT ?? "9205";
  const apiProxyTarget =
    env.VITE_API_PROXY_TARGET ?? `http://${backendHost}:${backendPort}`;

  return {
    plugins: [react()],
    test: {
      environment: "jsdom",
    },
    server: {
      port: 5426,
      proxy: {
        "/api": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
