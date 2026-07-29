import { afterEach, describe, expect, it, vi } from "vitest";

import { postSse } from "./streamingHttpClient";

const encoder = new TextEncoder();

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("postSse", () => {
  it("解析跨分块及同一读取批次内的 SSE 事件", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(responseFor([
      "event: meta\ndata: {\"request_id\":\"r1\"}\n\nevent: heartbeat\ndata: {\"request_id\":\"r1\"}\n\nevent: del",
      "ta\ndata: {\"content\":\"你\"}\n\nevent: delta\ndata: {\"content\":\"好\"}\n\n",
    ])));
    const events: string[] = [];

    await postSse("/stream", { message: "你好" }, {
      signal: new AbortController().signal,
      onEvent: (event) => events.push(`${event.event}:${String(event.data.content ?? event.data.request_id)}`),
    });

    expect(events).toEqual(["meta:r1", "heartbeat:r1", "delta:你", "delta:好"]);
  });

  it("将 HTTP 错误转换为稳定的流式错误", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: "上游模型暂时不可用。" }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    )));

    await expect(postSse("/stream", {}, {
      signal: new AbortController().signal,
      onEvent: vi.fn(),
    })).rejects.toMatchObject({
      message: "上游模型暂时不可用。",
      retryable: true,
    });
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

    const pending = postSse("/stream", {}, { signal: abortController.signal, onEvent: vi.fn() });
    abortController.abort();

    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
    expect(fetch).toHaveBeenCalledWith("/stream", expect.objectContaining({ signal: abortController.signal }));
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
