import { t } from '../../app/i18n.ts';
import { useLayoutEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router';
import { Button } from '@comfyshop/ui';
import { ApiError } from '@comfyshop/api-client';
import {
  useWorkflowDetail,
  useWorkflowPages,
  useWorkspace,
  workflowDetailOptions,
} from '../../app/use-workspace';
import { workspaceKey } from '../../app/workspace-scope';
import { workflowPath, workflowReplaySource } from '../../app/workflow-route';
import type { WorkflowRouteState } from '../../app/workflow-route';
import { clearResultParams, resultHistoryDepth } from '../../app/result-route';
import type { RequireAuth } from '../auth/login-dialog';
import WorkflowDialog from './workflow-dialog';
import type { WorkflowTab } from './workflow-dialog';

type VersionRequest = { locationKey: string; userId: string | null; versionId: string };

export default function SharedWorkflowPage({
  overlay,
  restoreFocus,
  requireAuth,
  notify,
}: {
  overlay?: WorkflowRouteState;
  restoreFocus: () => void;
  requireAuth: RequireAuth;
  notify: (message: string) => void;
}) {
  const { workflowId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const locationState = location.state as Partial<WorkflowRouteState> | null;
  const [params, setParams] = useSearchParams();
  const viewParam = params.get('view');
  const view = viewParam === 'fullscreen' || viewParam === 'dialog' ? viewParam : undefined;
  const preferFullscreen = document.documentElement.dataset.workflowFullscreen === 'on';
  const fullscreen = view ? view === 'fullscreen' : preferFullscreen;
  const queries = useQueryClient();
  const { api, state, workspaceScope } = useWorkspace();
  const [versionTab, setVersionTab] = useState<{
    workflowId: string;
    versionId: string;
    tab: WorkflowTab;
  }>();
  const versionRequest = useRef<VersionRequest | undefined>(undefined);
  const [pendingVersion, setPendingVersion] = useState<VersionRequest>();
  const pendingVersionId =
    pendingVersion?.locationKey === location.key && pendingVersion.userId === state.userId
      ? pendingVersion.versionId
      : undefined;
  useLayoutEffect(
    () => () => {
      versionRequest.current = undefined;
    },
    [location.key, state.userId],
  );
  const linkedId = params.get('work');
  const linked = useQuery({
    queryKey: ['works', 'linked', state.userId, linkedId, ...workspaceKey(workspaceScope)],
    enabled: !!linkedId && state.ready,
    queryFn: ({ signal }) => api.work(linkedId!, signal),
    retry: false,
  });
  const linkedWork = linked.data?.workflowId === workflowId ? linked.data : undefined;
  const versionId = linkedWork?.versionId ?? params.get('version') ?? undefined;
  const workflow = useWorkflowDetail(
    linkedId && linked.isPending ? '' : (workflowId ?? ''),
    versionId,
  );
  const versions = useQuery({
    queryKey: ['workflows', 'versions', state.userId, workflowId, ...workspaceKey(workspaceScope)],
    enabled: !!workflow.data,
    queryFn: ({ signal }) => api.workflowVersions(workflowId!, signal),
  });
  const currentVersionId =
    versions.data?.currentVersionId ?? (versionId ? undefined : workflow.data?.versionId);
  const { pages } = useWorkflowPages(overlay?.filters);
  // 访客点了作品的「载入参数」再登录：弹框按新身份重建，参数由这里读取后交给新弹框。
  // 只对这个工作流和登录后的那个账号有效，换了工作流或账号就不再载入。
  const [signedInReplay, setSignedInReplay] = useState<{
    workId: string;
    workflowId: string;
    userId?: string;
  }>();
  if (signedInReplay && !signedInReplay.userId && state.userId)
    setSignedInReplay({ ...signedInReplay, userId: state.userId });
  const deferred =
    signedInReplay &&
    signedInReplay.workflowId === workflowId &&
    (!signedInReplay.userId || signedInReplay.userId === state.userId)
      ? { workId: signedInReplay.workId }
      : undefined;
  const fromExecution = params.get('fromExecution');
  const fromWork = params.get('fromWork');
  const source =
    deferred ??
    locationState?.replaySource ??
    (fromExecution ? { executionId: fromExecution } : fromWork ? { workId: fromWork } : undefined);
  function showVersion(
    nextVersionId: string | undefined,
    routeState: Partial<WorkflowRouteState> | undefined = overlay,
  ) {
    setParams(
      (prior) => {
        const next = new URLSearchParams(prior);
        clearResultParams(next);
        next.delete('work');
        next.delete('fromExecution');
        next.delete('fromWork');
        // 关闭直链时保持同一个详情查询，让已载入的重跑草稿继续留在弹框中。
        if (nextVersionId) next.set('version', nextVersionId);
        else next.delete('version');
        return next;
      },
      { replace: true, state: routeState, preventScrollReset: true },
    );
  }
  function replayAfterSignIn({ workId }: { workId: string }) {
    setSignedInReplay({ workId, workflowId: workflowId ?? '' });
    if (linkedId) showVersion(versionId);
  }
  const replay = useQuery({
    queryKey: ['workflow-route-replay', state.userId, source, ...workspaceKey(workspaceScope)],
    enabled: !!source && !!state.userId,
    queryFn: ({ signal }) => {
      if (!source) throw new Error(t('sharedWorkflowPage.missingSourceForThisRerun'));
      return 'executionId' in source
        ? api.replayExecution(source.executionId, signal)
        : api.replayWork(source.workId, signal);
    },
    staleTime: Infinity,
    retry: false,
  });
  const initialReplay = replay.data?.workflow.id === workflowId ? replay.data : undefined;
  const detail = workflow.data ?? initialReplay?.workflow;
  if (!detail || (source && state.userId && replay.isPending)) {
    const unavailable = workflow.error instanceof ApiError && workflow.error.status === 404;
    const content = workflow.error ? (
      <div className="inline-status" role="alert">
        {workflow.error.message}
        {!unavailable && (
          <Button size="small" onClick={() => void workflow.refetch()}>
            {t('app.retry')}
          </Button>
        )}
        {!state.user && unavailable && (
          <Button size="small" onClick={(event) => requireAuth(event.currentTarget)}>
            {t('sharedWorkflowPage.signInToViewThisPrivate')}
          </Button>
        )}
        <Button size="small" asChild>
          <Link to={overlay?.background ?? '/'} replace>
            {t('sharedWorkflowPage.backToList')}
          </Link>
        </Button>
      </div>
    ) : (
      <div className="inline-status" role="status">
        {t('appRoutes.loadingWorkflow')}
      </div>
    );
    return content;
  }
  const detailId = detail.id;
  const displayedVersionId = initialReplay?.workflow.versionId ?? detail.versionId;
  async function selectVersion(nextVersionId: string, tab: WorkflowTab) {
    if (nextVersionId === displayedVersionId) {
      versionRequest.current = undefined;
      setPendingVersion(undefined);
      return;
    }
    const request = { locationKey: location.key, userId: state.userId, versionId: nextVersionId };
    versionRequest.current = request;
    setPendingVersion(request);
    const routeVersionId = nextVersionId === currentVersionId ? undefined : nextVersionId;
    try {
      // 先填好目的地址对应的查询，避免切换地址时用加载提示替换整个弹框。
      await queries.fetchQuery(
        workflowDetailOptions(api, state.userId, detailId, routeVersionId, workspaceScope),
      );
      if (versionRequest.current !== request) return;
      setSignedInReplay(undefined);
      setVersionTab({ workflowId: detailId, versionId: nextVersionId, tab });
      // 新地址生效前继续以待切换版本为基准计算下一次按键。
      showVersion(routeVersionId, overlay && { ...overlay, replaySource: undefined });
    } catch (error) {
      if (versionRequest.current !== request) return;
      versionRequest.current = undefined;
      setPendingVersion(undefined);
      notify(
        error instanceof Error
          ? error.message
          : t('sharedWorkflowPage.couldNotLoadTheWorkflowVersion'),
      );
    }
  }
  const edit = locationState?.inpaintDraft;
  const initialTab = params.has('result')
    ? 'results'
    : !linkedWork &&
        versionTab?.workflowId === detail.id &&
        versionTab.versionId === detail.versionId
      ? versionTab.tab
      : undefined;
  return (
    <WorkflowDialog
      key={state.userId ?? 'guest'}
      workflow={detail}
      fullscreen={fullscreen}
      onToggleFullscreen={() => {
        const next = new URLSearchParams(params);
        if (!fullscreen) next.set('view', 'fullscreen');
        else if (preferFullscreen) next.set('view', 'dialog');
        else next.delete('view');
        setParams(next, { replace: true, state: locationState, preventScrollReset: true });
      }}
      currentVersionId={currentVersionId}
      versions={versions.data?.items ?? []}
      pendingVersionId={pendingVersionId}
      linkedWork={linkedWork}
      onLinkedWorkClose={() => showVersion(versionId)}
      onVersionChange={(nextVersionId, tab) => void selectVersion(nextVersionId, tab)}
      initialTab={initialTab}
      initialReplay={initialReplay}
      initialInpaint={
        edit &&
        !source &&
        edit.workflowId === detail.id &&
        edit.versionId === displayedVersionId &&
        edit.userId === state.userId &&
        edit.teamId === workspaceScope?.id
          ? edit
          : undefined
      }
      projectId={overlay?.projectId}
      onReplayChange={(next) => {
        const replaySource = workflowReplaySource(next ?? undefined);
        if (replaySource && next) {
          queries.setQueryData(
            ['workflow-route-replay', state.userId, replaySource, ...workspaceKey(workspaceScope)],
            next,
          );
          queries.setQueryData(
            workflowDetailOptions(api, state.userId, next.workflow.id, next.workflow.versionId)
              .queryKey,
            next.workflow,
          );
        }
        setSignedInReplay(undefined);
        showVersion(next?.workflow.versionId ?? versionId, {
          ...overlay,
          replaySource,
          inpaintDraft: undefined,
          backSteps: (overlay?.backSteps ?? 1) + resultHistoryDepth(location),
        });
      }}
      initialReplayError={source && replay.error ? replay.error.message : undefined}
      replayAfterSignIn={replayAfterSignIn}
      pages={overlay?.filters ? pages : undefined}
      onSelect={async (next, isCurrent) => {
        await queries.fetchQuery(
          workflowDetailOptions(api, state.userId, next.id, undefined, workspaceScope),
        );
        if (isCurrent())
          void navigate(workflowPath(next.id, undefined, view), {
            replace: true,
            state: overlay,
            preventScrollReset: true,
          });
      }}
      onClose={() => {
        versionRequest.current = undefined;
        if (overlay) void navigate(-(overlay.backSteps ?? 1));
        else void navigate('/', { replace: true });
      }}
      restoreFocus={restoreFocus}
      requireAuth={requireAuth}
      notify={notify}
    />
  );
}
