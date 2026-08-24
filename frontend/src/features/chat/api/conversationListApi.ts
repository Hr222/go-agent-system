import { axiosClient } from "../../../services/http/axiosClient";
import { toApiError } from "../../../services/http/errorHandler";

export type ConversationSummary = {
  id: string;
  createdAt: string;
  updatedAt: string;
  topicSummary: string | null;
  isPinned: boolean;
};

export type ConversationSummaryPage = {
  conversations: ConversationSummary[];
  hasMore: boolean;
  nextCursor: string | null;
};

type ConversationSummaryPageResponse = {
  conversations: Array<{
    id: string;
    created_at: string;
    updated_at: string;
    topic_summary: string | null;
    is_pinned?: boolean;
  }>;
  has_more: boolean;
  next_cursor: string | null;
};

type ConversationResponse = {
  id: string;
  created_at: string;
  updated_at: string;
  topic_summary: string | null;
  is_pinned?: boolean;
};

export type ConversationListRequestOptions = {
  cursor?: string | null;
  signal?: AbortSignal;
};

export async function listConversationSummaries(
  { cursor, signal }: ConversationListRequestOptions = {},
): Promise<ConversationSummaryPage> {
  try {
    const response = await axiosClient.get<ConversationSummaryPageResponse>(
      "/v1/conversations",
      {
        params: {
          limit: 50,
          ...(cursor ? { cursor } : {}),
        },
        signal,
      },
    );
    return {
      conversations: response.data.conversations.map(mapConversationSummary),
      hasMore: response.data.has_more,
      nextCursor: response.data.next_cursor,
    };
  } catch (error) {
    if (signal?.aborted) throw error;
    throw toApiError(error);
  }
}

export async function createConversation(signal?: AbortSignal): Promise<ConversationSummary> {
  try {
    const response = await axiosClient.post<ConversationResponse>(
      "/v1/conversations",
      {},
      { signal },
    );
    return mapConversationSummary(response.data);
  } catch (error) {
    if (signal?.aborted) throw error;
    throw toApiError(error);
  }
}

export async function updateConversationTopicSummary(
  conversationId: string,
  topicSummary: string | null,
  signal?: AbortSignal,
): Promise<ConversationSummary> {
  try {
    const response = await axiosClient.patch<ConversationResponse>(
      `/v1/conversations/${encodeURIComponent(conversationId)}/topic-summary`,
      { topic_summary: topicSummary },
      { signal },
    );
    return mapConversationSummary(response.data);
  } catch (error) {
    if (signal?.aborted) throw error;
    throw toApiError(error);
  }
}

export async function updateConversationPin(
  conversationId: string,
  isPinned: boolean,
  signal?: AbortSignal,
): Promise<ConversationSummary> {
  try {
    const response = await axiosClient.patch<ConversationResponse>(
      `/v1/conversations/${encodeURIComponent(conversationId)}/pin`,
      { is_pinned: isPinned },
      { signal },
    );
    return mapConversationSummary(response.data);
  } catch (error) {
    if (signal?.aborted) throw error;
    throw toApiError(error);
  }
}

export async function deleteConversation(
  conversationId: string,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await axiosClient.delete(
      `/v1/conversations/${encodeURIComponent(conversationId)}`,
      { signal },
    );
  } catch (error) {
    if (signal?.aborted) throw error;
    throw toApiError(error);
  }
}

function mapConversationSummary(response: {
  id: string;
  created_at: string;
  updated_at: string;
  topic_summary?: string | null;
  is_pinned?: boolean;
}): ConversationSummary {
  return {
    id: response.id,
    createdAt: response.created_at,
    updatedAt: response.updated_at,
    topicSummary: response.topic_summary ?? null,
    isPinned: response.is_pinned ?? false,
  };
}
