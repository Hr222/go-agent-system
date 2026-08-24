import { useCallback, useState } from "react";

export const ACTIVE_CONVERSATION_STORAGE_KEY = "chat.active-conversation.v1";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isConversationId(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

function readStoredConversationId(): string | null {
  try {
    const value = window.localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY);
    if (value !== null && isConversationId(value)) return value;
    if (value !== null) window.localStorage.removeItem(ACTIVE_CONVERSATION_STORAGE_KEY);
  } catch {
    // Storage can be unavailable in private browsing or non-browser rendering.
  }
  return null;
}

function persistConversationId(value: string | null): void {
  try {
    if (value === null) {
      window.localStorage.removeItem(ACTIVE_CONVERSATION_STORAGE_KEY);
    } else {
      window.localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, value);
    }
  } catch {
    // The in-memory state remains usable when browser storage is unavailable.
  }
}

export function useActiveConversation() {
  const [activeConversation, setActiveConversationState] = useState<string | null>(
    () => readStoredConversationId(),
  );

  const clearActiveConversation = useCallback(() => {
    persistConversationId(null);
    setActiveConversationState(null);
  }, []);

  const setActiveConversation = useCallback((conversationId: string | null | undefined) => {
    if (!isConversationId(conversationId)) {
      clearActiveConversation();
      return;
    }
    persistConversationId(conversationId);
    setActiveConversationState(conversationId);
  }, [clearActiveConversation]);

  return {
    activeConversation,
    setActiveConversation,
    clearActiveConversation,
  };
}
