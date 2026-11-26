/** 保留已加载的任务历史分页，另由轻量查询更新排队和执行中的任务。 */
import { infiniteQueryOptions, queryOptions } from '@tanstack/react-query';
import type { InfiniteData, QueryClient } from '@tanstack/react-query';
import { ApiError } from '@comfyshop/api-client';
import type { ApiClient, Task } from '@comfyshop/api-client';
import { isTaskActive } from '../domain/types.ts';
import { workspaceKey } from './workspace-scope.ts';
import type { WorkspaceTarget } from './workspace-scope.ts';

type TaskPage = Awaited<ReturnType<ApiClient['tasks']>>;
type TaskUpdate = Pick<Task, 'id' | 'status' | 'progress' | 'stage' | 'updated'> &
  Partial<Pick<Task, 'error' | 'promptId' | 'media' | 'machineId' | 'machineName'>>;
type Activity = Awaited<ReturnType<ApiClient['taskActivity']>> & {
  updates: Record<string, TaskUpdate | undefined>;
};

/** 有排队或执行中的任务时刷新状态的间隔。 */
export const activePollMs = 2000;

/** 任务列表的筛选：active 为排队或执行中，其余为同名的结束状态。 */
export type TaskFilter = NonNullable<NonNullable<Parameters<ApiClient['tasks']>[0]>['state']>;

const taskHistoryKey = (
  userId?: string,
  workflowId?: string,
  state?: TaskFilter,
  versionId?: string,
  workspaceScope?: WorkspaceTarget,
  projectId?: string,
) =>
  [
    'tasks',
    userId,
    workflowId,
    state,
    ...(versionId || workspaceScope ? [versionId] : []),
    ...workspaceKey(workspaceScope),
    ...(projectId ? [{ projectId }] : []),
  ] as const;

export const executionHistoryKey = (
  userId?: string,
  workflowId?: string,
  taskId?: string,
  versionId?: string,
  workspaceScope?: WorkspaceTarget,
  projectId?: string,
) =>
  [
    'executions',
    userId,
    workflowId,
    taskId,
    ...(versionId || workspaceScope ? [versionId] : []),
    ...workspaceKey(workspaceScope),
    ...(projectId ? [{ projectId }] : []),
  ] as const;

/** 合并较新的活动更新，保留终态，并避免执行状态从运行退回排队。 */
export function taskWithProgress(task: Task, update?: TaskUpdate): Task {
  if (!update || !isTaskActive(task.status) || update.updated < task.updated) return task;
  if (task.status === 'running' && update.status === 'queued') return task;
  return { ...task, ...update };
}

export function taskHistoryOptions(
  api: ApiClient,
  userId?: string,
  workflowId?: string,
  state?: TaskFilter,
  versionId?: string,
  workspaceScope?: WorkspaceTarget,
  projectId?: string,
) {
  return infiniteQueryOptions({
    queryKey: taskHistoryKey(userId, workflowId, state, versionId, workspaceScope, projectId),
    enabled: !!userId,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      api.tasks(
        {
          workflow_id: workflowId,
          version_id: versionId,
          project_id: projectId,
          state,
          cursor: pageParam,
        },
        signal,
      ),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
  });
}

/**
 * 按用户、工作流、版本或单个任务创建活动查询。任务移出活动列表时单独读取最终状态。
 * 返回轮询配置。完成执行数变化时刷新对应结果，已加载的任务历史页继续保留。
 */
export function taskActivityOptions(
  api: ApiClient,
  queries: QueryClient,
  userId?: string,
  {
    workflowId,
    taskId,
    state,
    versionId,
    workspaceScope,
    projectId,
  }: {
    workflowId?: string;
    taskId?: string;
    state?: TaskFilter;
    versionId?: string;
    workspaceScope?: WorkspaceTarget;
    projectId?: string;
  } = {},
) {
  const queryKey = [
    'task-activity',
    userId,
    workflowId,
    taskId,
    state,
    versionId,
    ...workspaceKey(workspaceScope),
    ...(projectId ? [{ projectId }] : []),
  ] as const;
  const resultsKey = executionHistoryKey(
    userId,
    workflowId,
    taskId,
    versionId,
    workspaceScope,
    projectId,
  );
  const historyKey = taskHistoryKey(
    userId,
    workflowId,
    state,
    versionId,
    workspaceScope,
    projectId,
  );
  const history = () =>
    taskId
      ? []
      : (queries
          .getQueryData<InfiniteData<TaskPage>>(historyKey)
          ?.pages.flatMap((page) => page.items) ?? []);
  return queryOptions({
    queryKey,
    enabled: !!userId,
    queryFn: async ({ signal }): Promise<Activity> => {
      const activity = await api.taskActivity(
        { workflow_id: workflowId, version_id: versionId, task_id: taskId, project_id: projectId },
        signal,
      );
      const previous = queries.getQueryData<Activity>(queryKey);
      const updates = new Map<string, TaskUpdate>(
        activity.activeTasks.map((task) => [task.id, task]),
      );
      const missing: string[] = [];
      for (const task of history()) {
        if (!isTaskActive(task.status) || updates.has(task.id)) continue;
        // A task can leave the active set between ticks. Read its final state once.
        const last = previous?.updates[task.id];
        if (last && !isTaskActive(last.status) && last.updated >= task.updated)
          updates.set(task.id, last);
        else missing.push(task.id);
      }
      const details = await Promise.all(
        missing.map(async (id) => {
          try {
            const task = await api.task(id, signal);
            return !projectId || task.projectId === projectId ? task : null;
          } catch (error) {
            if (error instanceof ApiError && error.status === 404) return null;
            throw error;
          }
        }),
      );
      signal.throwIfAborted();
      if (details.includes(null))
        void queries.invalidateQueries({
          queryKey: historyKey,
          exact: true,
        });
      for (const detail of details) {
        if (!detail) continue;
        // 结束的任务带上代表成品，未筛选的历史列表不重新分页也能显示结果。
        updates.set(detail.id, {
          id: detail.id,
          status: detail.status,
          progress: detail.progress,
          stage: detail.stage,
          updated: detail.updated,
          error: detail.error,
          promptId: detail.promptId,
          media: detail.media,
          machineId: detail.machineId,
          machineName: detail.machineName,
        });
      }

      const ended =
        previous?.activeTasks.some((task) => !updates.has(task.id)) ||
        details.some((task) => task && !isTaskActive(task.status));
      if (ended)
        void queries.invalidateQueries({
          queryKey: ['tasks', userId],
          predicate: ({ queryKey: [, , historyWorkflow, historyState, historyVersion] }) =>
            historyState !== undefined &&
            (!workflowId || historyWorkflow === undefined || historyWorkflow === workflowId) &&
            (!versionId || historyVersion === undefined || historyVersion === versionId),
        });
      if (previous?.completedExecutions !== activity.completedExecutions)
        void queries.invalidateQueries({ queryKey: resultsKey });
      return { ...activity, updates: Object.fromEntries(updates) };
    },
    refetchInterval: ({ state }) => {
      if (state.data?.activeTasks.length) return activePollMs;
      const pending = history().some((task) =>
        isTaskActive(taskWithProgress(task, state.data?.updates[task.id]).status),
      );
      return pending ? activePollMs : false;
    },
  });
}
