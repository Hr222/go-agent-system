import { describe, expect, it, vi } from "vitest";

import { axiosClient } from "../../../services/http/axiosClient";
import { cancelTask, listTaskEvents, listTasks } from "./taskApi";

vi.mock("../../../services/http/axiosClient", () => ({
  axiosClient: { get: vi.fn(), post: vi.fn() },
}));

const getMock = vi.mocked(axiosClient.get);
const postMock = vi.mocked(axiosClient.post);

describe("taskApi", () => {
  it("maps task list fields and pagination", async () => {
    getMock.mockResolvedValueOnce({ data: {
      tasks: [{
        id: "task-1", task_type: "tender.generate", owner_subject: "user-1", status: "running",
        attempt_count: 1, max_attempts: 2, available_at: "2026-09-21T00:00:00Z",
        result_summary: null, failure_code: null, created_at: "2026-09-21T00:00:00Z", updated_at: "2026-09-21T00:01:00Z",
      }], has_more: false, next_cursor: null,
    } });

    await expect(listTasks()).resolves.toEqual(expect.objectContaining({
      hasMore: false,
      tasks: [expect.objectContaining({ id: "task-1", taskType: "tender.generate" })],
    }));
    expect(getMock).toHaveBeenCalledWith("/v1/tasks", expect.objectContaining({ params: { limit: 50 } }));
  });

  it("maps event pages", async () => {
    getMock.mockResolvedValueOnce({ data: {
      events: [{ id: "event-1", sequence: 1, transition_id: "created", event_type: "TASK_CREATED", metadata: {}, created_at: "2026-09-21T00:00:00Z" }],
      has_more: false, next_after_sequence: null,
    } });

    await expect(listTaskEvents("task-1")).resolves.toEqual(expect.objectContaining({
      events: [expect.objectContaining({ transitionId: "created", eventType: "TASK_CREATED" })],
    }));
  });

  it("sends command ids for cancellation", async () => {
    postMock.mockResolvedValueOnce({ data: {
      id: "task-1", task_type: "tender.generate", owner_subject: "user-1", status: "cancel_requested",
      attempt_count: 1, max_attempts: 2, available_at: "2026-09-21T00:00:00Z",
      result_summary: null, failure_code: null, created_at: "2026-09-21T00:00:00Z", updated_at: "2026-09-21T00:01:00Z",
    } });

    await cancelTask("task-1", "cmd-1");
    expect(postMock).toHaveBeenCalledWith("/v1/tasks/task-1/cancel", { command_id: "cmd-1" });
  });
});
