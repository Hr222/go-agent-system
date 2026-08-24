import { afterEach, describe, expect, it, vi } from "vitest";

import { axiosClient } from "../../../services/http/axiosClient";
import {
  createConversation,
  deleteConversation,
  listConversationSummaries,
  updateConversationPin,
  updateConversationTopicSummary,
} from "./conversationListApi";

vi.mock("../../../services/http/axiosClient", () => ({
  axiosClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

const getMock = vi.mocked(axiosClient.get);
const postMock = vi.mocked(axiosClient.post);
const patchMock = vi.mocked(axiosClient.patch);
const deleteMock = vi.mocked(axiosClient.delete);

afterEach(() => {
  getMock.mockReset();
  postMock.mockReset();
  patchMock.mockReset();
  deleteMock.mockReset();
});

describe("conversation list API", () => {
  it("maps summaries and forwards the opaque cursor", async () => {
    getMock.mockResolvedValue({
      data: {
        conversations: [{
          id: "00000000-0000-4000-8000-000000000001",
          created_at: "2025-01-01T00:00:00Z",
          updated_at: "2025-01-02T00:00:00Z",
          topic_summary: "知识库检索",
          is_pinned: true,
        }],
        has_more: true,
        next_cursor: "opaque-cursor",
      },
    });
    const signal = new AbortController().signal;

    await expect(listConversationSummaries({ cursor: "previous", signal })).resolves.toEqual({
      conversations: [{
        id: "00000000-0000-4000-8000-000000000001",
        createdAt: "2025-01-01T00:00:00Z",
        updatedAt: "2025-01-02T00:00:00Z",
        topicSummary: "知识库检索",
        isPinned: true,
      }],
      hasMore: true,
      nextCursor: "opaque-cursor",
    });
    expect(getMock).toHaveBeenCalledWith(
      "/v1/conversations",
      expect.objectContaining({
        params: { limit: 50, cursor: "previous" },
        signal,
      }),
    );
  });

  it("creates a server-owned conversation without a client UUID", async () => {
    postMock.mockResolvedValue({
      data: {
        id: "00000000-0000-4000-8000-000000000002",
        created_at: "2025-01-03T00:00:00Z",
        updated_at: "2025-01-03T00:00:00Z",
          topic_summary: null,
          is_pinned: false,
      },
    });

    await expect(createConversation()).resolves.toEqual({
      id: "00000000-0000-4000-8000-000000000002",
      createdAt: "2025-01-03T00:00:00Z",
      updatedAt: "2025-01-03T00:00:00Z",
      topicSummary: null,
      isPinned: false,
    });
    expect(postMock).toHaveBeenCalledWith(
      "/v1/conversations",
      {},
      expect.objectContaining({ signal: undefined }),
    );
  });

  it("updates and clears a topic summary through the owner-scoped endpoint", async () => {
    patchMock.mockResolvedValue({
      data: {
        id: "00000000-0000-4000-8000-000000000003",
        created_at: "2025-01-03T00:00:00Z",
        updated_at: "2025-01-03T00:00:00Z",
          topic_summary: null,
          is_pinned: false,
      },
    });

    await expect(updateConversationTopicSummary("conversation/1", null)).resolves.toMatchObject({
      id: "00000000-0000-4000-8000-000000000003",
      topicSummary: null,
      isPinned: false,
    });
    expect(patchMock).toHaveBeenCalledWith(
      "/v1/conversations/conversation%2F1/topic-summary",
      { topic_summary: null },
      { signal: undefined },
    );
  });

  it("updates pin state and deletes a conversation", async () => {
    patchMock.mockResolvedValue({
      data: {
        id: "00000000-0000-4000-8000-000000000004",
        created_at: "2025-01-03T00:00:00Z",
        updated_at: "2025-01-03T00:00:00Z",
        topic_summary: null,
        is_pinned: true,
      },
    });
    deleteMock.mockResolvedValue({ status: 204 });

    await expect(updateConversationPin("conversation/1", true)).resolves.toMatchObject({
      isPinned: true,
    });
    await expect(deleteConversation("conversation/1")).resolves.toBeUndefined();
    expect(patchMock).toHaveBeenCalledWith(
      "/v1/conversations/conversation%2F1/pin",
      { is_pinned: true },
      { signal: undefined },
    );
    expect(deleteMock).toHaveBeenCalledWith(
      "/v1/conversations/conversation%2F1",
      { signal: undefined },
    );
  });
});
