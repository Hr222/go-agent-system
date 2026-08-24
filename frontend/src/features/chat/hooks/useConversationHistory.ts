import { useInfiniteQuery } from "@tanstack/react-query";

import {
  getConversationHistory,
  type ConversationHistoryPage,
} from "../api/conversationHistoryApi";

export function useConversationHistory(conversationId: string | null) {
  return useInfiniteQuery({
    queryKey: ["conversation-history", conversationId],
    queryFn: ({ pageParam, signal }) => getConversationHistory(conversationId as string, {
      afterSequence: pageParam,
      signal,
    }),
    enabled: conversationId !== null,
    initialPageParam: null as number | null,
    getNextPageParam: (lastPage) => lastPage.hasMore
      ? lastPage.nextAfterSequence ?? undefined
      : undefined,
    retry: false,
  });
}
