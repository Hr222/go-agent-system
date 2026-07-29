import { appConfig } from "../../../app/appConfig";
import { postSse, StreamingHttpError } from "../../../services/http/streamingHttpClient";

import type { ChatStreamComplete, ChatStreamHandlers, ChatStreamMeta } from "../types";

export class ChatStreamError extends Error {
  constructor(message: string, readonly retryable = true) {
    super(message);
    this.name = "ChatStreamError";
  }
}

export async function streamChatMessage(
  message: string,
  handlers: ChatStreamHandlers,
  signal: AbortSignal,
): Promise<void> {
  let completed = false;

  try {
    await postSse(`${appConfig.apiBaseUrl}/v1/llm/chat/stream`, { message }, {
      signal,
      onEvent: (event) => {
      if (event.event === "complete") completed = true;
      handleEvent(event, handlers);
      },
    });
    if (!completed && !signal.aborted) {
      throw new ChatStreamError("流式响应未正常完成。");
    }
  } catch (error) {
    if (error instanceof ChatStreamError || signal.aborted) throw error;
    if (error instanceof StreamingHttpError) {
      throw new ChatStreamError(error.message, error.retryable);
    }
    throw error;
  }
}

function handleEvent(
  event: { event: string; data: Record<string, unknown> },
  handlers: ChatStreamHandlers,
): void {
  if (event.event === "meta") {
    handlers.onMeta?.({
      requestId: stringValue(event.data.request_id),
      model: stringValue(event.data.model),
      promptVersion: stringValue(event.data.prompt_version),
    });
  } else if (event.event === "delta") {
    handlers.onDelta?.(stringValue(event.data.content));
  } else if (event.event === "complete") {
    handlers.onComplete?.({
      requestId: stringValue(event.data.request_id),
      model: stringValue(event.data.model),
      promptVersion: stringValue(event.data.prompt_version),
      usage: objectValue(event.data.usage) as ChatStreamComplete["usage"],
    });
  } else if (event.event === "error") {
    throw new ChatStreamError(
      stringValue(event.data.message) || "模型请求失败。",
      event.data.retryable !== false,
    );
  }
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function objectValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? value as Record<string, unknown> : {};
}
