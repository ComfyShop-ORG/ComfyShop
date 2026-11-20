import type { Location } from 'react-router';
import type { Replay } from '@comfyshop/api-client';
import type { WorkflowFilters } from '../domain/types';

export type WorkflowRouteState = {
  background: Location;
  filters?: WorkflowFilters;
  replaySource?: { executionId: string } | { workId: string };
};

export function workflowPath(id: string, versionId?: string) {
  const path = '/workflows/' + encodeURIComponent(id);
  return versionId ? `${path}?${new URLSearchParams({ version: versionId })}` : path;
}

/** 作品的分享地址：打开来源工作流并直接展示这件作品。 */
export function workLink(work: { id: string; workflowId: string }) {
  const url = new URL(workflowPath(work.workflowId), window.location.origin);
  url.searchParams.set('work', work.id);
  return url.href;
}

export function authorPath(name: string) {
  return '/authors/' + encodeURIComponent(name);
}

export function workflowRouteState(location: Location) {
  return location.pathname.startsWith('/workflows/')
    ? (location.state as WorkflowRouteState | null)
    : null;
}

export function workflowOverlayState(
  background: Location,
  replay?: Replay,
  filters?: WorkflowFilters,
): WorkflowRouteState {
  const replaySource = replay?.sourceExecutionId
    ? { executionId: replay.sourceExecutionId }
    : replay?.sourceWorkId
      ? { workId: replay.sourceWorkId }
      : undefined;
  return { background: { ...background, state: null }, filters, replaySource };
}
