import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatStreamError, streamChatMessage } from "./chatStreamApi";

const encoder = new TextEncoder();

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("streamChatMessage", () => {
  it("解析跨分块的 SSE 并按顺序交付增量", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(responseFor([
      "event: meta\ndata: {\"request_id\":\"r1\",\"model\":\"glm\",\"prompt_version\":\"v1\"}\n\n",
      "event: delta\ndata: {\"content\":\"你\"}\n\nevent: delta\ndata: {\"content\":\"好\"}",
      "\n\nevent: complete\ndata: {\"request_id\":\"r1\",\"model\":\"glm\",\"prompt_version\":\"v1\",\"usage\":{\"total_tokens\":2}}\n\n",
    ])));
    const events: string[] = [];

    await streamChatMessage("你好", {
      onMeta: (meta) => events.push(`meta:${meta.requestId}`),
      onDelta: (content) => events.push(`delta:${content}`),
      onComplete: (result) => events.push(`complete:${result.usage.total_tokens}`),
    }, new AbortController().signal);

    expect(events).toEqual(["meta:r1", "delta:你", "delta:好", "complete:2"]);
  });

  it("将服务端 SSE 错误显式传递给调用方", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(responseFor([
      "event: error\ndata: {\"message\":\"上游失败\",\"retryable\":true}\n\n",
    ])));

    await expect(streamChatMessage("你好", {}, new AbortController().signal))
      .rejects.toMatchObject({ message: "上游失败", retryable: true });
  });

  it("将 AbortSignal 传递给 fetch 并中断读取", async () => {
    const abortController = new AbortController();
    vi.stubGlobal("fetch", vi.fn().mockImplementation((_url, init: RequestInit) => {
      const body = new ReadableStream<Uint8Array>({
        start(controller) {
          init.signal?.addEventListener("abort", () => controller.error(new DOMException("Aborted", "AbortError")));
        },
      });
      return Promise.resolve(new Response(body, { status: 200 }));
    }));

    const pending = streamChatMessage("你好", {}, abortController.signal);
    abortController.abort();

    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
    expect(fetch).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ signal: abortController.signal }));
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
