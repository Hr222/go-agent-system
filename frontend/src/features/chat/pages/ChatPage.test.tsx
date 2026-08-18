import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { streamInteractionChat } from "../../interaction/api/interactionStreamApi";
import { respondToIntentProposal } from "../../interaction/api/interactionApi";
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

const streamInteractionChatMock = vi.mocked(streamInteractionChat);
const respondToIntentProposalMock = vi.mocked(respondToIntentProposal);

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
  });
}

describe("ChatPage interaction stream", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    streamInteractionChatMock.mockReset();
    respondToIntentProposalMock.mockReset();
  });

  it("renders ordinary chat from real deltas without an approval card", async () => {
    streamInteractionChatMock.mockImplementation(async (_input, handlers) => {
      handlers.onMeta?.({ requestId: "r1", model: "glm", promptVersion: "v1" });
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
      execution_result: { answer: "已执行" },
      error_code: null,
    });

    renderPage();
    fireEvent.change(screen.getByRole("textbox", { name: "发送消息" }), { target: { value: "生成投标文件" } });
    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    await screen.findByText("需要你的批准");
    expect(respondToIntentProposalMock).not.toHaveBeenCalled();
    expect(screen.queryByText("tender.generate_bid_skeleton")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "批准执行" }));
    await screen.findByText("已执行");
    expect(respondToIntentProposalMock).toHaveBeenCalledWith("proposal-1", "confirm");
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
