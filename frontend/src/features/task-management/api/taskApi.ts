import { axiosClient } from "../../../services/http/axiosClient";
import { toApiError } from "../../../services/http/errorHandler";

export type TaskStatus =
  | "queued"
  | "running"
  | "retry_wait"
  | "cancel_requested"
  | "succeeded"
  | "failed"
  | "cancelled";

export type Task = {
  id: string;
  taskType: string;
  ownerSubject: string;
  status: TaskStatus;
  attemptCount: number;
  maxAttempts: number;
  availableAt: string;
  resultSummary: string | null;
  failureCode: string | null;
  createdAt: string;
  updatedAt: string;
};

export type TaskEvent = {
  id: string;
  sequence: number;
  transitionId: string;
  eventType: string;
  metadata: Record<string, string | number>;
  createdAt: string;
};

export type TaskPage = {
  tasks: Task[];
  hasMore: boolean;
  nextCursor: string | null;
};

export type TaskEventPage = {
  events: TaskEvent[];
  hasMore: boolean;
  nextAfterSequence: number | null;
};

export type TaskResultResource = {
  resourceId: string;
  fileName: string;
  mediaType: string;
  sizeBytes: number;
  sha256: string;
  downloadUrl: string;
};

type TaskResponse = {
  id: string;
  task_type: string;
  owner_subject: string;
  status: TaskStatus;
  attempt_count: number;
  max_attempts: number;
  available_at: string;
  result_summary: string | null;
  failure_code: string | null;
  created_at: string;
  updated_at: string;
};

type TaskPageResponse = {
  tasks: TaskResponse[];
  has_more: boolean;
  next_cursor: string | null;
};

type TaskEventResponse = {
  id: string;
  sequence: number;
  transition_id: string;
  event_type: string;
  metadata: Record<string, string | number>;
  created_at: string;
};

type TaskEventPageResponse = {
  events: TaskEventResponse[];
  has_more: boolean;
  next_after_sequence: number | null;
};

type TaskResultResourceListResponse = {
  task_id: string;
  resources: Array<{
    resource_id: string;
    file_name: string;
    media_type: string;
    size_bytes: number;
    sha256: string;
    download_url: string;
  }>;
};

type TaskCommandResponse = TaskResponse;

export type TaskListOptions = {
  cursor?: string | null;
  signal?: AbortSignal;
};

export type TaskEventsOptions = {
  afterSequence?: number | null;
  signal?: AbortSignal;
};

export async function listTasks({ cursor, signal }: TaskListOptions = {}): Promise<TaskPage> {
  try {
    const response = await axiosClient.get<TaskPageResponse>("/v1/tasks", {
      params: { limit: 50, ...(cursor ? { cursor } : {}) },
      signal,
    });
    return {
      tasks: response.data.tasks.map(mapTask),
      hasMore: response.data.has_more,
      nextCursor: response.data.next_cursor,
    };
  } catch (error) {
    if (signal?.aborted) throw error;
    throw toApiError(error);
  }
}

export async function getTask(taskId: string, signal?: AbortSignal): Promise<Task> {
  try {
    const response = await axiosClient.get<TaskResponse>(
      `/v1/tasks/${encodeURIComponent(taskId)}`,
      { signal },
    );
    return mapTask(response.data);
  } catch (error) {
    if (signal?.aborted) throw error;
    throw toApiError(error);
  }
}

export async function listTaskEvents(
  taskId: string,
  { afterSequence, signal }: TaskEventsOptions = {},
): Promise<TaskEventPage> {
  try {
    const response = await axiosClient.get<TaskEventPageResponse>(
      `/v1/tasks/${encodeURIComponent(taskId)}/events`,
      {
        params: { limit: 200, ...(afterSequence ? { after_sequence: afterSequence } : {}) },
        signal,
      },
    );
    return {
      events: response.data.events.map(mapTaskEvent),
      hasMore: response.data.has_more,
      nextAfterSequence: response.data.next_after_sequence,
    };
  } catch (error) {
    if (signal?.aborted) throw error;
    throw toApiError(error);
  }
}

export async function cancelTask(taskId: string, commandId: string): Promise<Task> {
  return commandTask(taskId, "cancel", commandId);
}

export async function listTaskResources(taskId: string, signal?: AbortSignal): Promise<TaskResultResource[]> {
  try {
    const response = await axiosClient.get<TaskResultResourceListResponse>(
      `/v1/tasks/${encodeURIComponent(taskId)}/resources`,
      { signal },
    );
    return response.data.resources.map((resource) => ({
      resourceId: resource.resource_id,
      fileName: resource.file_name,
      mediaType: resource.media_type,
      sizeBytes: resource.size_bytes,
      sha256: resource.sha256,
      downloadUrl: resource.download_url,
    }));
  } catch (error) {
    if (signal?.aborted) throw error;
    throw toApiError(error);
  }
}

export async function retryTask(taskId: string, commandId: string): Promise<Task> {
  return commandTask(taskId, "retry", commandId);
}

async function commandTask(
  taskId: string,
  command: "cancel" | "retry",
  commandId: string,
): Promise<Task> {
  try {
    const response = await axiosClient.post<TaskCommandResponse>(
      `/v1/tasks/${encodeURIComponent(taskId)}/${command}`,
      { command_id: commandId },
    );
    return mapTask(response.data);
  } catch (error) {
    throw toApiError(error);
  }
}

function mapTask(response: TaskResponse): Task {
  return {
    id: response.id,
    taskType: response.task_type,
    ownerSubject: response.owner_subject,
    status: response.status,
    attemptCount: response.attempt_count,
    maxAttempts: response.max_attempts,
    availableAt: response.available_at,
    resultSummary: response.result_summary,
    failureCode: response.failure_code,
    createdAt: response.created_at,
    updatedAt: response.updated_at,
  };
}

function mapTaskEvent(response: TaskEventResponse): TaskEvent {
  return {
    id: response.id,
    sequence: response.sequence,
    transitionId: response.transition_id,
    eventType: response.event_type,
    metadata: response.metadata,
    createdAt: response.created_at,
  };
}
