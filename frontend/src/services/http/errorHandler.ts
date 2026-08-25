import axios from "axios";

import type { ApiError } from "./requestTypes";

export function toApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    const message = errorMessageFromDetail(detail);
    return {
      message: message ?? error.message ?? "请求失败，请稍后重试。",
      status: error.response?.status,
      code: error.code,
    };
  }

  if (error instanceof Error) {
    return { message: error.message };
  }

  return { message: "请求失败，请稍后重试。" };
}

function errorMessageFromDetail(detail: unknown): string | undefined {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (
    detail
    && typeof detail === "object"
    && "message" in detail
    && typeof detail.message === "string"
    && detail.message.trim()
  ) {
    return detail.message;
  }
  return undefined;
}
