import { queryOptions } from '@tanstack/react-query';
import type { ApiClient, ReplaySource } from '@comfyshop/api-client';

export function workflowFormQuery(
  api: ApiClient,
  key: readonly [string, string | null, string, string],
  machineId: string,
  replaySource?: ReplaySource,
) {
  const [, , workflowId, versionId] = key;
  return queryOptions({
    queryKey: [...key, machineId, replaySource],
    queryFn: ({ signal }) =>
      api.workflowForm(workflowId, versionId, machineId, signal, replaySource),
    retry: false,
  });
}
