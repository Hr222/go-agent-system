import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { recognizeIntent, respondToIntentProposal } from "../api/interactionApi";
import { InteractionPage } from "./InteractionPage";

vi.mock("../api/interactionApi", () => ({
  recognizeIntent: vi.fn(),
  respondToIntentProposal: vi.fn(),
}));

const recognizeIntentMock = vi.mocked(recognizeIntent);
const respondToIntentProposalMock = vi.mocked(respondToIntentProposal);

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <InteractionPage />
    </QueryClientProvider>,
  );
}

describe("InteractionPage", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    recognizeIntentMock.mockReset();
    respondToIntentProposalMock.mockReset();
  });

  it("renders a pending proposal without dispatching until explicit confirmation", async () => {
    recognizeIntentMock.mockResolvedValue({
      status: "pending",
      message: "等待确认。",
      assessment: {
        status: "matched",
        capability_code: "chat.general",
        missing_fields: [],
        clarification: null,
        confidence: 0.93,
        error_code: null,
      },
      proposal: {
        proposal_id: "proposal-1",
        state: "pending",
        capability_code: "chat.general",
        summary: "chat.general: 通用对话",
        confirmation_prompt: "确认执行吗？",
      },
      execution_result: null,
      error_code: null,
    });
    respondToIntentProposalMock.mockResolvedValue({
      status: "completed",
      message: "目标能力已完成执行。",
      assessment: null,
      proposal: null,
      execution_result: { answer: "已执行" },
      error_code: null,
    });

    renderPage();
    fireEvent.change(screen.getByLabelText("请求内容"), {
      target: { value: "帮我回答一个问题" },
    });
    fireEvent.click(screen.getByRole("button", { name: "识别请求" }));

    await screen.findByText("等待确认。")
    expect(respondToIntentProposalMock).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "确认执行" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "确认执行" }));

    await waitFor(() => {
      expect(respondToIntentProposalMock).toHaveBeenCalledWith("proposal-1", "confirm");
    });
    await screen.findByText("目标能力已完成执行。")
    expect(screen.getByText("已完成")).toBeTruthy();
  });

  it("allows a pending proposal to be cancelled without sending confirmation", async () => {
    recognizeIntentMock.mockResolvedValue({
      status: "pending",
      message: "等待确认。",
      assessment: null,
      proposal: {
        proposal_id: "proposal-cancel",
        state: "pending",
        capability_code: "chat.general",
        summary: "通用对话",
        confirmation_prompt: "确认执行吗？",
      },
      execution_result: null,
      error_code: null,
    });
    respondToIntentProposalMock.mockResolvedValue({
      status: "cancelled",
      message: "已取消待执行能力。",
      assessment: null,
      proposal: null,
      execution_result: null,
      error_code: null,
    });

    renderPage();
    fireEvent.change(screen.getByLabelText("请求内容"), {
      target: { value: "先不要执行" },
    });
    fireEvent.click(screen.getByRole("button", { name: "识别请求" }));
    await screen.findByText("等待确认。");

    fireEvent.click(screen.getByRole("button", { name: "取消" }));

    await waitFor(() => {
      expect(respondToIntentProposalMock).toHaveBeenCalledWith("proposal-cancel", "cancel");
    });
    await screen.findByText("已取消待执行能力。");
    expect(screen.getByText("已取消")).toBeTruthy();
  });

  it("shows recognition errors without attempting a confirmation", async () => {
    recognizeIntentMock.mockRejectedValue(new Error("识别服务暂时不可用"));

    renderPage();
    fireEvent.change(screen.getByLabelText("请求内容"), {
      target: { value: "帮我处理一件事" },
    });
    fireEvent.click(screen.getByRole("button", { name: "识别请求" }));

    await screen.findByText("识别服务暂时不可用");
    expect(respondToIntentProposalMock).not.toHaveBeenCalled();
  });

  it("shows a controlled dispatch failure after confirmation", async () => {
    recognizeIntentMock.mockResolvedValue({
      status: "pending",
      message: "等待确认。",
      assessment: null,
      proposal: {
        proposal_id: "proposal-failed",
        state: "pending",
        capability_code: "chat.general",
        summary: "通用对话",
        confirmation_prompt: "确认执行吗？",
      },
      execution_result: null,
      error_code: null,
    });
    respondToIntentProposalMock.mockResolvedValue({
      status: "failed",
      message: "目标能力执行失败。",
      assessment: null,
      proposal: null,
      execution_result: null,
      error_code: "DISPATCH_EXECUTION_FAILED",
    });

    renderPage();
    fireEvent.change(screen.getByLabelText("请求内容"), {
      target: { value: "执行可能失败的请求" },
    });
    fireEvent.click(screen.getByRole("button", { name: "识别请求" }));
    await screen.findByText("等待确认。");

    fireEvent.click(screen.getByRole("button", { name: "确认执行" }));

    await screen.findByText("目标能力执行失败。");
    expect(screen.getByText("执行失败")).toBeTruthy();
    expect(respondToIntentProposalMock).toHaveBeenCalledTimes(1);
  });
});
