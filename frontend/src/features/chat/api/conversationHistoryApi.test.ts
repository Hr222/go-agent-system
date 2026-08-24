import { afterEach, describe, expect, it, vi } from "vitest";

import { axiosClient } from "../../../services/http/axiosClient";
import { getConversationHistory } from "./conversationHistoryApi";

vi.mock("../../../services/http/axiosClient", () => ({
  axiosClient: { get: vi.fn() },
}));

const getMock = vi.mocked(axiosClient.get);

afterEach(() => {
  getMock.mockReset();
});

describe("getConversationHistory", () => {
  it("maps the browser-safe history page and forwards the sequence cursor", async () => {
    getMock.mockResolvedValue({
      data: {
        conversation: {
          id: "00000000-0000-4000-8000-000000000001",
          created_at: "2025-01-01T00:00:00Z",
          updated_at: "2025-01-01T00:02:00Z",
        },
        messages: [{
          id: "00000000-0000-4000-8000-000000000002",
          role: "user",
          content: "你好",
          sequence: 3,
          created_at: "2025-01-01T00:01:00Z",
        }],
        has_more: true,
        next_after_sequence: 3,
      },
    });
    const signal = new AbortController().signal;

    await expect(getConversationHistory(
      "00000000-0000-4000-8000-000000000001",
      { afterSequence: 2, signal },
    )).resolves.toEqual({
      conversation: {
        id: "00000000-0000-4000-8000-000000000001",
        createdAt: "2025-01-01T00:00:00Z",
        updatedAt: "2025-01-01T00:02:00Z",
      },
      messages: [{
        id: "00000000-0000-4000-8000-000000000002",
        role: "user",
        content: "你好",
        sequence: 3,
        createdAt: "2025-01-01T00:01:00Z",
      }],
      hasMore: true,
      nextAfterSequence: 3,
    });
    expect(getMock).toHaveBeenCalledWith(
      "/v1/conversations/00000000-0000-4000-8000-000000000001/messages",
      expect.objectContaining({
        params: { limit: 50, after_sequence: 2 },
        signal,
      }),
    );
  });

  it("does not add a cursor parameter to the first page", async () => {
    getMock.mockResolvedValue({
      data: {
        conversation: {
          id: "00000000-0000-4000-8000-000000000001",
          created_at: "2025-01-01T00:00:00Z",
          updated_at: "2025-01-01T00:00:00Z",
        },
        messages: [],
        has_more: false,
        next_after_sequence: null,
      },
    });

    await getConversationHistory("00000000-0000-4000-8000-000000000001");

    expect(getMock.mock.calls[0]?.[1]).toEqual(expect.objectContaining({
      params: { limit: 50 },
    }));
  });
});
