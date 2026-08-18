import { useCallback, useRef, useState } from "react";

import {
  InteractionStreamError,
  streamInteractionChat,
  type InteractionStreamTerminal,
} from "../api/interactionStreamApi";
import type { InteractionStreamHandlers } from "../types";

export type InteractionChatStreamPhase =
  | "idle"
  | "connecting"
  | "streaming"
  | "awaiting_approval"
  | "result"
  | "completed"
  | "cancelled"
  | "failed";

export function useInteractionChatStream() {
  const [phase, setPhase] = useState<InteractionChatStreamPhase>("idle");
  const controllerRef = useRef<AbortController | null>(null);

  const send = useCallback(async (
    userInput: string,
    handlers: InteractionStreamHandlers,
  ): Promise<InteractionStreamTerminal | undefined> => {
    const controller = new AbortController();
    controllerRef.current = controller;
    setPhase("connecting");
    try {
      const terminal = await streamInteractionChat(userInput, {
        ...handlers,
        onMeta: (meta) => {
          setPhase("streaming");
          handlers.onMeta?.(meta);
        },
      }, controller.signal);
      setPhase(terminal === "complete" ? "completed" : terminal === "result" ? "result" : "awaiting_approval");
      return terminal;
    } catch (error) {
      if (controller.signal.aborted) {
        setPhase("cancelled");
        return undefined;
      }
      setPhase("failed");
      throw error instanceof InteractionStreamError
        ? error
        : new InteractionStreamError(
          error instanceof Error && error.message ? error.message : "流式请求失败。",
          true,
        );
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null;
    }
  }, []);

  const cancel = useCallback(() => controllerRef.current?.abort(), []);

  return {
    phase,
    isActive: phase === "connecting" || phase === "streaming",
    send,
    cancel,
  };
}
