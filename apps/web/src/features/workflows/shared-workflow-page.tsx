import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import { Button } from '@comfyshop/ui';
import { ApiError } from '@comfyshop/api-client';
import {
  useWorkflowDetail,
  useWorkflowPages,
  useWorkspace,
  workflowDetailOptions,
} from '../../app/use-workspace';
import { workflowPath } from '../../app/workflow-route';
import type { WorkflowRouteState } from '../../app/workflow-route';
import type { RequireAuth } from '../auth/login-dialog';
import WorkflowDialog from './workflow-dialog';

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
  const [params, setParams] = useSearchParams();
  const queries = useQueryClient();
  const { api, state } = useWorkspace();
  const workflow = useWorkflowDetail(workflowId ?? '');
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
  const source = deferred ?? overlay?.replaySource;
  function replayAfterSignIn({ workId }: { workId: string }) {
    setSignedInReplay({ workId, workflowId: workflowId ?? '' });
    // 作品弹框是由地址里的 `work` 打开的，载入参数后去掉它，切回「作品」时不会再弹出。
    if (params.has('work'))
      setParams(
        (prior) => {
          const next = new URLSearchParams(prior);
          next.delete('work');
          return next;
        },
        { replace: true, state: overlay, preventScrollReset: true },
      );
  }
  const replay = useQuery({
    queryKey: ['workflow-route-replay', state.userId, source],
    enabled: !!source && !!state.userId,
    queryFn: ({ signal }) => {
      if (!source) throw new Error('缺少重跑来源');
      return 'executionId' in source
        ? api.replayExecution(source.executionId, signal)
        : api.replayWork(source.workId, signal);
    },
    staleTime: Infinity,
    retry: false,
  });
  if (!workflow.data || (source && state.userId && replay.isPending)) {
    const unavailable = workflow.error instanceof ApiError && workflow.error.status === 404;
    const content = workflow.error ? (
      <div className="inline-status" role="alert">
        {workflow.error.message}
        {!unavailable && (
          <Button size="small" onClick={() => void workflow.refetch()}>
            重试
          </Button>
        )}
        {!state.user && unavailable && (
          <Button size="small" onClick={(event) => requireAuth(event.currentTarget)}>
            登录查看私有工作流
          </Button>
        )}
        <Button size="small" asChild>
          <Link to={overlay?.background ?? '/'} replace>
            返回列表
          </Link>
        </Button>
      </div>
    ) : (
      <div className="inline-status" role="status">
        正在读取工作流
      </div>
    );
    return content;
  }
  const initialReplay = replay.data?.workflow.id === workflowId ? replay.data : undefined;
  return (
    <WorkflowDialog
      key={state.userId ?? 'guest'}
      workflow={workflow.data}
      initialReplay={initialReplay}
      initialReplayError={source && replay.error ? replay.error.message : undefined}
      replayAfterSignIn={replayAfterSignIn}
      pages={overlay?.filters ? pages : undefined}
      onSelect={async (next, isCurrent) => {
        await queries.fetchQuery(workflowDetailOptions(api, state.userId, next.id));
        if (isCurrent())
          void navigate(workflowPath(next.id), {
            replace: true,
            state: overlay,
            preventScrollReset: true,
          });
      }}
      onClose={() => {
        if (overlay) void navigate(-1);
        else void navigate('/', { replace: true });
      }}
      restoreFocus={restoreFocus}
      requireAuth={requireAuth}
      notify={notify}
    />
  );
}
