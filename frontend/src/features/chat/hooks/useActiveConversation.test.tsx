import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import {
  ACTIVE_CONVERSATION_STORAGE_KEY,
  useActiveConversation,
} from "./useActiveConversation";

const CONVERSATION_ID = "00000000-0000-4000-8000-000000000001";

describe("useActiveConversation", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.history.replaceState({}, "", "/chat");
  });

  it("restores and saves a valid conversation id", () => {
    window.localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, CONVERSATION_ID);

    const { result } = renderHook(() => useActiveConversation());
    expect(result.current.activeConversation).toBe(CONVERSATION_ID);

    const nextId = "00000000-0000-4000-8000-000000000002";
    act(() => result.current.setActiveConversation(nextId));
    expect(result.current.activeConversation).toBe(nextId);
    expect(window.localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY)).toBe(nextId);
  });

  it("ignores and removes an invalid stored value", () => {
    window.localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, "not-a-uuid");

    const { result } = renderHook(() => useActiveConversation());
    expect(result.current.activeConversation).toBeNull();
    expect(window.localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY)).toBeNull();

    act(() => result.current.setActiveConversation("also-invalid"));
    expect(result.current.activeConversation).toBeNull();
  });

  it("treats an empty stored value as no active conversation", () => {
    window.localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, "");

    const { result } = renderHook(() => useActiveConversation());
    expect(result.current.activeConversation).toBeNull();
    expect(window.localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY)).toBeNull();
  });

  it("clears the current id and persisted value", () => {
    const { result } = renderHook(() => useActiveConversation());
    act(() => result.current.setActiveConversation(CONVERSATION_ID));
    act(() => result.current.clearActiveConversation());

    expect(result.current.activeConversation).toBeNull();
    expect(window.localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY)).toBeNull();
  });
});
