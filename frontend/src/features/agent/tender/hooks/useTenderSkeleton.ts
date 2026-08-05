import { useMutation } from "@tanstack/react-query";
import axios from "axios";

import {
  generateTenderSkeleton,
  type TenderApiError,
  type TenderSkeletonResult,
} from "../api/tenderApi";

const fallbackError: TenderApiError = {
  code: "REQUEST_FAILED",
  message: "请求失败，请稍后重试。",
};

function normalizeError(reason: unknown): TenderApiError {
  if (axios.isAxiosError(reason)) {
    const detail = reason.response?.data?.detail;
    if (detail && typeof detail.code === "string" && typeof detail.message === "string") {
      return detail as TenderApiError;
    }
  }
  return fallbackError;
}

export function useTenderSkeleton() {
  const mutation = useMutation<
    TenderSkeletonResult,
    TenderApiError,
    { file: File; userFocus: string }
  >({
    mutationFn: async ({ file, userFocus }) => {
      try {
        return await generateTenderSkeleton(file, userFocus);
      } catch (reason) {
        throw normalizeError(reason);
      }
    },
  });

  const submit = async (file: File, userFocus: string) => {
    try {
      return await mutation.mutateAsync({ file, userFocus });
    } catch (reason) {
      throw normalizeError(reason);
    }
  };

  return {
    result: mutation.data ?? null,
    error: mutation.error,
    isSubmitting: mutation.isPending,
    submit,
    reset: mutation.reset,
  };
}
