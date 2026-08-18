import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { streamInteractionChat } from "../api/interactionStreamApi";
import { useInteractionChatStream } from "./useInteractionChatStream";

vi.mock("../api/interactionStreamApi", () => ({
  InteractionStreamError: class InteractionStreamError extends Error {
    constructor(message: string) {
      super(message);
    }
  },
  streamInteractionChat: vi.fn(),
}));

const streamMock = vi.mocked(streamInteractionChat);

afterEach(() => {
  streamMock.mockReset();
});

describe("useInteractionChatStream", () => {
  it("moves from connecting to completed only after the stream terminal event", async () => {
    streamMock.mockImplementation(async (_input, handlers) => {
      handlers.onMeta?.({ requestId: "r1", model: "glm", promptVersion: "v1" });
      handlers.onDelta?.("你好");
      handlers.onComplete?.({
        requestId: "r1",
        model: "glm",
        promptVersion: "v1",
        usage: { total_tokens: 2 },
      });
      return "complete";
    });
    const { result } = renderHook(() => useInteractionChatStream());

    await act(async () => {
      await result.current.send("你好", {});
    });

    expect(result.current.phase).toBe("completed");
    expect(result.current.isActive).toBe(false);
  });

  it("treats an abort as cancellation rather than a failed request", async () => {
    streamMock.mockImplementation((_input, _handlers, signal) => new Promise((resolve, reject) => {
      signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    }));
    const { result } = renderHook(() => useInteractionChatStream());

    let pending: Promise<unknown>;
    act(() => {
      pending = result.current.send("你好", {});
      result.current.cancel();
    });
    await act(async () => {
      await pending;
    });

    expect(result.current.phase).toBe("cancelled");
  });
});
