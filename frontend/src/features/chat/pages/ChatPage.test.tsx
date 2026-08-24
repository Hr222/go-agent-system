import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { streamInteractionChat } from "../../interaction/api/interactionStreamApi";
import { respondToIntentProposal } from "../../interaction/api/interactionApi";
import { uploadAttachment } from "../../attachment/api/attachmentApi";
import { ChatPage } from "./ChatPage";

vi.mock("../../interaction/api/interactionStreamApi", () => ({
  InteractionStreamError: class InteractionStreamError extends Error {
    constructor(message: string, readonly retryable = true) {
      super(message);
    }
  },
  streamInteractionChat: vi.fn(),
}));

vi.mock("../../interaction/api/interactionApi", () => ({
  respondToIntentProposal: vi.fn(),
}));

vi.mock("../../attachment/api/attachmentApi", () => ({
  AttachmentUploadError: class AttachmentUploadError extends Error {
    constructor(message: string, readonly retryable: boolean) {
      super(message);
    }
  },
  uploadAttachment: vi.fn(),
}));

vi.mock("../hooks/useConversationHistory", () => ({
  useConversationHistory: vi.fn(() => ({
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
  })),
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

const streamInteractionChatMock = vi.mocked(streamInteractionChat);
const respondToIntentProposalMock = vi.mocked(respondToIntentProposal);
const uploadAttachmentMock = vi.mocked(uploadAttachment);

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ChatPage />
    </QueryClientProvider>,
  );
}

function emitApproval(handlers: Parameters<typeof streamInteractionChat>[1]) {
  handlers.onApprovalRequired?.({
    proposalId: "proposal-1",
    state: "pending",
    summary: "生成投标骨架",
    confirmationPrompt: "批准后才会执行。",
    conversationId: "00000000-0000-0000-0000-000000000001",
  });
}

describe("ChatPage interaction stream", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    window.localStorage.clear();
    streamInteractionChatMock.mockReset();
    respondToIntentProposalMock.mockReset();
    uploadAttachmentMock.mockReset();
  });

  it("renders ordinary chat from real deltas without an approval card", async () => {
    streamInteractionChatMock.mockImplementation(async (_input, handlers) => {
      handlers.onMeta?.({
        requestId: "r1",
        conversationId: "00000000-0000-0000-0000-000000000001",
        model: "glm",
        promptVersion: "v1",
      });
      handlers.onDelta?.("你好，");
      handlers.onDelta?.("这是流式回答。");
      handlers.onComplete?.({
        requestId: "r1",
        model: "glm",
        promptVersion: "v1",
        usage: { total_tokens: 8 },
      });
      return "complete";
    });

    renderPage();
    fireEvent.change(screen.getByRole("textbox", { name: "发送消息" }), { target: { value: "你好" } });
    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    await screen.findByText("你好，这是流式回答。");
    expect(streamInteractionChatMock).toHaveBeenCalledWith(
      "你好",
      expect.objectContaining({ onDelta: expect.any(Function) }),
      expect.any(AbortSignal),
    );
    expect(screen.queryByText("需要你的批准")).toBeNull();
    expect(respondToIntentProposalMock).not.toHaveBeenCalled();
  });

  it("uses the ordinary chat meta conversation for the next request", async () => {
    streamInteractionChatMock
      .mockImplementationOnce(async (_input, handlers) => {
        handlers.onMeta?.({
          requestId: "r1",
          conversationId: "00000000-0000-0000-0000-000000000001",
          model: "glm",
          promptVersion: "v1",
        });
        handlers.onComplete?.({
          requestId: "r1",
          model: "glm",
          promptVersion: "v1",
          usage: {},
        });
        return "complete";
      })
      .mockImplementationOnce(async (_input, handlers) => {
        handlers.onMeta?.({
          requestId: "r2",
          conversationId: "00000000-0000-0000-0000-000000000001",
          model: "glm",
          promptVersion: "v1",
        });
        handlers.onComplete?.({
          requestId: "r2",
          model: "glm",
          promptVersion: "v1",
          usage: {},
        });
        return "complete";
      });

    renderPage();
    const composer = screen.getByRole("textbox", { name: "发送消息" });
    fireEvent.change(composer, { target: { value: "第一条" } });
    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));
    await waitFor(() => expect(streamInteractionChatMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.queryByRole("button", { name: "取消生成" })).toBeNull());

    fireEvent.change(composer, { target: { value: "第二条" } });
    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    await waitFor(() => expect(streamInteractionChatMock).toHaveBeenCalledWith(
      "第二条",
      expect.objectContaining({ onDelta: expect.any(Function) }),
      expect.any(AbortSignal),
      "00000000-0000-0000-0000-000000000001",
    ));
  });

  it("sends an uploaded attachment only as source_document", async () => {
    const attachmentId = "a".repeat(32);
    uploadAttachmentMock.mockResolvedValue({
      attachmentId,
      fileName: "tender.docx",
      mediaType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      sizeBytes: 4,
      sha256: "b".repeat(64),
      status: "available",
    });
    streamInteractionChatMock.mockImplementation(async (_input, handlers) => {
      handlers.onResult?.({
        status: "needs_clarification",
        message: "more input needed",
        errorCode: null,
      });
      return "result";
    });

    const { container } = renderPage();
    fireEvent.click(screen.getByRole("button", { name: "添加附件" }));
    const fileInput = container.querySelector<HTMLInputElement>('input[type="file"]');
    expect(fileInput).not.toBeNull();
    fireEvent.change(fileInput as HTMLInputElement, {
      target: {
        files: [new File(["docx"], "tender.docx", {
          type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        })],
      },
    });

    await screen.findByText("tender.docx");
    fireEvent.change(screen.getByRole("textbox", { name: "发送消息" }), {
      target: { value: "create a tender skeleton" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    await waitFor(() => expect(streamInteractionChatMock).toHaveBeenCalledWith(
      "create a tender skeleton",
      expect.objectContaining({ onDelta: expect.any(Function) }),
      expect.any(AbortSignal),
      undefined,
      { source_document: attachmentId },
    ));
    await screen.findByLabelText("附件 tender.docx");
    expect(screen.queryByRole("button", { name: "移除 tender.docx" })).toBeNull();
    expect(JSON.stringify(streamInteractionChatMock.mock.calls)).not.toContain("tender.docx");
    expect(JSON.stringify(streamInteractionChatMock.mock.calls)).not.toContain("b".repeat(64));
  });

  it("blocks sending while an attachment upload is unfinished", async () => {
    let finishUpload: (value: Awaited<ReturnType<typeof uploadAttachment>>) => void;
    uploadAttachmentMock.mockImplementation(() => new Promise((resolve) => {
      finishUpload = resolve;
    }));

    const { container } = renderPage();
    fireEvent.change(screen.getByRole("textbox", { name: "发送消息" }), {
      target: { value: "create a tender skeleton" },
    });
    const sendButton = screen.getByRole<HTMLButtonElement>("button", { name: "发送消息" });
    expect(sendButton.disabled).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "添加附件" }));
    const fileInput = container.querySelector<HTMLInputElement>('input[type="file"]');
    fireEvent.change(fileInput as HTMLInputElement, {
      target: {
        files: [new File(["docx"], "tender.docx", {
          type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        })],
      },
    });

    await waitFor(() => expect(screen.queryByRole("button", { name: "发送消息" })).toBeNull());
    expect(streamInteractionChatMock).not.toHaveBeenCalled();

    finishUpload!({
      attachmentId: "a".repeat(32),
      fileName: "tender.docx",
      mediaType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      sizeBytes: 4,
      sha256: "b".repeat(64),
      status: "available",
    });
    await waitFor(() => expect(
      screen.getByRole<HTMLButtonElement>("button", { name: "发送消息" }).disabled,
    ).toBe(false));
  });

  it("keeps a capability request behind the inline approval card", async () => {
    streamInteractionChatMock.mockImplementation(async (_input, handlers) => {
      emitApproval(handlers);
      return "approval_required";
    });
    respondToIntentProposalMock.mockResolvedValue({
      status: "completed",
      message: "请求已完成。",
      assessment: null,
      proposal: null,
      execution_result: {
        answer: "投标骨架已经生成。",
        agent_result: {
          artifact: {
            file_name: "投标骨架.docx",
            media_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size: 42,
            resource_id: "a".repeat(32),
          },
        },
      },
      error_code: null,
    });

    renderPage();
    fireEvent.change(screen.getByRole("textbox", { name: "发送消息" }), { target: { value: "生成投标文件" } });
    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    await screen.findByText("需要你的批准");
    expect(respondToIntentProposalMock).not.toHaveBeenCalled();
    expect(screen.queryByText("tender.generate_bid_skeleton")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "批准执行" }));
    await screen.findByText("投标骨架已经生成。");
    await screen.findByText("投标骨架.docx");
    expect(respondToIntentProposalMock).toHaveBeenCalledWith("proposal-1", "confirm");
    const downloadLink = screen.getByRole<HTMLAnchorElement>("link", { name: "下载文件" });
    expect(downloadLink.getAttribute("href")).toBe(
      "/api/v1/attachments/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/download?conversation_id=00000000-0000-0000-0000-000000000001",
    );
  });

  it("submits cancellation from the same approval card", async () => {
    streamInteractionChatMock.mockImplementation(async (_input, handlers) => {
      emitApproval(handlers);
      return "approval_required";
    });
    respondToIntentProposalMock.mockResolvedValue({
      status: "cancelled",
      message: "已取消该请求，未执行任何操作。",
      assessment: null,
      proposal: null,
      execution_result: null,
      error_code: null,
    });

    renderPage();
    fireEvent.change(screen.getByRole("textbox", { name: "发送消息" }), { target: { value: "先不要执行" } });
    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));
    await screen.findByText("需要你的批准");

    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    await screen.findByText("已取消该请求，未执行任何操作。");
    expect(respondToIntentProposalMock).toHaveBeenCalledWith("proposal-1", "cancel");
  });

  it("offers explicit retry after a stream failure without resubmitting automatically", async () => {
    streamInteractionChatMock.mockRejectedValueOnce(new Error("上游模型暂时不可用。"));

    renderPage();
    fireEvent.change(screen.getByRole("textbox", { name: "发送消息" }), { target: { value: "失败测试" } });
    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    await screen.findByText("上游模型暂时不可用。");
    expect(streamInteractionChatMock).toHaveBeenCalledTimes(1);

    streamInteractionChatMock.mockImplementationOnce(async (_input, handlers) => {
      handlers.onResult?.({
        status: "needs_clarification",
        message: "请补充完成这项请求所需的信息。",
        errorCode: "INPUT_VALIDATION_FAILED",
      });
      return "result";
    });
    fireEvent.click(screen.getByRole("button", { name: "再次尝试" }));

    await screen.findByText("请补充完成这项请求所需的信息。");
    await waitFor(() => expect(streamInteractionChatMock).toHaveBeenCalledTimes(2));
  });
});
