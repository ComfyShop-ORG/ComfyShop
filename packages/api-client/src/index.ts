/** 封装浏览器调用 FastAPI 的方式。路径、参数和返回类型都取自生成的 `schema.d.ts`。 */
import type { components, paths } from './schema';
export { defaultAssetContentTypes, workflowCategoryValues } from './runtime-contract.ts';

export type AuthSession = components['schemas']['SessionRead'];
export type Team = components['schemas']['TeamRead'];
export type ArchivedTeam = components['schemas']['ArchivedTeamRead'];
export type TeamRole = components['schemas']['TeamRole'];
export type TeamMember = components['schemas']['TeamMemberRead'];
export type TeamMemberRole = components['schemas']['TeamMemberChange']['role'];
export type TeamEvent = components['schemas']['TeamEventRead'];
export type Project = components['schemas']['ProjectRead'];
export type ProjectListItem = components['schemas']['ProjectListItem'];
export type Workflow = components['schemas']['WorkflowRead'];
export type WorkflowCreate = components['schemas']['WorkflowCreate'];
export type WorkflowUpdate = components['schemas']['WorkflowUpdate'];
export type WorkflowVersion = components['schemas']['WorkflowVersionRead'];
export type GenerationInputs = components['schemas']['GenerationInputs'];
export type TaskCreate = components['schemas']['TaskCreate'];
export type Task = components['schemas']['TaskRead'];
export type TaskProgress = components['schemas']['TaskProgressRead'];
export type TaskRetryRequest =
  components['schemas']['TaskRetryRequest'] | components['schemas']['ServiceRetryRequest'];
export type Media = components['schemas']['MediaRead'];
export type Machine = components['schemas']['MachineRead'];
export type WorkerType = components['schemas']['WorkerType'];
export type MachineKey = components['schemas']['MachineKey'];
export type Asset = components['schemas']['AssetRead'];
export type Artifact = components['schemas']['ArtifactRead'];
export type Execution = components['schemas']['ExecutionRead'];
export type Work = components['schemas']['WorkRead'];
export type CoverUpdate = components['schemas']['CoverUpdate'];
export type Replay = components['schemas']['ReplayRead'];
/** 重跑来源最多指定一种。executionId 表示自己的执行，workId 表示作品。 */
export type ReplaySource = { executionId?: string; workId?: string };
export type InpaintTarget = components['schemas']['InpaintTarget'];
export type WorkflowForm = components['schemas']['WorkflowForm'];
export type WorkflowFormData = components['schemas']['WorkflowFormData'];
export type WorkflowInput = WorkflowForm['fields'][number];
export type WorkflowParameterDisplay = WorkflowForm['parameterLayout'][number];
export type InputValue = WorkflowInput['default'];
export type ApiClient = ReturnType<typeof createApiClient>;

type Verb = 'get' | 'post' | 'put' | 'patch' | 'delete';
/** 契约中某个路径在某个方法下的操作定义。路径或方法不存在时调用处无法通过编译。 */
type Operation<P extends keyof paths, V extends Verb> =
  paths[P] extends Record<V, infer O> ? O : never;
type Query<P extends keyof paths, V extends Verb = 'get'> =
  Operation<P, V> extends { parameters: { query?: infer Q } } ? NonNullable<Q> : never;
type Result<O> = O extends { responses: infer R }
  ? R extends { 200: { content: { 'application/json': infer T } } }
    ? T
    : R extends { 201: { content: { 'application/json': infer T } } }
      ? T
      : void
  : never;
/** 有路径参数或请求体的操作必须提供对应字段，二进制请求体以 Blob 发送。 */
type Options<O> = { signal?: AbortSignal } & (O extends {
  parameters: { query?: infer Q };
}
  ? { query?: { [K in keyof NonNullable<Q>]?: NonNullable<Q>[K] | undefined } }
  : unknown) &
  (O extends { parameters: { path: infer X } } ? { path: X } : unknown) &
  (O extends { requestBody: { content: { 'application/json': infer B } } }
    ? { body: B }
    : O extends { requestBody: { content: { 'application/octet-stream': unknown } } }
      ? { body: Blob }
      : unknown);

