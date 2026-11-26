import type { Location } from 'react-router';
import type { InputValue, Replay } from '@comfyshop/api-client';
import type { WorkflowFilters } from '../domain/types';
import type { WorkspaceTarget } from './workspace-scope';

export type InpaintDraft = {
  key: string;
  userId: string;
  teamId?: string;
  workflowId: string;
  versionId: string;
  machineId: string;
  inputValues: Record<string, InputValue>;
};

export type WorkflowRouteState = {
  background: Location;
  filters?: WorkflowFilters;
  workspace?: WorkspaceTarget;
  projectId?: string;
  replaySource?: { executionId: string } | { workId: string };
  backSteps?: number;
  inpaintDraft?: InpaintDraft;
};

export function workflowPath(id: string, versionId?: string, view?: 'fullscreen' | 'dialog') {
  const path = '/workflows/' + encodeURIComponent(id);
  const params = new URLSearchParams();
  if (versionId) params.set('version', versionId);
  if (view) params.set('view', view);
  return params.size ? `${path}?${params}` : path;
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

export function publicTeamPath(id: string, tab?: 'works') {
  const path = '/teams/' + encodeURIComponent(id);
  return tab ? `${path}?${new URLSearchParams({ tab })}` : path;
}

export function workflowRouteState(location: Location) {
  const state = location.state as WorkflowRouteState | null;
  return location.pathname.startsWith('/workflows/') && state?.background ? state : null;
}

export function workflowReplaySource(replay?: Replay): WorkflowRouteState['replaySource'] {
  if (replay?.sourceExecutionId) return { executionId: replay.sourceExecutionId };
  if (replay?.sourceWorkId) return { workId: replay.sourceWorkId };
}

export function workflowOverlayState(
  background: Location,
  replay?: Replay,
  filters?: WorkflowFilters,
): WorkflowRouteState {
  return {
    background: { ...background, state: null },
    filters,
    replaySource: workflowReplaySource(replay),
  };
}
