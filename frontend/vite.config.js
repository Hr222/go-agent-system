import { defineConfig } from "vitest/config";
import { loadEnv } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(function (_a) {
    var _b, _c, _d;
    var mode = _a.mode;
    var env = loadEnv(mode, "..", "");
    var backendHost = (_b = env.BACKEND_HOST) !== null && _b !== void 0 ? _b : "127.0.0.1";
    var backendPort = (_c = env.BACKEND_PORT) !== null && _c !== void 0 ? _c : "9205";
    var apiProxyTarget = (_d = env.VITE_API_PROXY_TARGET) !== null && _d !== void 0 ? _d : "http://".concat(backendHost, ":").concat(backendPort);
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