export class ApiError extends Error {
  /** HTTP 状态码。0 表示网络请求没有收到响应。 */
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/**
 * 通过会话 Cookie 发送请求。在内存中保存 CSRF 值，用于写操作。
 * @param baseUrl 平台地址。空字符串表示使用当前网页的来源。
 * @param fetcher 可注入的请求实现，默认为浏览器的 `fetch`。
 * @param onUnauthorized 会话失效后清理页面身份数据的回调。登录失败由登录表单处理。
 * @returns 包含登录、工作流、任务和媒体接口方法的客户端。
 */
export function createApiClient(
  baseUrl = '',
  fetcher: typeof fetch = fetch,
  onUnauthorized?: () => void,
  settings: {
    language?: string;
    messages?: { offline: string; requestFailed: string; invalidResponse: string };
    workspaceOwner?: string;
    workspaceTeam?: string;
    sessionCsrfToken?: () => string | null;
  } = {},
) {
  const base = baseUrl.replace(/\/$/, '');
  const teamId = settings.workspaceTeam;
  let csrfToken: string | null = null;
  /**
   * 按契约里的路径模板发起请求。JSON 请求体会序列化，Blob 作为原始文件发送，204 返回 undefined。
   * @throws {ApiError} 网络失败、HTTP 错误或无效 JSON 响应。调用方取消时传播请求的原始异常。
   */
  async function call<P extends keyof paths, V extends Verb>(
    verb: V,
    template: P,
    options: Options<Operation<P, V>>,
  ): Promise<Result<Operation<P, V>>> {
    if (settings.workspaceOwner && verb !== 'get')
      throw new ApiError(403, settings.messages?.requestFailed ?? '共享空间为只读');
    const scopedWrite =
      /^\/api\/v1\/(machines|tasks|executions|artifacts|works|projects)(\/|$)/.test(template) ||
      template === '/api/v1/assets/{asset_id}/library' ||
      template === '/api/v1/workflows/from-connection' ||
      (verb === 'delete' && template === '/api/v1/workflows/{workflow_id}') ||
      template === '/api/v1/workflows/{workflow_id}/publish' ||
      template === '/api/v1/workflows/{workflow_id}/restore' ||
      template === '/api/v1/workflows/{workflow_id}/versions/{version_id}/parameter-layout';
    if (teamId && verb !== 'get' && !scopedWrite && !template.startsWith('/api/v1/teams/'))
      throw new ApiError(403, settings.messages?.requestFailed ?? '请在团队空间内操作');
    const { signal, path, query, body } = options as {
      signal?: AbortSignal;
      path?: Record<string, string | number>;
      query?: Record<string, string | number | boolean | string[] | null | undefined>;
      body?: unknown;
    };
    const values = new URLSearchParams();
    for (const [key, value] of Object.entries(query ?? {})) {
      if (Array.isArray(value)) {
        for (const item of value) values.append(key, item);
      } else if (value !== undefined && value !== null && value !== '') {
        values.set(key, String(value));
      }
    }
    if (settings.workspaceOwner) values.set('workspace_owner', settings.workspaceOwner);
    if (teamId && (verb === 'get' || scopedWrite)) values.set('workspace_team', teamId);
    const url =
      template.replace(/\{(\w+)\}/g, (_match, name: string) =>
        encodeURIComponent(String(path?.[name])),
      ) + (values.size ? `?${values}` : '');
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (settings.language) headers['Accept-Language'] = settings.language;
    const binary = body instanceof Blob;
    if (body !== undefined)
      headers['Content-Type'] = binary ? 'application/octet-stream' : 'application/json';
    if (verb !== 'get') {
      const token = settings.sessionCsrfToken ? settings.sessionCsrfToken() : csrfToken;
      if (token) headers['X-CSRF-Token'] = token;
    }
    let response: Response;
    try {
      response = await fetcher(`${base}${url}`, {
        method: verb.toUpperCase(),
        body: body === undefined ? undefined : binary ? body : JSON.stringify(body),
        signal,
        credentials: 'include',
        cache: 'no-store',
        headers,
      });
    } catch (error) {
      if (signal?.aborted) throw error;
      throw new ApiError(0, settings.messages?.offline ?? '无法连接服务');
    }
    if (!response.ok) {
      if (response.status === 401 && template !== '/api/v1/auth/login') {
        csrfToken = null;
        onUnauthorized?.();
      }
      const error: unknown = await response.json().catch(() => null);
      throw new ApiError(
        response.status,
        error !== null &&
          typeof error === 'object' &&
          'detail' in error &&
          typeof error.detail === 'string'
          ? error.detail
          : (settings.messages?.requestFailed ?? '请求失败，请重试'),
      );
    }
    type Value = Result<Operation<P, V>>;
    if (response.status === 204) return undefined as Value;
    try {
      return (await response.json()) as Value;
    } catch {
      throw new ApiError(502, settings.messages?.invalidResponse ?? '服务响应无效');
    }
  }
  /** 登录、注册和会话恢复都会返回新的 CSRF 值，后续写操作使用它。 */
  function remember(result: AuthSession) {
    csrfToken = result.csrfToken;
    return result;
  }
  return {
    session: async (signal?: AbortSignal) =>
      remember(await call('get', '/api/v1/auth/session', { signal })),
    updateNickname: (nickname: string | null) =>
      call('put', '/api/v1/auth/profile', { body: { nickname } }),
    uploadAvatar: (file: Blob) => call('put', '/api/v1/auth/profile/avatar', { body: file }),
    removeAvatar: () => call('delete', '/api/v1/auth/profile/avatar', {}),
    author: (username: string, signal?: AbortSignal) =>
      call('get', '/api/v1/authors/{username}', { path: { username }, signal }),
    officialImportGrants: (cursor: string | null, signal?: AbortSignal) =>
      call('get', '/api/v1/auth/official-import-grants', { query: { cursor }, signal }),
    setOfficialImportGrant: (username: string, granted: boolean) =>
      call('put', '/api/v1/auth/official-import-grants/{username}', {
        path: { username },
        body: { granted },
      }),
    login: async (username: string, password: string) =>
      remember(await call('post', '/api/v1/auth/login', { body: { username, password } })),
    register: async (username: string, password: string, email?: string) =>
      remember(
        await call('post', '/api/v1/auth/register', {
          body: { username, password, email: email || null },
        }),
      ),
    logout: async () => {
      await call('post', '/api/v1/auth/logout', {});
      csrfToken = null;
    },
    webPushPreference: (signal?: AbortSignal) => call('get', '/api/v1/web-push', { signal }),
    enableWebPush: (body: components['schemas']['WebPushWrite']) =>
      call('put', '/api/v1/web-push', { body }),
    disableWebPush: () => call('delete', '/api/v1/web-push', {}),
    changePassword: (currentPassword: string, newPassword: string) =>
      call('post', '/api/v1/auth/password', { body: { currentPassword, newPassword } }),
    updateEmail: (email: string | null, password: string) =>
      call('put', '/api/v1/auth/email', { body: { email, password } }),
    confirmEmail: (token: string) =>
      call('post', '/api/v1/auth/email/confirm', { body: { token } }),
    requestPasswordReset: (email: string) =>
      call('post', '/api/v1/auth/password-reset', { body: { email } }),
    confirmPasswordReset: (token: string, password: string) =>
      call('post', '/api/v1/auth/password-reset/confirm', { body: { token, password } }),
    deleteAccount: async (password: string) => {
      await call('post', '/api/v1/auth/account/delete', { body: { password } });
      csrfToken = null;
    },
    health: (signal?: AbortSignal) => call('get', '/api/v1/health', { signal }),
    presentation: (signal?: AbortSignal) => call('get', '/api/v1/presentation', { signal }),
    workspace: (signal?: AbortSignal) => call('get', '/api/v1/workspace', { signal }),
    teams: (cursor: string | null, signal?: AbortSignal) =>
      call('get', '/api/v1/teams', { query: { cursor }, signal }),
    team: (id: string, signal?: AbortSignal) =>
      call('get', '/api/v1/teams/{team_id}', { path: { team_id: id }, signal }),
    publicTeam: (id: string, signal?: AbortSignal) =>
      call('get', '/api/v1/teams/{team_id}/public', { path: { team_id: id }, signal }),
    setTeamProfileVisibility: (id: string, isPublic: boolean) =>
      call('put', '/api/v1/teams/{team_id}/profile-visibility', {
        path: { team_id: id },
        body: { public: isPublic },
      }),
    createTeam: (name: string) => call('post', '/api/v1/teams', { body: { name } }),
    renameTeam: (id: string, name: string) =>
      call('patch', '/api/v1/teams/{team_id}', { path: { team_id: id }, body: { name } }),
    updateTeamAvatar: (id: string, avatar: Blob | null) => {
      const path = { team_id: id };
      return avatar
        ? call('put', '/api/v1/teams/{team_id}/avatar', { path, body: avatar })
        : call('delete', '/api/v1/teams/{team_id}/avatar', { path });
    },
    teamMembers: (id: string, cursor: string | null, signal?: AbortSignal) =>
      call('get', '/api/v1/teams/{team_id}/members', {
        path: { team_id: id },
        query: { cursor },
        signal,
      }),
    teamEvents: (
      id: string,
      query: Query<'/api/v1/teams/{team_id}/events'>,
      signal?: AbortSignal,
    ) => call('get', '/api/v1/teams/{team_id}/events', { path: { team_id: id }, query, signal }),
    setTeamMember: (id: string, username: string, role: TeamMemberRole) =>
      call('put', '/api/v1/teams/{team_id}/members/by-name/{username}', {
        path: { team_id: id, username },
        body: { role },
      }),
    removeTeamMember: (id: string, memberId: string) =>
      call('delete', '/api/v1/teams/{team_id}/members/{member_id}', {
        path: { team_id: id, member_id: memberId },
      }),
    transferTeam: (id: string, memberId: string) =>
      call('put', '/api/v1/teams/{team_id}/owner/{member_id}', {
        path: { team_id: id, member_id: memberId },
      }),
    archiveTeam: (id: string) =>
      call('delete', '/api/v1/teams/{team_id}', { path: { team_id: id } }),
    archivedTeams: (cursor: string | null, signal?: AbortSignal) =>
      call('get', '/api/v1/teams/archived', { query: { cursor }, signal }),
    restoreTeam: (id: string) =>
      call('post', '/api/v1/teams/{team_id}/restore', { path: { team_id: id } }),
    copyWorkflowToTeam: (id: string, workflowId: string, versionId: string) =>
      call('post', '/api/v1/teams/{team_id}/workflows/{workflow_id}/copy', {
        path: { team_id: id, workflow_id: workflowId },
        query: { version_id: versionId },
      }),
    copyAssetToTeam: (id: string, assetId: string) =>
      call('post', '/api/v1/teams/{team_id}/assets/{asset_id}/copy', {
        path: { team_id: id, asset_id: assetId },
      }),
    workspaceShares: (query: Query<'/api/v1/workspace/shares'>, signal?: AbortSignal) =>
      call('get', '/api/v1/workspace/shares', { query, signal }),
    grantWorkspaceShare: (username: string) =>
      call('put', '/api/v1/workspace/shares/by-name/{username}', { path: { username } }),
    revokeWorkspaceShare: (id: string) =>
      call('delete', '/api/v1/workspace/shares/{viewer_id}', { path: { viewer_id: id } }),
    sharedWorkspaceAccount: (id: string, signal?: AbortSignal) =>
      call('get', '/api/v1/workspace/shared/{owner_id}', { path: { owner_id: id }, signal }),
    projects: (query: Query<'/api/v1/projects'> = {}, signal?: AbortSignal) =>
      call('get', '/api/v1/projects', { query, signal }),
    project: (id: string, signal?: AbortSignal) =>
      call('get', '/api/v1/projects/{project_id}', { path: { project_id: id }, signal }),
    createProject: (body: components['schemas']['ProjectCreate']) =>
      call('post', '/api/v1/projects', { body }),
    updateProject: (id: string, body: components['schemas']['ProjectCreate']) =>
      call('put', '/api/v1/projects/{project_id}', { path: { project_id: id }, body }),
    setProjectArchived: (id: string, archived: boolean) =>
      call('put', '/api/v1/projects/{project_id}/archive', {
        path: { project_id: id },
        body: { archived },
      }),
    deleteProject: (id: string) =>
      call('delete', '/api/v1/projects/{project_id}', { path: { project_id: id } }),
    restoreProject: (id: string) =>
      call('post', '/api/v1/projects/{project_id}/restore', { path: { project_id: id } }),
    changeProjectMaterial: (
      projectId: string,
      kind: 'workflows' | 'assets',
      recordId: string,
      linked: boolean,
    ) =>
      call(linked ? 'put' : 'delete', '/api/v1/projects/{project_id}/{kind}/{record_id}', {
        path: { project_id: projectId, kind, record_id: recordId },
      }),
    workflows: (query: Query<'/api/v1/workflows'> = {}, signal?: AbortSignal) =>
      call('get', '/api/v1/workflows', { query, signal }),
    workflow: (id: string, signal?: AbortSignal, versionId?: string) =>
      call('get', '/api/v1/workflows/{workflow_id}', {
        path: { workflow_id: id },
        query: { version_id: versionId },
        signal,
      }),
    workflowVersions: (id: string, signal?: AbortSignal) =>
      call('get', '/api/v1/workflows/{workflow_id}/versions', {
        path: { workflow_id: id },
        signal,
      }),
    inpaintTargets: (id: string, signal?: AbortSignal) =>
      call('get', '/api/v1/artifacts/{artifact_id}/inpaint-targets', {
        path: { artifact_id: id },
        signal,
      }),
    workflowForm: (
      id: string,
      versionId: string,
      machineId: string,
      signal?: AbortSignal,
      source?: ReplaySource,
    ) =>
      call('get', '/api/v1/workflows/{workflow_id}/inputs', {
        path: { workflow_id: id },
        query: {
          version_id: versionId,
          machine_id: machineId,
          execution_id: source?.executionId,
          work_id: source?.workId,
        },
        signal,
      }),
    serviceWorkflowForm: (
      id: string,
      versionId: string,
      signal?: AbortSignal,
      source?: ReplaySource,
    ) =>
      call('get', '/api/v1/workflows/{workflow_id}/service-inputs', {
        path: { workflow_id: id },
        query: {
          version_id: versionId,
          execution_id: source?.executionId,
          work_id: source?.workId,
        },
        signal,
      }),
    saveWorkflowParameterLayout: (
      id: string,
      versionId: string,
      machineId: string | undefined,
      parameterLayout: WorkflowParameterDisplay[],
    ) =>
      call('put', '/api/v1/workflows/{workflow_id}/versions/{version_id}/parameter-layout', {
        path: { workflow_id: id, version_id: versionId },
        body: { machineId, parameterLayout },
      }),
    assets: (query: Query<'/api/v1/assets'> = {}, signal?: AbortSignal) =>
      call('get', '/api/v1/assets', { query, signal }),
    assetUsage: (signal?: AbortSignal) => call('get', '/api/v1/assets/usage', { signal }),
    uploadAsset: (
      file: File,
      id: string,
      signal?: AbortSignal,
      { saveToLibrary }: { saveToLibrary?: boolean } = {},
    ) =>
      teamId
        ? call('put', '/api/v1/teams/{team_id}/assets/{asset_id}', {
            path: { team_id: teamId, asset_id: id },
            query: { filename: file.name, save_to_library: saveToLibrary ?? false },
            body: file,
            signal,
          })
        : call('put', '/api/v1/assets/{asset_id}', {
            path: { asset_id: id },
            query: { filename: file.name, save_to_library: saveToLibrary },
            body: file,
            signal,
          }),
    asset: (id: string, signal?: AbortSignal) =>
      call('get', '/api/v1/assets/{asset_id}', { path: { asset_id: id }, signal }),
    saveAsset: (id: string) =>
      call('put', '/api/v1/assets/{asset_id}/library', { path: { asset_id: id } }),
    removeSavedAsset: (id: string) =>
      call('delete', '/api/v1/assets/{asset_id}/library', { path: { asset_id: id } }),
    useArtifactInput: (id: string, signal?: AbortSignal) =>
      call('put', '/api/v1/artifacts/{artifact_id}/input', { path: { artifact_id: id }, signal }),
    saveArtifactAsAsset: (id: string) =>
      call('put', '/api/v1/artifacts/{artifact_id}/library', { path: { artifact_id: id } }),
    graph: (id: string, versionId?: string, signal?: AbortSignal) =>
      call('get', '/api/v1/workflows/{workflow_id}/graph', {
        path: { workflow_id: id },
        query: { version_id: versionId },
        signal,
      }),
    createWorkflow: (body: WorkflowCreate) =>
      teamId
        ? call('post', '/api/v1/teams/{team_id}/workflows', { path: { team_id: teamId }, body })
        : call('post', '/api/v1/workflows', { body }),
    /** 修改名称或分类。带 `graph` 时保存为新的草稿版本，已发布的版本保持不变。 */
    updateWorkflow: (id: string, body: WorkflowUpdate) =>
      teamId
        ? call('patch', '/api/v1/teams/{team_id}/workflows/{workflow_id}', {
            path: { team_id: teamId, workflow_id: id },
            body,
          })
        : call('patch', '/api/v1/workflows/{workflow_id}', { path: { workflow_id: id }, body }),
    deleteWorkflow: (id: string) =>
      call('delete', '/api/v1/workflows/{workflow_id}', { path: { workflow_id: id } }),
    restoreWorkflow: (id: string) =>
      call('post', '/api/v1/workflows/{workflow_id}/restore', { path: { workflow_id: id } }),
    publishWorkflow: (id: string) =>
      call('post', '/api/v1/workflows/{workflow_id}/publish', { path: { workflow_id: id } }),
    /** 上传的图片会替换作品指定。清除作品指定时沿用已上传的图片。 */
    setWorkflowCover: (id: string, body: components['schemas']['WorkflowCoverUpdate']) =>
      teamId
        ? call('put', '/api/v1/teams/{team_id}/workflows/{workflow_id}/cover', {
            path: { team_id: teamId, workflow_id: id },
            body,
          })
        : call('put', '/api/v1/workflows/{workflow_id}/cover', {
            path: { workflow_id: id },
            body,
          }),
    favorite: (id: string, saved: boolean) =>
      teamId
        ? call(
            saved ? 'put' : 'delete',
            '/api/v1/teams/{team_id}/workflows/{workflow_id}/favorite',
            {
              path: { team_id: teamId, workflow_id: id },
            },
          )
        : saved
          ? call('put', '/api/v1/workflows/{workflow_id}/favorite', {
              path: { workflow_id: id },
            })
          : call('delete', '/api/v1/workflows/{workflow_id}/favorite', {
              path: { workflow_id: id },
            }),
    tasks: (query: Query<'/api/v1/tasks'> = {}, signal?: AbortSignal) =>
      call('get', '/api/v1/tasks', { query, signal }),
    taskActivity: (query: Query<'/api/v1/tasks/activity'> = {}, signal?: AbortSignal) =>
      call('get', '/api/v1/tasks/activity', { query, signal }),
    task: (id: string, signal?: AbortSignal) =>
      call('get', '/api/v1/tasks/{task_id}', { path: { task_id: id }, signal }),
    taskProgress: (
      id: string,
      signal?: AbortSignal,
      query: Query<'/api/v1/tasks/{task_id}/progress'> = {},
    ) => call('get', '/api/v1/tasks/{task_id}/progress', { path: { task_id: id }, signal, query }),
    changeTaskMachine: (id: string, machineId: string) =>
      call('put', '/api/v1/tasks/{task_id}/machine', {
        path: { task_id: id },
        body: { machineId },
      }),
    changeTaskProject: (id: string, projectId: string | null) =>
      call('put', '/api/v1/tasks/{task_id}/project', {
        path: { task_id: id },
        body: { projectId },
      }),
    retryExecutions: (id: string, body: TaskRetryRequest) =>
      call('post', '/api/v1/tasks/{task_id}/retry-executions', {
        path: { task_id: id },
        body,
      }),
    taskInputs: (id: string, signal?: AbortSignal) =>
      call('get', '/api/v1/tasks/{task_id}/inputs', { path: { task_id: id }, signal }),
    taskCostEstimate: (body: GenerationInputs, signal?: AbortSignal) =>
      call('post', '/api/v1/tasks/cost-estimate', { body, signal }),
    createTask: (body: TaskCreate) => call('post', '/api/v1/tasks', { body }),
    cancelTask: (id: string) =>
      call('post', '/api/v1/tasks/{task_id}/cancel', { path: { task_id: id } }),
    /** 撤销对排队任务的取消。工作机领取过的任务返回 409。 */
    resumeTask: (id: string) =>
      call('post', '/api/v1/tasks/{task_id}/resume', { path: { task_id: id } }),
    deleteTask: (id: string) =>
      call('delete', '/api/v1/tasks/{task_id}', { path: { task_id: id } }),
    restoreTask: (id: string) =>
      call('post', '/api/v1/tasks/{task_id}/restore', { path: { task_id: id } }),
    machines: (signal?: AbortSignal) => call('get', '/api/v1/machines', { signal }),
    machine: (id: string, signal?: AbortSignal) =>
      call('get', '/api/v1/machines/{machine_id}', { path: { machine_id: id }, signal }),
    renameMachine: (id: string, name: string) =>
      call('patch', '/api/v1/machines/{machine_id}', { path: { machine_id: id }, body: { name } }),
    updateMachine: (id: string) =>
      call('put', '/api/v1/machines/{machine_id}/update', {
        path: { machine_id: id },
      }),
    saveConnection: (body: components['schemas']['ConnectionWrite'], id?: string) =>
      id
        ? call('put', '/api/v1/machines/{machine_id}/connection', {
            path: { machine_id: id },
            body,
          })
        : call('post', '/api/v1/machines/connections', { body }),
    importReference: (body: components['schemas']['ReferenceImport']) =>
      call('post', '/api/v1/workflows/from-connection', { body }),
    createMachine: (name: string) => call('post', '/api/v1/machines', { body: { name } }),
    machineLink: (code: string, signal?: AbortSignal) =>
      call('get', '/api/v1/machines/links/{code}', { path: { code }, signal }),
    approveMachineLink: (
      code: string,
      body: Options<Operation<'/api/v1/machines/links/{code}/approve', 'post'>>['body'],
    ) => call('post', '/api/v1/machines/links/{code}/approve', { path: { code }, body }),
    defaultMachine: (id: string) =>
      call('put', '/api/v1/machines/{machine_id}/default', { path: { machine_id: id } }),
    setMachinePaused: (id: string, paused: boolean) =>
      call('put', '/api/v1/machines/{machine_id}/pause', {
        path: { machine_id: id },
        body: { paused },
      }),
    rotateMachine: (id: string) =>
      call('post', '/api/v1/machines/{machine_id}/rotate', { path: { machine_id: id } }),
    revokeMachine: (id: string) =>
      call('delete', '/api/v1/machines/{machine_id}', { path: { machine_id: id } }),
    deleteMachine: (id: string) =>
      call('delete', '/api/v1/machines/{machine_id}/record', { path: { machine_id: id } }),
    artifacts: (query: Query<'/api/v1/artifacts'> = {}, signal?: AbortSignal) =>
      call('get', '/api/v1/artifacts', { query, signal }),
    deleteArtifact: (id: string) =>
      call('delete', '/api/v1/artifacts/{artifact_id}', { path: { artifact_id: id } }),
    restoreArtifact: (id: string) =>
      call('post', '/api/v1/artifacts/{artifact_id}/restore', { path: { artifact_id: id } }),
    executions: (query: Query<'/api/v1/executions'> = {}, signal?: AbortSignal) =>
      call('get', '/api/v1/executions', { query, signal }),
    execution: (id: string, signal?: AbortSignal) =>
      call('get', '/api/v1/executions/{execution_id}', { path: { execution_id: id }, signal }),
    deleteExecutionArtifacts: (id: string) =>
      call('delete', '/api/v1/executions/{execution_id}/artifacts', {
        path: { execution_id: id },
      }),
    restoreExecutionArtifacts: (id: string) =>
      call('post', '/api/v1/executions/{execution_id}/artifacts/restore', {
        path: { execution_id: id },
      }),
    /** 指定结果组封面。`frameMs` 是封面视频取哪一刻的画面，不传用首帧。 */
    setExecutionCover: (id: string, body: CoverUpdate) =>
      call('put', '/api/v1/executions/{execution_id}/cover', {
        path: { execution_id: id },
        body,
      }),
    replayExecution: (id: string, signal?: AbortSignal) =>
      call('get', '/api/v1/executions/{execution_id}/replay', {
        path: { execution_id: id },
        signal,
      }),
    works: (query: Query<'/api/v1/works'> = {}, signal?: AbortSignal) =>
      call('get', '/api/v1/works', { query, signal }),
    work: (id: string, signal?: AbortSignal) =>
      call('get', '/api/v1/works/{work_id}', {
        path: { work_id: id },
        signal,
      }),
    /** 作者随作品公开的参数字段和参考素材。 */
    workInputs: (id: string, signal?: AbortSignal) =>
      call('get', '/api/v1/works/{work_id}/inputs', {
        path: { work_id: id },
        signal,
      }),
    workArtifacts: (id: string, cursor?: string | null, signal?: AbortSignal) =>
      call('get', '/api/v1/works/{work_id}/artifacts', {
        path: { work_id: id },
        query: { cursor },
        signal,
      }),
    publishWork: (body: components['schemas']['WorkCreate']) =>
      call('post', '/api/v1/works', { body }),
    setWorkCover: (id: string, body: CoverUpdate) =>
      call('put', '/api/v1/works/{work_id}/cover', { path: { work_id: id }, body }),
    unpublishWork: (id: string) =>
      call('delete', '/api/v1/works/{work_id}', { path: { work_id: id } }),
    deleteWork: (id: string) =>
      call('post', '/api/v1/works/{work_id}/delete', { path: { work_id: id } }),
    restoreWork: (id: string) =>
      call('post', '/api/v1/works/{work_id}/restore', { path: { work_id: id } }),
    replayWork: (id: string, signal?: AbortSignal) =>
      call('get', '/api/v1/works/{work_id}/replay', {
        path: { work_id: id },
        signal,
      }),
  };
}
