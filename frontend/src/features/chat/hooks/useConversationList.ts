import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import {
  createConversation,
  deleteConversation,
  listConversationSummaries,
  updateConversationPin,
  updateConversationTopicSummary,
} from "../api/conversationListApi";
import type { ConversationSummary } from "../api/conversationListApi";

const conversationListQueryKey = ["conversation-list"] as const;

export function useConversationList() {
  return useInfiniteQuery({
    queryKey: conversationListQueryKey,
    queryFn: ({ pageParam, signal }) => listConversationSummaries({
      cursor: pageParam,
      signal,
    }),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.hasMore
      ? lastPage.nextCursor ?? undefined
      : undefined,
    retry: false,
  });
}

export function useCreateConversation() {
  const queryClient = useQueryClient();
  return useMutation<ConversationSummary, unknown, void>({
    mutationFn: () => createConversation(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: conversationListQueryKey });
    },
  });
}

export function useUpdateConversationTopicSummary() {
  const queryClient = useQueryClient();
  return useMutation<ConversationSummary, unknown, { conversationId: string; topicSummary: string | null }>({
    mutationFn: ({ conversationId, topicSummary }) => updateConversationTopicSummary(
      conversationId,
      topicSummary,
    ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: conversationListQueryKey });
    },
  });
}

export function useUpdateConversationPin() {
  const queryClient = useQueryClient();
  return useMutation<ConversationSummary, unknown, { conversationId: string; isPinned: boolean }>({
    mutationFn: ({ conversationId, isPinned }) => updateConversationPin(conversationId, isPinned),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: conversationListQueryKey });
    },
  });
}

export function useDeleteConversation() {
  const queryClient = useQueryClient();
  return useMutation<void, unknown, string>({
    mutationFn: (conversationId) => deleteConversation(conversationId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: conversationListQueryKey });
    },
  });
}
