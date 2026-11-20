/** 将平台接口接入 React Query，提供会话、工作流分页以及个人任务数据。 */
import { createContext, useContext } from 'react';
import { queryOptions, useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '@comfyshop/api-client';
import type { ApiClient, AuthSession, WorkflowCreate, TaskCreate } from '@comfyshop/api-client';
import type { Category, WorkflowFilters } from '../domain/types';
import {
  executionHistoryKey,
  taskActivityOptions,
  taskHistoryOptions,
  taskWithProgress,
} from './task-queries';
import type { TaskFilter } from './task-queries';

export const WorkspaceContext = createContext<ApiClient | null>(null);
function useApi() {
  const api = useContext(WorkspaceContext);
  if (!api) throw new Error('WorkspaceProvider is required');
  return api;
}

function useSession() {
  const api = useApi();
  return useQuery({
    queryKey: ['session'],
    queryFn: ({ signal }) => api.session(signal),
    retry: false,
    refetchOnWindowFocus: true,
  });
}

export function useAuthor(username: string) {
  const api = useApi();
  const session = useSession();
  return useQuery({
    queryKey: ['authors', session.data?.user?.id ?? null, username],
    enabled: !!username && !session.isPending,
    queryFn: ({ signal }) => api.author(username, signal),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
  });
}

/**
 * 按 `filters` 读取工作流。public 使用公开缓存，mine 和 favorites 按用户隔离。
 * 返回分页查询及瀑布流的 `resetKey`，筛选或用户变化时重置列表测量。
 */
export function useWorkflowPages(filters?: WorkflowFilters) {
  const api = useApi();
  const session = useSession();
  const userId = session.data?.user?.id;
  const scope = filters?.scope;
  const identity = [
    scope,
    scope === 'public' ? '' : userId,
    filters?.category,
    filters?.search,
    filters?.sort,
    filters?.author,
  ];
  const pages = useInfiniteQuery({
    queryKey: ['workflows', ...identity],
    enabled: !!filters && (scope === 'public' || !!userId),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => api.workflows({ ...filters, cursor: pageParam }, signal),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
  });
  return { pages, resetKey: identity.join(':') };
}

export function workflowDetailOptions(
  api: ApiClient,
  userId: string | null,
  workflowId: string,
  versionId?: string,
) {
  return queryOptions({
    queryKey: ['workflows', 'detail', userId, workflowId, ...(versionId ? [versionId] : [])],
    queryFn: ({ signal }) => api.workflow(workflowId, signal, versionId),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
  });
}

export function useWorkflowDetail(workflowId: string, versionId?: string) {
  const api = useApi();
  const session = useSession();
  return useQuery({
    ...workflowDetailOptions(api, session.data?.user?.id ?? null, workflowId, versionId),
    enabled: !!workflowId && !session.isPending,
  });
}

export function useTasks(workflowId?: string, state?: TaskFilter, versionId?: string) {
  const api = useApi();
  const userId = useSession().data?.user?.id;
  const queries = useQueryClient();
  const history = useInfiniteQuery(taskHistoryOptions(api, userId, workflowId, state, versionId));
  const activity = useQuery(
    taskActivityOptions(api, queries, userId, { workflowId, state, versionId }),
  );
  const items =
    history.data?.pages.flatMap((page) =>
      page.items
        .map((task) => taskWithProgress(task, activity.data?.updates[task.id]))
        .filter((task) =>
          !state
            ? true
            : state === 'active'
              ? task.status === 'queued' || task.status === 'running'
              : task.status === state,
        ),
    ) ?? [];
  return { history, activity, items };
}

export function useMachines() {
  const api = useApi();
  const session = useSession();
  return useQuery({
    queryKey: ['machines', session.data?.user?.id],
    enabled: !!session.data?.user,
    queryFn: ({ signal }) => api.machines(signal),
    refetchInterval: 10000,
  });
}

export function useExecutions(workflowId?: string, taskId?: string, versionId?: string) {
  const api = useApi();
  const userId = useSession().data?.user?.id;
  const queries = useQueryClient();
  const activity = useQuery(
    taskActivityOptions(api, queries, userId, { workflowId, taskId, versionId }),
  );
  return useInfiniteQuery({
    queryKey: executionHistoryKey(userId, workflowId, taskId, versionId),
    enabled: !!userId && !activity.isPending,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      api.executions(
        { workflow_id: workflowId, version_id: versionId, task_id: taskId, cursor: pageParam },
        signal,
      ),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
  });
}

export function useWorks(
  workflowId?: string,
  scope: 'public' | 'mine' = 'public',
  author?: string,
  category: Category = 'all',
  versionId?: string,
) {
  const api = useApi();
  const session = useSession();
  return useInfiniteQuery({
    queryKey: ['works', session.data?.user?.id, workflowId, scope, author, category, versionId],
    enabled: scope === 'public' || !!session.data?.user,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      api.works(
        {
          workflow_id: workflowId,
          version_id: versionId,
          current_version_only: scope === 'public' && !versionId ? true : undefined,
          scope,
          author,
          category,
          cursor: pageParam,
        },
        signal,
      ),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
  });
}

/** 返回当前身份、收藏和写操作。登录或退出时清除旧身份的请求和缓存。 */
export function useWorkspace() {
  const api = useApi();
  const queries = useQueryClient();
  const session = useSession();
  const user = session.data?.user;
  const data = useQuery({
    queryKey: ['workspace', user?.id],
    enabled: !!user,
    queryFn: ({ signal }) => api.workspace(signal),
  });
  const refresh = () => queries.invalidateQueries({ queryKey: ['workspace'] });
  return {
    api,
    state: {
      user: user?.username ?? null,
      nickname: user?.nickname ?? null,
      avatarUrl: user?.avatarUrl ?? null,
      email: user?.email ?? null,
      /** 已填写、还在等邮件确认的邮箱。 */
      pendingEmail: user?.pendingEmail ?? null,
      userId: user?.id ?? null,
      ready: !session.isPending && (!user || !data.isPending),
      error: session.error?.message ?? data.error?.message ?? null,
      favorites: data.data?.favoriteIds ?? [],
    },
    workspace: {
      reload: () => queries.invalidateQueries(),
      /** 登录或注册。注册时 `email` 是可选的邮箱，用于找回密码。 */
      signIn: async (account: string, password: string, register = false, email?: string) => {
        const result = register
          ? await api.register(account, password, email)
          : await api.login(account, password);
        await queries.cancelQueries({ predicate: (query) => query.queryKey[0] !== 'session' });
        queries.removeQueries({ predicate: (query) => query.queryKey[0] !== 'session' });
        queries.setQueryData(['session'], result);
      },
      signOut: async () => {
        await api.logout();
        await queries.cancelQueries({ predicate: (query) => query.queryKey[0] !== 'session' });
        queries.removeQueries({ predicate: (query) => query.queryKey[0] !== 'session' });
        queries.setQueryData(['session'], { user: null, csrfToken: null });
      },
      updateProfile: async (change: { nickname: string | null } | { avatar: File | null }) => {
        const saved =
          'nickname' in change
            ? await api.updateNickname(change.nickname)
            : change.avatar
              ? await api.uploadAvatar(change.avatar)
              : await api.removeAvatar();
        const fields =
          'nickname' in change ? { nickname: saved.nickname } : { avatarUrl: saved.avatarUrl };
        queries.setQueryData<AuthSession>(['session'], (session) =>
          session?.user?.id === saved.id
            ? { ...session, user: { ...session.user, ...fields } }
            : session,
        );
        void Promise.all(
          ['session', 'authors', 'workflows', 'works', 'workflow-route-replay'].map((key) =>
            queries.invalidateQueries({ queryKey: [key] }),
          ),
        );
      },
      /** 绑定或解除邮箱，并更新当前会话里的账号信息。 */
      updateEmail: async (email: string | null, password: string) => {
        const updated = await api.updateEmail(email, password);
        queries.setQueryData<AuthSession>(['session'], (session) =>
          session?.user?.id === updated.id
            ? {
                ...session,
                user: { ...session.user, email: updated.email, pendingEmail: updated.pendingEmail },
              }
            : session,
        );
      },
      /** 注销账号并清空本机缓存的个人数据。 */
      deleteAccount: async (password: string) => {
        await api.deleteAccount(password);
        await queries.cancelQueries({ predicate: (query) => query.queryKey[0] !== 'session' });
        queries.removeQueries({ predicate: (query) => query.queryKey[0] !== 'session' });
        queries.setQueryData(['session'], { user: null, csrfToken: null });
      },
      toggleFavorite: async (id: string) => {
        await api.favorite(id, !data.data?.favoriteIds.includes(id));
        await refresh();
        await queries.invalidateQueries({ queryKey: ['workflows'] });
      },
      importWorkflow: async (input: WorkflowCreate) => {
        const workflow = await api.createWorkflow(input);
        await refresh();
        await queries.invalidateQueries({ queryKey: ['workflows'] });
        return workflow;
      },
      publishWorkflow: async (id: string) => {
        await api.publishWorkflow(id);
        await refresh();
        await queries.invalidateQueries({ queryKey: ['workflows'] });
      },
      setDefaultMachine: async (id: string) => {
        await api.defaultMachine(id);
        await queries.invalidateQueries({ queryKey: ['machines'] });
      },
      run: async (body: TaskCreate) => {
        const task = await api.createTask(body);
        await Promise.all([
          queries.invalidateQueries({ queryKey: ['tasks'] }),
          queries.invalidateQueries({ queryKey: ['task-activity'] }),
        ]);
        return task;
      },
      cancelTask: async (id: string) => {
        await api.cancelTask(id);
        await Promise.all([
          queries.invalidateQueries({ queryKey: ['tasks'] }),
          queries.invalidateQueries({ queryKey: ['task-activity'] }),
          queries.invalidateQueries({ queryKey: ['task-progress'] }),
        ]);
      },
      resumeTask: async (id: string) => {
        await api.resumeTask(id);
        await Promise.all(
          ['tasks', 'task-activity', 'task-progress'].map((key) =>
            queries.invalidateQueries({ queryKey: [key] }),
          ),
        );
      },
    },
  };
}
