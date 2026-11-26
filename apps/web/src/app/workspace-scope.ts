import { createContext } from 'react';
import { generatePath, matchPath } from 'react-router';
import type { ApiClient, Team } from '@comfyshop/api-client';

export type WorkspaceTarget = { kind: 'shared' | 'team'; id: string };

export const workspaceRoutes = {
  personal: '/workspace',
  shared: '/workspace/shared/:workspaceId',
  team: '/workspace/teams/:workspaceId',
} as const;

export const projectsRoute = '/projects';
export const sharedProjectsRoute = `${workspaceRoutes.shared}/projects`;

export function projectsPath(target?: WorkspaceTarget, projectId?: string) {
  const base = target?.kind === 'shared' ? workspacePath(target, 'projects') : projectsRoute;
  return projectId ? `${base}/${encodeURIComponent(projectId)}` : base;
}

export function matchProjectsPath(pathname: string) {
  return (
    matchPath(`${projectsRoute}/:projectId?`, pathname) ??
    matchPath(`${sharedProjectsRoute}/:projectId?`, pathname)
  );
}

export const ScopedWorkspace = createContext<{
  target: WorkspaceTarget;
  label: string;
  team?: Team;
  api: ApiClient;
} | null>(null);

export function workspaceKey(target?: WorkspaceTarget) {
  if (!target) return [];
  return target.kind === 'team' ? [{ workspaceTeam: target.id }] : [{ workspaceOwner: target.id }];
}

export function workspacePath(target?: WorkspaceTarget, tab = 'favorites') {
  const base =
    target?.kind === 'shared'
      ? generatePath(workspaceRoutes.shared, { workspaceId: encodeURIComponent(target.id) })
      : workspaceRoutes.personal;
  return `${base}/${tab}`;
}

export function workspaceTargetFromPath(pathname: string): WorkspaceTarget | undefined {
  for (const kind of ['team', 'shared'] as const) {
    const workspaceId = matchPath({ path: workspaceRoutes[kind], end: false }, pathname)?.params
      .workspaceId;
    if (workspaceId) {
      try {
        return { kind, id: decodeURIComponent(workspaceId) };
      } catch {
        return { kind, id: workspaceId };
      }
    }
  }
}
