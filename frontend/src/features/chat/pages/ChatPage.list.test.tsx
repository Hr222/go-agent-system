import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ACTIVE_CONVERSATION_STORAGE_KEY } from "../hooks/useActiveConversation";
import { ChatPage } from "./ChatPage";

const mocks = vi.hoisted(() => ({
  useConversationHistory: vi.fn(),
  useConversationList: vi.fn(),
  useCreateConversation: vi.fn(),
  useDeleteConversation: vi.fn(),
  useUpdateConversationPin: vi.fn(),
  useUpdateConversationTopicSummary: vi.fn(),
  messageError: vi.fn(),
}));

vi.mock("antd", () => ({
  message: {
    error: mocks.messageError,
  },
}));

vi.mock("../hooks/useConversationHistory", () => ({
  useConversationHistory: mocks.useConversationHistory,
}));

vi.mock("../hooks/useConversationList", () => ({
  useConversationList: mocks.useConversationList,
  useCreateConversation: mocks.useCreateConversation,
  useDeleteConversation: mocks.useDeleteConversation,
  useUpdateConversationPin: mocks.useUpdateConversationPin,
  useUpdateConversationTopicSummary: mocks.useUpdateConversationTopicSummary,
}));

const FIRST_ID = "00000000-0000-4000-8000-000000000001";
const SECOND_ID = "00000000-0000-4000-8000-000000000002";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ChatPage />
    </QueryClientProvider>,
  );
}

function summary(id: string, createdAt: string, topicSummary: string | null = null) {
  return {
    id,
    createdAt,
    updatedAt: createdAt,
    topicSummary,
    isPinned: false,
  };
}

function listState(conversations: ReturnType<typeof summary>[], overrides: Record<string, unknown> = {}) {
  return {
    data: {
      pages: [{ conversations, hasMore: false, nextCursor: null }],
      pageParams: [null],
    },
    fetchNextPage: vi.fn(),
    hasNextPage: false,
    isError: false,
    isFetching: false,
    isFetchingNextPage: false,
    isPending: false,
    refetch: vi.fn(),
    ...overrides,
  };
}

