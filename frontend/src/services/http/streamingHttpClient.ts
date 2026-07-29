export type ServerSentEvent = {
  event: string;
  data: Record<string, unknown>;
};

export class StreamingHttpError extends Error {
  constructor(message: string, readonly retryable = true) {
    super(message);
    this.name = "StreamingHttpError";
  }
}

type PostSseOptions = {
  signal: AbortSignal;
  onEvent: (event: ServerSentEvent) => void;
};

export async function postSse(
  url: string,
  body: unknown,
  { signal, onEvent }: PostSseOptions,
): Promise<void> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new StreamingHttpError(await responseMessage(response), response.status >= 500);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = "";

  try {
    while (true) {
      const result = await reader.read();
      if (result.done) break;
      pending += decoder.decode(result.value, { stream: true });
      pending = consumeEvents(pending, onEvent);
    }
    pending += decoder.decode();
    consumeEvents(`${pending}\n\n`, onEvent);
  } finally {
    reader.releaseLock();
  }
}

function consumeEvents(source: string, onEvent: (event: ServerSentEvent) => void): string {
  const frames = source.split("\n\n");
  const incomplete = frames.pop() ?? "";
  for (const frame of frames) {
    const event = parseEvent(frame);
    if (event) onEvent(event);
  }
  return incomplete;
}

function parseEvent(frame: string): ServerSentEvent | null {
  const lines = frame.replace(/\r/g, "").split("\n");
  const event = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
  const data = lines
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trim())
    .join("\n");
  if (!event || !data) return null;

  try {
    const payload = JSON.parse(data) as unknown;
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      throw new Error("invalid payload");
    }
    return { event, data: payload as Record<string, unknown> };
  } catch {
    throw new StreamingHttpError("流式响应格式无效。", false);
  }
}

async function responseMessage(response: Response): Promise<string> {
  try {
    const payload = await response.json() as { detail?: unknown };
    if (typeof payload.detail === "string") return payload.detail;
  } catch {}
  return "流式请求失败，请稍后重试。";
}
