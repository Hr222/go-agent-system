import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { cancelTask, listTaskEvents, listTasks } from "../api/taskApi";
import { useCancelTask, useTaskEvents, useTaskList, isTaskActive } from "./useTasks";

vi.mock("../api/taskApi", async () => {
  const actual = await vi.importActual<typeof import("../api/taskApi")>("../api/taskApi");
  return { ...actual, listTasks: vi.fn(), listTaskEvents: vi.fn(), cancelTask: vi.fn() };
});

const listMock = vi.mocked(listTasks);
const eventsMock = vi.mocked(listTaskEvents);
const cancelMock = vi.mocked(cancelTask);

afterEach(() => {
  listMock.mockReset();
  eventsMock.mockReset();
  cancelMock.mockReset();
});

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const task = {
  id: "task-1", taskType: "tender.generate", ownerSubject: "user-1", status: "running" as const,
  attemptCount: 1, maxAttempts: 2, availableAt: "2026-09-21T00:00:00Z", resultSummary: null,
  failureCode: null, createdAt: "2026-09-21T00:00:00Z", updatedAt: "2026-09-21T00:01:00Z",
};

describe("task hooks", () => {
  it("polls only active tasks", async () => {
    listMock.mockResolvedValue({ tasks: [task], hasMore: false, nextCursor: null });
    const { result } = renderHook(() => useTaskList(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(isTaskActive("running")).toBe(true);
    expect(isTaskActive("succeeded")).toBe(false);
  });

  it("executes cancellation through the command hook", async () => {
    cancelMock.mockResolvedValue({ ...task, status: "cancel_requested" });
    const { result } = renderHook(() => useCancelTask(), { wrapper: createWrapper() });
    await expect(result.current.mutateAsync({ taskId: "task-1", commandId: "cmd-1" }))
      .resolves.toMatchObject({ status: "cancel_requested" });
    expect(cancelMock).toHaveBeenCalledWith("task-1", "cmd-1");
  });

  it("keeps event queries enabled for terminal tasks while disabling polling", async () => {
    eventsMock.mockResolvedValue({ events: [], hasMore: false, nextAfterSequence: null });
    const { result } = renderHook(() => useTaskEvents("task-1", false), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(eventsMock).toHaveBeenCalledOnce();
  });
});