const emptyHistoryState = {
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

describe("ChatPage conversation list", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    window.localStorage.clear();
    mocks.useConversationHistory.mockReset();
    mocks.useConversationList.mockReset();
    mocks.useCreateConversation.mockReset();
    mocks.useDeleteConversation.mockReset();
    mocks.useUpdateConversationPin.mockReset();
    mocks.useUpdateConversationTopicSummary.mockReset();
    mocks.messageError.mockReset();
    mocks.useConversationHistory.mockReturnValue(emptyHistoryState);
    mocks.useConversationList.mockReturnValue(listState([]));
    mocks.useCreateConversation.mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn(),
    });
    mocks.useDeleteConversation.mockReturnValue({ isPending: false, mutateAsync: vi.fn() });
    mocks.useUpdateConversationPin.mockReturnValue({ isPending: false, mutateAsync: vi.fn() });
    mocks.useUpdateConversationTopicSummary.mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn(),
    });
  });

  it("renders server summaries in their returned order", () => {
    mocks.useConversationList.mockReturnValue(listState([
      summary(FIRST_ID, "2025-01-01T00:00:00Z"),
      summary(SECOND_ID, "2025-01-02T00:00:00Z"),
    ]));

    renderPage();

    const first = screen.getByText("会话 1/1");
    const second = screen.getByText("会话 1/2");
    expect(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("prefers the topic summary and saves edits for the active conversation", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(summary(FIRST_ID, "2025-01-01T00:00:00Z"));
    mocks.useConversationList.mockReturnValue(listState([
      { ...summary(FIRST_ID, "2025-01-01T00:00:00Z"), topicSummary: "首轮自动概括" },
    ]));
    mocks.useUpdateConversationTopicSummary.mockReturnValue({ isPending: false, mutateAsync });
    window.localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, FIRST_ID);

    renderPage();

    expect(screen.getByText("首轮自动概括")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "会话操作：首轮自动概括" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "重命名" }));
    const editor = screen.getByRole("textbox", { name: "会话名称" });
    fireEvent.change(editor, { target: { value: "人工修正主题" } });
    fireEvent.click(screen.getByRole("button", { name: "保存会话名称" }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith({
      conversationId: FIRST_ID,
      topicSummary: "人工修正主题",
    }));
  });

  it("keeps the rename draft when saving fails", async () => {
    const mutateAsync = vi.fn().mockRejectedValue(new Error("保存失败"));
    mocks.useConversationList.mockReturnValue(listState([
      { ...summary(FIRST_ID, "2025-01-01T00:00:00Z"), topicSummary: "保留这个草稿" },
    ]));
    mocks.useUpdateConversationTopicSummary.mockReturnValue({ isPending: false, mutateAsync });
    window.localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, FIRST_ID);

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "会话操作：保留这个草稿" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "重命名" }));
    fireEvent.change(screen.getByRole("textbox", { name: "会话名称" }), { target: { value: "新的会话名称" } });
    fireEvent.click(screen.getByRole("button", { name: "保存会话名称" }));

    await waitFor(() => expect(
      (screen.getByRole("textbox", { name: "会话名称" }) as HTMLInputElement).value,
    ).toBe("新的会话名称"));
    expect(screen.getByRole("alert").textContent).toContain("保存失败");
  });

  it("clears a conversation name when the rename draft is blank", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(summary(FIRST_ID, "2025-01-01T00:00:00Z"));
    mocks.useConversationList.mockReturnValue(listState([
      { ...summary(FIRST_ID, "2025-01-01T00:00:00Z"), topicSummary: "可清除名称" },
    ]));
    mocks.useUpdateConversationTopicSummary.mockReturnValue({ isPending: false, mutateAsync });

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "会话操作：可清除名称" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "重命名" }));
    fireEvent.change(screen.getByRole("textbox", { name: "会话名称" }), { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: "保存会话名称" }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith({
      conversationId: FIRST_ID,
      topicSummary: null,
    }));
  });

  it("shows an empty state while keeping new conversation available", () => {
    renderPage();

    expect(screen.getByText("暂无历史会话")).toBeTruthy();
    expect(screen.getByRole("button", { name: /新建对话/ })).toBeTruthy();
  });

  it("offers a retry when the summary list fails", () => {
    const refetch = vi.fn();
    mocks.useConversationList.mockReturnValue(listState([], {
      data: undefined,
      isError: true,
      refetch,
    }));

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "重试" }));

    expect(refetch).toHaveBeenCalledOnce();
  });

  it("selects a server summary and lets the history hook load it", async () => {
    mocks.useConversationList.mockReturnValue(listState([
      summary(FIRST_ID, "2025-01-01T00:00:00Z"),
    ]));

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "会话 1/1 更新于 1/1" }));

    await waitFor(() => expect(
      window.localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY),
    ).toBe(FIRST_ID));
    expect(mocks.useConversationHistory).toHaveBeenCalledWith(FIRST_ID);
  });

  it("creates on the server, selects the returned id and refreshes the list", async () => {
    const refetch = vi.fn().mockResolvedValue(undefined);
    const mutateAsync = vi.fn().mockResolvedValue(summary(SECOND_ID, "2025-01-03T00:00:00Z"));
    mocks.useConversationList.mockReturnValue(listState([], { refetch }));
    mocks.useCreateConversation.mockReturnValue({ isPending: false, mutateAsync });

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /新建对话/ }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledOnce());
    expect(window.localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY)).toBe(SECOND_ID);
    expect(refetch).toHaveBeenCalledOnce();
  });

  it("requires confirmation before deleting a conversation", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(undefined);
    mocks.useConversationList.mockReturnValue(listState([
      summary(FIRST_ID, "2025-01-01T00:00:00Z", "待删除会话"),
    ]));
    mocks.useDeleteConversation.mockReturnValue({ isPending: false, mutateAsync });

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "会话操作：待删除会话" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "删除" }));

    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(mutateAsync).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(mutateAsync).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "会话操作：待删除会话" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "删除" }));
    fireEvent.click(screen.getByRole("button", { name: "确认删除" }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith(FIRST_ID));
  });

  it("clears the active conversation after deleting it", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(undefined);
    const refetch = vi.fn().mockResolvedValue(undefined);
    mocks.useConversationList.mockReturnValue(listState([
      summary(FIRST_ID, "2025-01-01T00:00:00Z", "当前会话"),
    ], { refetch }));
    mocks.useDeleteConversation.mockReturnValue({ isPending: false, mutateAsync });
    window.localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, FIRST_ID);

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "会话操作：当前会话" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "删除" }));
    fireEvent.click(screen.getByRole("button", { name: "确认删除" }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith(FIRST_ID));
    expect(window.localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY)).toBeNull();
    expect(refetch).toHaveBeenCalledOnce();
    expect(screen.getByRole("status").textContent).toContain("会话已删除");
  });

  it("retains the conversation and shows an error when deletion fails", async () => {
    const mutateAsync = vi.fn().mockRejectedValue(new Error("删除失败"));
    mocks.useConversationList.mockReturnValue(listState([
      summary(FIRST_ID, "2025-01-01T00:00:00Z", "删除失败会话"),
    ]));
    mocks.useDeleteConversation.mockReturnValue({ isPending: false, mutateAsync });

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "会话操作：删除失败会话" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "删除" }));
    fireEvent.click(screen.getByRole("button", { name: "确认删除" }));

    await waitFor(() => expect(mocks.messageError).toHaveBeenCalledWith("会话删除失败，请重试。"));
    expect(screen.getByText("删除失败会话")).toBeTruthy();
  });

  it("closes an open conversation menu when clicking outside", () => {
    mocks.useConversationList.mockReturnValue(listState([
      summary(FIRST_ID, "2025-01-01T00:00:00Z", "菜单测试"),
    ]));

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "会话操作：菜单测试" }));
    expect(screen.getByRole("menu")).toBeTruthy();

    fireEvent.pointerDown(document.body);

    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("keeps the share action as an inert placeholder", () => {
    mocks.useConversationList.mockReturnValue(listState([
      summary(FIRST_ID, "2025-01-01T00:00:00Z", "分享测试"),
    ]));

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "会话操作：分享测试" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "分享" }));

    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.getByRole("menu")).toBeTruthy();
  });
});
