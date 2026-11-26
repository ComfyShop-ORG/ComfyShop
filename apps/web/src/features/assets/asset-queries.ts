import { queryOptions, useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ApiClient, Asset, AuthSession } from '@comfyshop/api-client';
import { useWorkspace } from '../../app/use-workspace';
import { workspaceKey } from '../../app/workspace-scope';
import type { WorkspaceTarget } from '../../app/workspace-scope';
import { createRequestId } from '../../data/request-id';

type LibraryFilters = Pick<
  NonNullable<Parameters<ApiClient['assets']>[0]>,
  'kind' | 'search' | 'content_types' | 'project_id'
>;

const libraryKey = (userId: string | null, target?: WorkspaceTarget) =>
  ['asset-library', userId, ...workspaceKey(target)] as const;

export const assetUsageKey = (userId: string | null, target?: WorkspaceTarget) =>
  [...libraryKey(userId, target), 'usage'] as const;

export function useAssetUsage() {
  const { api, state, workspaceScope } = useWorkspace();
  return useQuery({
    queryKey: assetUsageKey(state.userId, workspaceScope),
    enabled: !!state.userId,
    refetchOnMount: 'always',
    refetchOnWindowFocus: 'always',
    queryFn: ({ signal }) => api.assetUsage(signal),
  });
}

export function assetQuery(
  api: ApiClient,
  userId: string | null,
  assetId: string | null,
  target?: WorkspaceTarget,
) {
  return queryOptions({
    queryKey: ['asset', userId, assetId, ...workspaceKey(target)],
    enabled: !!assetId,
    queryFn: ({ signal }) => api.asset(assetId!, signal),
  });
}

export function useLibraryAssets(filters: LibraryFilters) {
  const { api, state, workspaceScope } = useWorkspace();
  const queryKey = [...libraryKey(state.userId, workspaceScope), filters];
  const query = useInfiniteQuery({
    queryKey,
    enabled: !!state.userId,
    refetchOnMount: workspaceScope?.kind === 'team' ? 'always' : undefined,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => api.assets({ ...filters, cursor: pageParam }, signal),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
  });
  return { query, resetKey: JSON.stringify(queryKey) };
}

export function useAssetLibraryActions() {
  const {
    api,
    workspaceScope,
    state: { userId },
  } = useWorkspace();
  const queries = useQueryClient();
  const currentAccount = () => queries.getQueryData<AuthSession>(['session'])?.user?.id === userId;
  const refresh = () => queries.invalidateQueries({ queryKey: libraryKey(userId, workspaceScope) });

  async function update(asset: Asset) {
    if (!currentAccount()) return;
    queries.setQueryData(assetQuery(api, userId, asset.id, workspaceScope).queryKey, asset);
    await refresh();
  }

  return {
    upload: async (file: File) =>
      update(await api.uploadAsset(file, createRequestId(), undefined, { saveToLibrary: true })),
    save: async (id: string) => update(await api.saveAsset(id)),
    saveArtifact: async (id: string) => update(await api.saveArtifactAsAsset(id)),
    async remove(id: string) {
      await api.removeSavedAsset(id);
      if (!currentAccount()) return;
      queries.removeQueries({
        queryKey: assetQuery(api, userId, id, workspaceScope).queryKey,
        exact: true,
      });
      await refresh();
    },
  };
}
