import { appConfig } from "../../../app/appConfig";
import { postSse, StreamingHttpError } from "../../../services/http/streamingHttpClient";

import type {
  InteractionStreamApproval,
  InteractionStreamComplete,
  InteractionStreamHandlers,
  InteractionStreamMeta,
  InteractionStreamResult,
} from "../types";

export class InteractionStreamError extends Error {
  constructor(message: string, readonly retryable = true) {
    super(message);
    this.name = "InteractionStreamError";
  }
}

export type InteractionStreamTerminal = "complete" | "approval_required" | "result";

export async function streamInteractionChat(
  userInput: string,
  handlers: InteractionStreamHandlers,
  signal: AbortSignal,
  conversationId?: string,
): Promise<InteractionStreamTerminal> {
  let terminal: InteractionStreamTerminal | null = null;

  try {
    await postSse(`${appConfig.apiBaseUrl}/v1/interaction/chat/stream`, {
      user_input: userInput,
      provided_inputs: {},
      ...(conversationId ? { conversation_id: conversationId } : {}),
    }, {
      signal,
      onEvent: (event) => {
        if (event.event === "heartbeat") return;
        terminal = handleEvent(event, handlers) ?? terminal;
      },
    });
    if (terminal === null && !signal.aborted) {
      throw new InteractionStreamError("流式响应未正常完成。", true);
    }
    return terminal ?? "result";
  } catch (error) {
    if (error instanceof InteractionStreamError || signal.aborted) throw error;
    if (error instanceof StreamingHttpError) {
      throw new InteractionStreamError(error.message, error.retryable);
    }
    throw error;
  }
}

function handleEvent(
  event: { event: string; data: Record<string, unknown> },
  handlers: InteractionStreamHandlers,
): InteractionStreamTerminal | null {
  if (event.event === "meta") {
    handlers.onMeta?.({
      requestId: stringValue(event.data.request_id),
      model: stringValue(event.data.model),
      promptVersion: stringValue(event.data.prompt_version),
    });
    return null;
  }
  if (event.event === "delta") {
    handlers.onDelta?.(stringValue(event.data.content));
    return null;
  }
  if (event.event === "complete") {
    handlers.onComplete?.({
      requestId: stringValue(event.data.request_id),
      model: stringValue(event.data.model),
      promptVersion: stringValue(event.data.prompt_version),
      usage: objectValue(event.data.usage) as InteractionStreamComplete["usage"],
    });
    return "complete";
  }
  if (event.event === "approval_required") {
    handlers.onApprovalRequired?.({
      proposalId: stringValue(event.data.proposal_id),
      state: approvalState(event.data.state),
      summary: stringValue(event.data.summary),
      confirmationPrompt: stringValue(event.data.confirmation_prompt),
      conversationId: nullableString(event.data.conversation_id) ?? undefined,
    });
    return "approval_required";
  }
  if (event.event === "result") {
    handlers.onResult?.({
      status: resultStatus(event.data.status),
      message: stringValue(event.data.message),
      errorCode: nullableString(event.data.error_code),
    });
    return "result";
  }
  if (event.event === "error") {
    throw new InteractionStreamError(
      stringValue(event.data.message) || "请求暂时无法处理。",
      event.data.retryable !== false,
    );
  }
  return null;
}

function approvalState(value: unknown): InteractionStreamApproval["state"] {
  if (value === "confirmed" || value === "cancelled") return value;
  return "pending";
}

function resultStatus(value: unknown): InteractionStreamResult["status"] {
  if (
    value === "needs_clarification"
    || value === "unrecognized"
    || value === "cancelled"
    || value === "rejected"
    || value === "failed"
  ) {
    return value;
  }
  return "failed";
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function nullableString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function objectValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? value as Record<string, unknown> : {};
}
