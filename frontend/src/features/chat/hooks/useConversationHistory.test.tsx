import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { PropsWithChildren } from "react";

import {
  getConversationHistory,
  type ConversationHistoryPage,
} from "../api/conversationHistoryApi";
import { useConversationHistory } from "./useConversationHistory";

vi.mock("../api/conversationHistoryApi", () => ({
  getConversationHistory: vi.fn(),
}));

const getHistoryMock = vi.mocked(getConversationHistory);
const CONVERSATION_ID = "00000000-0000-4000-8000-000000000001";

afterEach(() => {
  getHistoryMock.mockReset();
});

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

function page(
  sequences: number[],
  hasMore: boolean,
  nextAfterSequence: number | null,
): ConversationHistoryPage {
  return {
    conversation: {
      id: CONVERSATION_ID,
      createdAt: "2025-01-01T00:00:00Z",
      updatedAt: "2025-01-01T00:00:00Z",
    },
    messages: sequences.map((sequence) => ({
      id: `00000000-0000-4000-8000-${sequence.toString().padStart(12, "0")}`,
      role: "user" as const,
      content: `消息 ${sequence}`,
      sequence,
      createdAt: "2025-01-01T00:00:00Z",
    })),
    hasMore,
    nextAfterSequence,
  };
}

describe("useConversationHistory", () => {
  it("loads subsequent pages using the server sequence cursor", async () => {
    getHistoryMock.mockImplementation(async (_conversationId, options) => (
      options?.afterSequence === 2 ? page([3], false, null) : page([1, 2], true, 2)
    ));
    const { result } = renderHook(() => useConversationHistory(CONVERSATION_ID), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.hasNextPage).toBe(true);
    await result.current.fetchNextPage();
    await waitFor(() => expect(result.current.data?.pages).toHaveLength(2));

    expect(result.current.data?.pages.flatMap((item) => item.messages.map((message) => message.sequence)))
      .toEqual([1, 2, 3]);
    expect(getHistoryMock).toHaveBeenNthCalledWith(
      2,
      CONVERSATION_ID,
      expect.objectContaining({ afterSequence: 2, signal: expect.any(AbortSignal) }),
    );
  });

  it("does not query when there is no active conversation", async () => {
    const { result } = renderHook(() => useConversationHistory(null), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(getHistoryMock).not.toHaveBeenCalled();
  });

  it("aborts the previous request when the active conversation changes", async () => {
    let aborted = false;
    let resolveRequest: (() => void) | undefined;
    getHistoryMock.mockImplementation(async (_conversationId, options) => {
      options?.signal?.addEventListener("abort", () => {
        aborted = true;
        resolveRequest?.();
      });
      await new Promise<void>((resolve) => {
        resolveRequest = resolve;
      });
      return page([], false, null);
    });
    const { result, rerender } = renderHook(
      ({ conversationId }: { conversationId: string | null }) => useConversationHistory(conversationId),
      {
        initialProps: { conversationId: CONVERSATION_ID as string | null },
        wrapper: createWrapper(),
      },
    );

    await waitFor(() => expect(getHistoryMock).toHaveBeenCalled());
    rerender({ conversationId: null });
    await waitFor(() => expect(aborted).toBe(true));
    expect(result.current.fetchStatus).toBe("idle");
  });
});
