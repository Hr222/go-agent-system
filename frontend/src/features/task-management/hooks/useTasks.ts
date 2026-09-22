import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cancelTask,
  getTask,
  listTaskEvents,
  listTaskResources,
  listTasks,
  retryTask,
  type Task,
  type TaskStatus,
} from "../api/taskApi";

export const taskListQueryKey = ["tasks", "list"] as const;

export function useTaskList() {
  return useQuery({
    queryKey: taskListQueryKey,
    queryFn: ({ signal }) => listTasks({ signal }),
    retry: false,
    refetchInterval: (query) => {
      const tasks = query.state.data?.tasks ?? [];
      return tasks.some((task) => isTaskActive(task.status)) ? 5000 : false;
    },
  });
}

export function useTask(taskId: string | undefined) {
  return useQuery({
    queryKey: ["tasks", "detail", taskId],
    queryFn: ({ signal }) => getTask(taskId as string, signal),
    enabled: Boolean(taskId),
    retry: false,
    refetchInterval: (query) => {
      const task = query.state.data;
      return task && isTaskActive(task.status) ? 3000 : false;
    },
  });
}

export function useTaskEvents(taskId: string | undefined, poll = true) {
  return useQuery({
    queryKey: ["tasks", "events", taskId],
    queryFn: ({ signal }) => listTaskEvents(taskId as string, { signal }),
    enabled: Boolean(taskId),
    retry: false,
    refetchInterval: poll ? 3000 : false,
  });
}

export function useTaskResources(taskId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ["tasks", "resources", taskId],
    queryFn: ({ signal }) => listTaskResources(taskId as string, signal),
    enabled: Boolean(taskId) && enabled,
    retry: false,
  });
}

export function useCancelTask() {
  return useTaskCommand(cancelTask);
}

export function useRetryTask() {
  return useTaskCommand(retryTask);
}

function useTaskCommand(command: (taskId: string, commandId: string) => Promise<Task>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, commandId }: { taskId: string; commandId: string }) =>
      command(taskId, commandId),
    onSuccess: async (task) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: taskListQueryKey }),
        queryClient.invalidateQueries({ queryKey: ["tasks", "detail", task.id] }),
        queryClient.invalidateQueries({ queryKey: ["tasks", "events", task.id] }),
      ]);
    },
  });
}

export function isTaskActive(status: TaskStatus): boolean {
  return status === "queued"
    || status === "running"
    || status === "retry_wait"
    || status === "cancel_requested";
}
