import { axiosClient } from "../../../services/http/axiosClient";
import { toApiError } from "../../../services/http/errorHandler";

export type ConversationMessageRole = "system" | "user" | "assistant";

export type ConversationHistoryMessage = {
  id: string;
  role: ConversationMessageRole;
  content: string;
  sequence: number;
  createdAt: string;
};

export type ConversationHistoryPage = {
  conversation: {
    id: string;
    createdAt: string;
    updatedAt: string;
  };
  messages: ConversationHistoryMessage[];
  hasMore: boolean;
  nextAfterSequence: number | null;
};

type ConversationHistoryResponse = {
  conversation: {
    id: string;
    created_at: string;
    updated_at: string;
  };
  messages: Array<{
    id: string;
    role: ConversationMessageRole;
    content: string;
    sequence: number;
    created_at: string;
  }>;
  has_more: boolean;
  next_after_sequence: number | null;
};

export type ConversationHistoryRequestOptions = {
  afterSequence?: number | null;
  signal?: AbortSignal;
};

export async function getConversationHistory(
  conversationId: string,
  { afterSequence, signal }: ConversationHistoryRequestOptions = {},
): Promise<ConversationHistoryPage> {
  try {
    const response = await axiosClient.get<ConversationHistoryResponse>(
      `/v1/conversations/${encodeURIComponent(conversationId)}/messages`,
      {
        params: {
          limit: 50,
          ...(afterSequence === null || afterSequence === undefined
            ? {}
            : { after_sequence: afterSequence }),
        },
        signal,
      },
    );
    return mapConversationHistoryPage(response.data);
  } catch (error) {
    if (signal?.aborted) throw error;
    throw toApiError(error);
  }
}

function mapConversationHistoryPage(
  response: ConversationHistoryResponse,
): ConversationHistoryPage {
  return {
    conversation: {
      id: response.conversation.id,
      createdAt: response.conversation.created_at,
      updatedAt: response.conversation.updated_at,
    },
    messages: response.messages.map((message) => ({
      id: message.id,
      role: message.role,
      content: message.content,
      sequence: message.sequence,
      createdAt: message.created_at,
    })),
    hasMore: response.has_more,
    nextAfterSequence: response.next_after_sequence,
  };
}
