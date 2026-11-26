import { queryOptions } from '@tanstack/react-query';
import type { ApiClient, ReplaySource } from '@comfyshop/api-client';

export function workflowFormQuery(
  api: ApiClient,
  key: readonly [string, string | null, string, string, ...unknown[]],
  machineId: string,
  replaySource?: ReplaySource,
  platformManaged = false,
) {
  const [, , workflowId, versionId] = key;
  return queryOptions({
    queryKey: [...key, machineId, replaySource],
    queryFn: ({ signal }) =>
      platformManaged
        ? api.serviceWorkflowForm(workflowId, versionId, signal, replaySource)
        : api.workflowForm(workflowId, versionId, machineId, signal, replaySource),
    retry: false,
  });
}
