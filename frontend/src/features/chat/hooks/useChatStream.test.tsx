import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatStreamError, streamChatMessage } from "../api/chatStreamApi";
import { useChatStream } from "./useChatStream";

vi.mock("../api/chatStreamApi", () => ({
  ChatStreamError: class ChatStreamError extends Error {
    constructor(message: string) {
      super(message);
    }
  },
  streamChatMessage: vi.fn(),
}));

const streamMock = vi.mocked(streamChatMessage);

afterEach(() => {
  streamMock.mockReset();
});

describe("useChatStream", () => {
  it("在 connecting、streaming、completed 之间正确切换", async () => {
    streamMock.mockImplementation(async (_message, handlers) => {
      handlers.onMeta?.({ requestId: "r1", model: "glm", promptVersion: "v1" });
      handlers.onDelta?.("你好");
      handlers.onComplete?.({ requestId: "r1", model: "glm", promptVersion: "v1", usage: { input_tokens: 1, output_tokens: 2, total_tokens: 3 } });
    });
    const { result } = renderHook(() => useChatStream());

    await act(async () => {
      await result.current.send("你好", {});
    });

    expect(result.current.phase).toBe("completed");
    expect(result.current.isActive).toBe(false);
  });

  it("只在请求失败后标记失败，不会自动重试", async () => {
    streamMock.mockRejectedValue(new ChatStreamError("上游失败"));
    const { result } = renderHook(() => useChatStream());
    let error: unknown;

    await act(async () => {
      try {
        await result.current.send("你好", {});
      } catch (caught) {
        error = caught;
      }
    });

    expect(error).toBeInstanceOf(ChatStreamError);
    expect(result.current.phase).toBe("failed");
    expect(streamMock).toHaveBeenCalledTimes(1);
  });

  it("取消请求后标记取消且不转换为失败", async () => {
    streamMock.mockImplementation((_message, _handlers, signal) => new Promise<void>((_resolve, reject) => {
      signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    }));
    const { result } = renderHook(() => useChatStream());

    let pending: Promise<void>;
    act(() => {
      pending = result.current.send("你好", {});
      result.current.cancel();
    });
    await act(async () => {
      await pending!;
    });

    expect(result.current.phase).toBe("cancelled");
  });
});
