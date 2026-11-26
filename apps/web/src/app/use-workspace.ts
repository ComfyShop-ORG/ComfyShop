/** 将平台接口接入 React Query，提供会话、工作流分页以及个人任务数据。 */
import { createContext, useContext, useMemo } from 'react';
import { queryOptions, useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, createApiClient } from '@comfyshop/api-client';
import type {
  ApiClient,
  AuthSession,
  Task,
  WorkflowCreate,
  TaskCreate,
  TaskProgress,
  TaskRetryRequest,
} from '@comfyshop/api-client';
import type { Category, WorkflowFilters } from '../domain/types';
import { isTaskActive } from '../domain/types';
import {
  activePollMs,
  executionHistoryKey,
  taskActivityOptions,
  taskHistoryOptions,
  taskWithProgress,
} from './task-queries';
import type { TaskFilter } from './task-queries';
import { ScopedWorkspace, workspaceKey } from './workspace-scope';
import type { WorkspaceTarget } from './workspace-scope';
import { t } from './i18n';
import { refreshPublishedContent } from './publication-queries';

export const WorkspaceContext = createContext<ApiClient | null>(null);
function useApi() {
  const api = useContext(WorkspaceContext);
  if (!api) throw new Error('WorkspaceProvider is required');
  return api;
}

function useWorkspaceReader() {
  const api = useApi();
  const scoped = useContext(ScopedWorkspace);
  return { api: scoped?.api ?? api, workspaceScope: scoped?.target, workspaceTeam: scoped?.team };
}

export function useSession() {
  const api = useApi();
  return useQuery({
    queryKey: ['session'],
    queryFn: ({ signal }) => api.session(signal),
    retry: false,
    refetchOnWindowFocus: true,
  });
}

