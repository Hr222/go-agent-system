export const appConfig = {
  appName: "Go Agent System",
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "/api",
  knowledgeBaseDataSource: import.meta.env.VITE_KB_DATA_SOURCE ?? "api",
  requestTimeoutMs: Number(import.meta.env.VITE_API_TIMEOUT_MS ?? 15_000),
  llmRequestTimeoutMs: Number(import.meta.env.VITE_LLM_TIMEOUT_MS ?? 90_000),
} as const;
