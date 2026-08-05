import { useCallback, useState } from "react";
import axios from "axios";

import {
  generateTenderSkeleton,
  type TenderApiError,
  type TenderSkeletonResult,
} from "../api/tenderApi";

export function useTenderSkeleton() {
  const [result, setResult] = useState<TenderSkeletonResult | null>(null);
  const [error, setError] = useState<TenderApiError | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const submit = useCallback(async (file: File, userFocus: string) => {
    setIsSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const nextResult = await generateTenderSkeleton(file, userFocus);
      setResult(nextResult);
      return nextResult;
    } catch (reason) {
      if (axios.isAxiosError(reason)) {
        const apiError = reason.response?.data?.detail as TenderApiError | undefined;
        setError(apiError ?? { code: "REQUEST_FAILED", message: "请求失败，请稍后重试。" });
      } else {
        setError({ code: "REQUEST_FAILED", message: "请求失败，请稍后重试。" });
      }
      return null;
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  const reset = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return { result, error, isSubmitting, submit, reset };
}
