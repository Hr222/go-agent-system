import { useCallback, useRef, useState } from "react";

import { ChatStreamError, streamChatMessage } from "../api/chatStreamApi";
import type { ChatStreamHandlers } from "../types";

export type ChatStreamPhase = "idle" | "connecting" | "streaming" | "completed" | "cancelled" | "failed";

export function useChatStream() {
  const [phase, setPhase] = useState<ChatStreamPhase>("idle");
  const controllerRef = useRef<AbortController | null>(null);

  const send = useCallback(async (message: string, handlers: ChatStreamHandlers) => {
    const controller = new AbortController();
    controllerRef.current = controller;
    setPhase("connecting");
    try {
      await streamChatMessage(message, {
        ...handlers,
        onMeta: (meta) => {
          setPhase("streaming");
          handlers.onMeta?.(meta);
        },
      }, controller.signal);
      setPhase("completed");
    } catch (error) {
      if (controller.signal.aborted) {
        setPhase("cancelled");
        return;
      }
      setPhase("failed");
      throw error instanceof ChatStreamError ? error : new ChatStreamError("流式请求失败。");
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null;
    }
  }, []);

  const cancel = useCallback(() => controllerRef.current?.abort(), []);

  return { phase, isActive: phase === "connecting" || phase === "streaming", send, cancel };
}
