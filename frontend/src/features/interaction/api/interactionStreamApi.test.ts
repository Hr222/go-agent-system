import { afterEach, describe, expect, it, vi } from "vitest";

import { InteractionStreamError, streamInteractionChat } from "./interactionStreamApi";

const encoder = new TextEncoder();

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("streamInteractionChat", () => {
  it("sends only user input and parses ordinary chat deltas in order", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(responseFor([
      "event: meta\ndata: {\"request_id\":\"r1\",\"model\":\"glm\",\"prompt_version\":\"v1\"}\n\n",
      "event: delta\ndata: {\"content\":\"你\"}\n\nevent: delta\ndata: {\"content\":\"好\"}\n\n",
      "event: complete\ndata: {\"request_id\":\"r1\",\"model\":\"glm\",\"prompt_version\":\"v1\",\"usage\":{\"total_tokens\":2}}\n\n",
    ])));
    const events: string[] = [];

    const terminal = await streamInteractionChat("你好", {
      onMeta: (meta) => events.push("meta:" + meta.requestId),
      onDelta: (content) => events.push("delta:" + content),
      onComplete: (complete) => events.push("complete:" + complete.usage.total_tokens),
    }, new AbortController().signal);

    expect(terminal).toBe("complete");
    expect(events).toEqual(["meta:r1", "delta:你", "delta:好", "complete:2"]);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/v1/interaction/chat/stream"),
      expect.objectContaining({
        body: JSON.stringify({ user_input: "你好", provided_inputs: {} }),
      }),
    );
  });

  it("parses an approval event without exposing an internal dispatch target", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(responseFor([
      "event: approval_required\ndata: {\"proposal_id\":\"p1\",\"state\":\"pending\",\"summary\":\"生成投标骨架\",\"confirmation_prompt\":\"批准后才会执行。\"}\n\n",
    ])));
    const approvals: object[] = [];

    const terminal = await streamInteractionChat("生成投标文件", {
      onApprovalRequired: (approval) => approvals.push(approval),
    }, new AbortController().signal);

    expect(terminal).toBe("approval_required");
    expect(approvals).toEqual([{
      proposalId: "p1",
      state: "pending",
      summary: "生成投标骨架",
      confirmationPrompt: "批准后才会执行。",
    }]);
    expect(JSON.stringify(approvals)).not.toContain("dispatch_key");
  });

  it("raises a controlled error event to the caller", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(responseFor([
      "event: error\ndata: {\"code\":\"UPSTREAM_TIMEOUT\",\"message\":\"模型响应超时。\",\"retryable\":true}\n\n",
    ])));

    await expect(streamInteractionChat("你好", {}, new AbortController().signal))
      .rejects.toBeInstanceOf(InteractionStreamError);
  });
});

function responseFor(chunks: string[]): Response {
  return new Response(new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  }), { status: 200 });
}
