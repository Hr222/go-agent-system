import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { PropsWithChildren } from "react";

import {
  createConversation,
  deleteConversation,
  listConversationSummaries,
  updateConversationPin,
} from "../api/conversationListApi";
import { useConversationList, useCreateConversation, useDeleteConversation, useUpdateConversationPin } from "./useConversationList";

vi.mock("../api/conversationListApi", () => ({
  createConversation: vi.fn(),
  deleteConversation: vi.fn(),
  listConversationSummaries: vi.fn(),
  updateConversationPin: vi.fn(),
}));

const listMock = vi.mocked(listConversationSummaries);
const createMock = vi.mocked(createConversation);
const deleteMock = vi.mocked(deleteConversation);
const pinMock = vi.mocked(updateConversationPin);

afterEach(() => {
  listMock.mockReset();
  createMock.mockReset();
  deleteMock.mockReset();
  pinMock.mockReset();
});

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const summary = {
  id: "00000000-0000-4000-8000-000000000001",
  createdAt: "2025-01-01T00:00:00Z",
  updatedAt: "2025-01-02T00:00:00Z",
  topicSummary: null,
  isPinned: false,
};

describe("conversation list hooks", () => {
  it("loads additional summary pages with the returned cursor", async () => {
    listMock.mockImplementation(async ({ cursor } = {}) => cursor
      ? { conversations: [{ ...summary, id: "00000000-0000-4000-8000-000000000002" }], hasMore: false, nextCursor: null }
      : { conversations: [summary], hasMore: true, nextCursor: "next" });
    const { result } = renderHook(() => useConversationList(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.hasNextPage).toBe(true);
    await result.current.fetchNextPage();
    await waitFor(() => expect(result.current.data?.pages).toHaveLength(2));

    expect(result.current.data?.pages.flatMap((page) => page.conversations.map((item) => item.id)))
      .toEqual([
        "00000000-0000-4000-8000-000000000001",
        "00000000-0000-4000-8000-000000000002",
      ]);
  });

  it("creates a conversation and invalidates the list query", async () => {
    createMock.mockResolvedValue(summary);
    const { result } = renderHook(() => useCreateConversation(), { wrapper: createWrapper() });

    await expect(result.current.mutateAsync()).resolves.toEqual(summary);
    expect(createMock).toHaveBeenCalledOnce();
  });

  it("updates pin state and deletes a conversation", async () => {
    pinMock.mockResolvedValue({ ...summary, isPinned: true });
    deleteMock.mockResolvedValue(undefined);
    const { result } = renderHook(() => useUpdateConversationPin(), { wrapper: createWrapper() });
    await expect(result.current.mutateAsync({ conversationId: summary.id, isPinned: true }))
      .resolves.toMatchObject({ isPinned: true });
    const deletion = renderHook(() => useDeleteConversation(), { wrapper: createWrapper() });
    await expect(deletion.result.current.mutateAsync(summary.id)).resolves.toBeUndefined();
    expect(pinMock).toHaveBeenCalledWith(summary.id, true);
    expect(deleteMock).toHaveBeenCalledWith(summary.id);
  });
});
