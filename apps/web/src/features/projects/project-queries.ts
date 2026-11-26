import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ApiClient, Project } from '@comfyshop/api-client';
import { useWorkspace } from '../../app/use-workspace';
import { workspaceKey } from '../../app/workspace-scope';
import type { WorkspaceTarget } from '../../app/workspace-scope';

export const projectKey = (userId: string | null, target?: WorkspaceTarget) =>
  ['projects', userId, ...workspaceKey(target)] as const;

export const projectDetailKey = (
  userId: string | null,
  target: WorkspaceTarget | undefined,
  id?: string,
) => [...projectKey(userId, target), 'detail', id] as const;

export function useProject(id?: string, enabled = true) {
  const { api, state, workspaceScope } = useWorkspace();
  return useQuery({
    queryKey: projectDetailKey(state.userId, workspaceScope, id),
    enabled: !!state.userId && !!id && enabled,
    queryFn: ({ signal }) => api.project(id!, signal),
    retry: false,
  });
}

export function useProjectPages({
  search = '',
  enabled = true,
  archived = false,
}: { search?: string; enabled?: boolean; archived?: boolean } = {}) {
  const { api, state, workspaceScope } = useWorkspace();
  return useInfiniteQuery({
    queryKey: [...projectKey(state.userId, workspaceScope), 'list', search, archived],
    enabled: !!state.userId && enabled,
    staleTime: 0,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      api.projects({ cursor: pageParam, search, archived }, signal),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
  });
}

export function useProjectCache() {
  const { state, workspaceScope } = useWorkspace();
  const client = useQueryClient();
  const userId = state.userId;
  const refresh = () =>
    Promise.all([
      client.invalidateQueries({ queryKey: [...projectKey(userId, workspaceScope), 'list'] }),
      client.invalidateQueries({ queryKey: ['team-events', userId] }),
    ]);
  return {
    save(project: Project) {
      client.setQueryData(projectDetailKey(userId, workspaceScope, project.id), project);
      return refresh();
    },
    remove(id: string) {
      client.removeQueries({ queryKey: projectDetailKey(userId, workspaceScope, id), exact: true });
      return refresh();
    },
  };
}

export function useChangeProjectMaterial() {
  const { api } = useWorkspace();
  const client = useQueryClient();
  return async (...args: Parameters<ApiClient['changeProjectMaterial']>) => {
    await api.changeProjectMaterial(...args);
    const [, kind] = args;
    const key = kind === 'assets' ? 'asset-library' : 'workflows';
    await Promise.all(
      [key, 'team-events'].map((queryKey) => client.invalidateQueries({ queryKey: [queryKey] })),
    );
  };
}