export function useWorkspaceAccess(target?: WorkspaceTarget) {
  const identityApi = useApi();
  const userId = useSession().data?.user?.id;
  const queries = useQueryClient();
  const id = target?.id;
  const kind = target?.kind;
  const access = useQuery({
    queryKey: ['workspace-access', userId, target],
    enabled: !!userId && !!id,
    queryFn: async ({ signal }) =>
      kind === 'team'
        ? identityApi.team(id!, signal)
        : identityApi.sharedWorkspaceAccount(id!, signal),
    refetchOnMount: 'always',
    refetchInterval: 15000,
    retry: false,
    gcTime: 0,
  });
  const api = useMemo(
    () =>
      createApiClient('', fetch, () => void queries.invalidateQueries({ queryKey: ['session'] }), {
        workspaceOwner: kind === 'shared' ? id : undefined,
        workspaceTeam: kind === 'team' ? id : undefined,
        sessionCsrfToken: () => {
          const session = queries.getQueryData<AuthSession>(['session']);
          return session?.user?.id === userId ? (session?.csrfToken ?? null) : null;
        },
        messages: {
          offline: t('api.offline'),
          requestFailed: t('api.requestFailed'),
          invalidResponse: t('api.invalidResponse'),
        },
      }),
    [id, kind, queries, userId],
  );
  const pending = access.isPending || (!access.isFetchedAfterMount && access.isFetching);
  const account = access.data;
  const scope =
    target && account && userId && !pending && !access.isError
      ? 'role' in account
        ? { target, label: account.name, team: account, api }
        : { target, label: account.username, api }
      : null;
  return { userId, scope, error: access.error };
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

export function usePublicTeam(teamId?: string) {
  const api = useApi();
  return useQuery({
    queryKey: ['public-team', teamId],
    enabled: !!teamId,
    queryFn: ({ signal }) => api.publicTeam(teamId!, signal),
    retry: (count, error) =>
      !(error instanceof ApiError && error.status < 500 && error.status > 0) && count < 2,
    refetchOnMount: 'always',
    refetchOnWindowFocus: 'always',
  });
}

/**
 * 按 `filters` 读取工作流。public 使用公开缓存，mine 和 favorites 按用户隔离。
 * 返回分页查询及瀑布流的 `resetKey`，筛选或用户变化时重置列表测量。
 */
export function useWorkflowPages(filters?: WorkflowFilters) {
  const { api, workspaceScope } = useWorkspaceReader();
  const identityApi = useApi();
  const session = useSession();
  const userId = session.data?.user?.id;
  const scope = filters?.scope;
  const catalog = scope === 'public' && !filters?.inpaintArtifactId;
  const listScope = catalog ? undefined : workspaceScope;
  const identity = [
    scope,
    catalog ? '' : userId,
    filters?.category,
    filters?.search,
    filters?.sort,
    filters?.author,
    filters?.publicTeamId,
    filters?.projectId,
    ...(filters?.inpaintArtifactId ? [filters.inpaintArtifactId] : []),
    ...workspaceKey(listScope),
  ];
  const pages = useInfiniteQuery({
    queryKey: ['workflows', ...identity],
    enabled: !!filters && (catalog || !!userId),
    refetchOnMount: listScope?.kind === 'team' || filters?.publicTeamId ? 'always' : undefined,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => {
      const { publicTeamId, projectId, inpaintArtifactId, ...listFilters } = filters!;
      return (catalog ? identityApi : api).workflows(
        {
          ...listFilters,
          public_team_id: publicTeamId,
          project_id: projectId,
          inpaint_artifact_id: inpaintArtifactId,
          cursor: pageParam,
        },
        signal,
      );
    },
    getNextPageParam: (page) => page.nextCursor ?? undefined,
  });
  return { pages, resetKey: JSON.stringify(identity) };
}

export function workflowDetailOptions(
  api: ApiClient,
  userId: string | null,
  workflowId: string,
  versionId?: string,
  workspaceScope?: WorkspaceTarget,
) {
  return queryOptions({
    queryKey: [
      'workflows',
      'detail',
      userId,
      workflowId,
      ...(versionId ? [versionId] : []),
      ...workspaceKey(workspaceScope),
    ],
    queryFn: ({ signal }) => api.workflow(workflowId, signal, versionId),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
  });
}

export function useWorkflowDetail(workflowId: string, versionId?: string) {
  const { api, workspaceScope } = useWorkspaceReader();
  const session = useSession();
  return useQuery({
    ...workflowDetailOptions(
      api,
      session.data?.user?.id ?? null,
      workflowId,
      versionId,
      workspaceScope,
    ),
    enabled: !!workflowId && !session.isPending,
  });
}

export function useTasks(
  workflowId?: string,
  state?: TaskFilter,
  versionId?: string,
  projectId?: string,
) {
  const { api, workspaceScope } = useWorkspaceReader();
  const userId = useSession().data?.user?.id;
  const queries = useQueryClient();
  const history = useInfiniteQuery(
    taskHistoryOptions(api, userId, workflowId, state, versionId, workspaceScope, projectId),
  );
  const activity = useQuery(
    taskActivityOptions(api, queries, userId, {
      workflowId,
      state,
      versionId,
      workspaceScope,
      projectId,
    }),
  );
  const items =
    history.data?.pages.flatMap((page) =>
      page.items
        .map((task) => taskWithProgress(task, activity.data?.updates[task.id]))
        .filter((task) =>
          !state ? true : state === 'active' ? isTaskActive(task.status) : task.status === state,
        ),
    ) ?? [];
  return { history, activity, items };
}

export function useMachines(enabled = true, { live = false } = {}) {
  const { api, workspaceScope } = useWorkspaceReader();
  const session = useSession();
  return useQuery({
    queryKey: ['machines', session.data?.user?.id, ...workspaceKey(workspaceScope)],
    enabled: enabled && !!session.data?.user && workspaceScope?.kind !== 'shared',
    queryFn: ({ signal }) => api.machines(signal),
    refetchInterval: live ? activePollMs : 10_000,
    ...(live && ({ refetchOnMount: 'always', refetchOnWindowFocus: 'always' } as const)),
  });
}

export function useTaskProgress(id: string, enabled = true, includeTakeoverHistory = false) {
  const { api, workspaceScope } = useWorkspaceReader();
  const userId = useSession().data?.user?.id;
  const queries = useQueryClient();
  const queryKey = [
    'task-progress',
    userId,
    id,
    includeTakeoverHistory,
    ...workspaceKey(workspaceScope),
  ] as const;
  return useQuery({
    queryKey,
    enabled: !!userId && enabled,
    queryFn: async ({ signal }) => {
      const next = await api.taskProgress(id, signal, {
        include_takeover_history: includeTakeoverHistory || undefined,
      });
      const prior = queries.getQueryData<TaskProgress>(queryKey);
      if (
        (prior?.status === 'failed' || prior?.status === 'cancelled') &&
        next.executions.some(
          (execution, index) =>
            execution.status === 'succeeded' && prior.executions[index]?.status !== 'succeeded',
        )
      ) {
        void Promise.all(
          ['executions', 'tasks', 'task-activity'].map((key) =>
            queries.invalidateQueries({ queryKey: [key] }),
          ),
        );
      }
      return next;
    },
    refetchInterval: ({ state: { data } }) => {
      if (isTaskActive(data?.status)) return activePollMs;
      return data?.executions.some(
        ({ recovery }) => recovery === 'pending' || recovery === 'uploading',
      )
        ? 5000
        : false;
    },
  });
}

export type ExecutionFilters = Pick<
  NonNullable<Parameters<ApiClient['executions']>[0]>,
  'workflow_name' | 'created_from' | 'created_before'
>;

export function useExecutions(
  workflowId?: string,
  taskId?: string,
  versionId?: string,
  filters?: ExecutionFilters,
  projectId?: string,
) {
  const { api, workspaceScope } = useWorkspaceReader();
  const userId = useSession().data?.user?.id;
  const queries = useQueryClient();
  const activity = useQuery(
    taskActivityOptions(api, queries, userId, {
      workflowId,
      taskId,
      versionId,
      workspaceScope,
      projectId,
    }),
  );
  const historyKey = executionHistoryKey(
    userId,
    workflowId,
    taskId,
    versionId,
    workspaceScope,
    projectId,
  );
  return useInfiniteQuery({
    queryKey: filters ? [...historyKey, filters] : historyKey,
    enabled: !!userId && !activity.isPending,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      api.executions(
        {
          workflow_id: workflowId,
          version_id: versionId,
          task_id: taskId,
          project_id: projectId,
          cursor: pageParam,
          ...filters,
        },
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
  publicTeamId?: string,
  projectId?: string,
) {
  const { api, workspaceScope } = useWorkspaceReader();
  const identityApi = useApi();
  const session = useSession();
  return useInfiniteQuery({
    queryKey: [
      'works',
      session.data?.user?.id,
      workflowId,
      scope,
      author,
      category,
      versionId,
      publicTeamId,
      ...workspaceKey(workspaceScope),
      ...(projectId ? [{ projectId }] : []),
    ],
    enabled: scope === 'public' || !!session.data?.user,
    refetchOnMount: publicTeamId ? 'always' : undefined,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      (publicTeamId ? identityApi : api).works(
        {
          workflow_id: workflowId,
          version_id: versionId,
          current_version_only:
            scope === 'public' && !versionId && !publicTeamId ? true : undefined,
          scope,
          author,
          public_team_id: publicTeamId,
          project_id: projectId,
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
  const identityApi = useApi();
  const { api, workspaceScope, workspaceTeam } = useWorkspaceReader();
  const queries = useQueryClient();
  const session = useSession();
  const user = session.data?.user;
  const data = useQuery({
    queryKey: ['workspace', user?.id, ...workspaceKey(workspaceTeam ? workspaceScope : undefined)],
    enabled: !!user,
    queryFn: ({ signal }) => (workspaceTeam ? api : identityApi).workspace(signal),
  });
  const refresh = () => queries.invalidateQueries({ queryKey: ['workspace'] });
  const canManageWorkspace =
    !workspaceScope || workspaceTeam?.role === 'owner' || workspaceTeam?.role === 'manager';
  const canEditWorkspace =
    !workspaceScope || (workspaceTeam !== undefined && workspaceTeam.role !== 'reader');
  return {
    api,
    identityApi,
    workspaceScope,
    workspaceTeam,
    canManageWorkspace,
    canEditWorkspace,
    canCancelTask: (task: Pick<Task, 'owner'>) =>
      canManageWorkspace || (canEditWorkspace && task.owner === user?.id),
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
      canImportOfficialWorkflows: data.data?.canImportOfficialWorkflows === true,
      canManageOfficialImportGrants: data.data?.canManageOfficialImportGrants === true,
    },
    workspace: {
      reload: () => queries.invalidateQueries(),
      /** 登录或注册。注册时 `email` 是可选的邮箱，用于找回密码。 */
      signIn: async (account: string, password: string, register = false, email?: string) => {
        const result = register
          ? await identityApi.register(account, password, email)
          : await identityApi.login(account, password);
        queries.setQueryData(['session'], result);
      },
      signOut: async () => {
        await identityApi.logout();
        queries.setQueryData(['session'], { user: null, csrfToken: null });
      },
      updateProfile: async (change: { nickname: string | null } | { avatar: File | null }) => {
        const saved =
          'nickname' in change
            ? await identityApi.updateNickname(change.nickname)
            : change.avatar
              ? await identityApi.uploadAvatar(change.avatar)
              : await identityApi.removeAvatar();
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
        const updated = await identityApi.updateEmail(email, password);
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
        await identityApi.deleteAccount(password);
        queries.setQueryData(['session'], { user: null, csrfToken: null });
      },
      toggleFavorite: async (id: string) => {
        const saved = !data.data?.favoriteIds.includes(id);
        await api.favorite(id, saved);
        await refresh();
        await queries.invalidateQueries({ queryKey: ['workflows'] });
        return saved;
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
        await refreshPublishedContent(queries);
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
        const result = await api.cancelTask(id);
        await Promise.all([
          queries.invalidateQueries({ queryKey: ['tasks'] }),
          queries.invalidateQueries({ queryKey: ['task-activity'] }),
          queries.invalidateQueries({ queryKey: ['task-progress'] }),
        ]);
        return result;
      },
      resumeTask: async (id: string) => {
        await api.resumeTask(id);
        await Promise.all(
          ['tasks', 'task-activity', 'task-progress'].map((key) =>
            queries.invalidateQueries({ queryKey: [key] }),
          ),
        );
      },
      changeTaskMachine: async (id: string, machineId: string) => {
        await api.changeTaskMachine(id, machineId);
        await Promise.all(
          ['tasks', 'task-progress', 'machines'].map((key) =>
            queries.invalidateQueries({ queryKey: [key] }),
          ),
        );
      },
      retryExecutions: async (id: string, body: TaskRetryRequest) => {
        await api.retryExecutions(id, body);
        await Promise.all(
          ['tasks', 'task-progress', 'task-activity', 'machines'].map((key) =>
            queries.invalidateQueries({ queryKey: [key] }),
          ),
        );
      },
    },
  };
}
