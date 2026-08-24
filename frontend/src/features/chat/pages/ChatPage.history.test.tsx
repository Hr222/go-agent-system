import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ACTIVE_CONVERSATION_STORAGE_KEY,
} from "../hooks/useActiveConversation";
import { ChatPage } from "./ChatPage";

const historyState = vi.hoisted(() => ({
  value: {
    data: undefined,
    error: null,
    fetchNextPage: vi.fn(),
    hasNextPage: false,
    isError: false,
    isFetching: false,
    isFetchingNextPage: false,
    isPending: false,
    isSuccess: false,
    refetch: vi.fn(),
  } as Record<string, unknown>,
}));

vi.mock("../hooks/useConversationHistory", () => ({
  useConversationHistory: vi.fn(() => historyState.value),
}));

vi.mock("../hooks/useConversationList", () => ({
  useConversationList: vi.fn(() => ({
    data: undefined,
    fetchNextPage: vi.fn(),
    hasNextPage: false,
    isError: false,
    isFetching: false,
    isFetchingNextPage: false,
    isPending: false,
    refetch: vi.fn(),
  })),
  useCreateConversation: vi.fn(() => ({
    isPending: false,
    mutateAsync: vi.fn(),
  })),
  useDeleteConversation: vi.fn(() => ({ isPending: false, mutateAsync: vi.fn() })),
  useUpdateConversationPin: vi.fn(() => ({ isPending: false, mutateAsync: vi.fn() })),
  useUpdateConversationTopicSummary: vi.fn(() => ({
    isPending: false,
    mutateAsync: vi.fn(),
  })),
}));

const CONVERSATION_ID = "00000000-0000-4000-8000-000000000001";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ChatPage />
    </QueryClientProvider>,
  );
}

function historyPage(messages: Array<{ id: string; role: "user" | "assistant"; content: string; sequence: number }>) {
  return {
    pages: [{
      conversation: {
        id: CONVERSATION_ID,
        createdAt: "2025-01-01T00:00:00Z",
        updatedAt: "2025-01-01T00:00:00Z",
      },
      messages: messages.map((message) => ({
        ...message,
        createdAt: "2025-01-01T00:00:00Z",
      })),
      hasMore: false,
      nextAfterSequence: null,
    }],
    pageParams: [null],
  };
}

describe("ChatPage conversation history", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    window.localStorage.clear();
    historyState.value = {
      data: undefined,
      error: null,
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isError: false,
      isFetching: false,
      isFetchingNextPage: false,
      isPending: false,
      isSuccess: false,
      refetch: vi.fn(),
    };
  });

  it("restores a saved conversation and renders ordered persisted messages", async () => {
    window.localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, CONVERSATION_ID);
    historyState.value = {
      ...historyState.value,
      data: historyPage([
        { id: "message-1", role: "user", content: "持久化提问", sequence: 1 },
        { id: "message-2", role: "assistant", content: "持久化回答", sequence: 2 },
      ]),
      isSuccess: true,
    };

    renderPage();

    expect(await screen.findByText("持久化提问")).toBeTruthy();
    expect(screen.getByText("持久化回答")).toBeTruthy();
    expect(screen.queryByText("开始一段新的工作对话")).toBeNull();
  });

  it("offers a next-page control without duplicating the first page", async () => {
    window.localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, CONVERSATION_ID);
    const fetchNextPage = vi.fn();
    historyState.value = {
      ...historyState.value,
      data: historyPage([{ id: "message-1", role: "user", content: "第一页", sequence: 1 }]),
      fetchNextPage,
      hasNextPage: true,
      isSuccess: true,
    };

    renderPage();
    await screen.findByText("第一页");
    fireEvent.click(screen.getByRole("button", { name: "加载更多消息" }));

    expect(fetchNextPage).toHaveBeenCalledOnce();
    expect(screen.getAllByText("第一页")).toHaveLength(1);
  });

  it("clears an inaccessible saved conversation", async () => {
    window.localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, CONVERSATION_ID);
    historyState.value = {
      ...historyState.value,
      error: { status: 404, message: "会话不可用" },
      isError: true,
    };

    renderPage();

    await waitFor(() => expect(
      window.localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY),
    ).toBeNull());
    expect(screen.queryByText("会话不可用")).toBeNull();
  });

  it("keeps the saved conversation and exposes retry for network errors", async () => {
    window.localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, CONVERSATION_ID);
    const refetch = vi.fn();
    historyState.value = {
      ...historyState.value,
      error: { status: 503, message: "服务暂不可用" },
      isError: true,
      refetch,
    };

    renderPage();

    const retry = await screen.findByRole("button", { name: "重试加载" });
    fireEvent.click(retry);
    expect(refetch).toHaveBeenCalledOnce();
    expect(window.localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY)).toBe(CONVERSATION_ID);
  });
});
