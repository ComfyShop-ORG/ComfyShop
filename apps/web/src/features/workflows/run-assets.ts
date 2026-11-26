import { t } from '../../app/i18n.ts';
import { useQueries } from '@tanstack/react-query';
import type { InputValue, WorkflowFormData } from '@comfyshop/api-client';
import { useWorkspace } from '../../app/use-workspace';
import { assetQuery } from '../assets/asset-queries';
import { runParameterState } from './run-parameter-state';

export function cropBounds(regions: WorkflowFormData['imageCrops'][string] | undefined) {
  if (!regions?.length) return null;
  return {
    width: Math.max(...regions.map(({ x, width }) => x + width)),
    height: Math.max(...regions.map(({ y, height }) => y + height)),
  };
}

/** 在主表单和本次参数弹框中校验当前选中的原图。 */
export function useRunParameters(
  form: WorkflowFormData | undefined,
  draft: Record<string, InputValue> | null,
  options?: Parameters<typeof runParameterState>[2],
) {
  const { api, state, workspaceScope } = useWorkspace();
  const parameters = runParameterState(form, draft, options);
  const visibleRows = new Map(
    [...parameters.groups.default, ...parameters.groups.advanced].map((row) => [row.id, row]),
  );
  const sharedAssets = new Map(form?.sharedAssets?.map((asset) => [asset.id, asset]));
  const crops = Object.entries(form?.imageCrops ?? {}).flatMap(([id, regions]) => {
    const value = parameters.values[id];
    const bounds = cropBounds(regions);
    return value && typeof value === 'object' && bounds
      ? [{ id, bounds, assetId: value.assetId, shared: sharedAssets.get(value.assetId) }]
      : [];
  });
  const assetIds = [
    ...new Set(crops.filter(({ shared }) => !shared).map(({ assetId }) => assetId)),
  ];
  const queries = useQueries({
    queries: assetIds.map((id) => assetQuery(api, state.userId, id, workspaceScope)),
  });
  const assets = new Map(assetIds.map((id, index) => [id, queries[index]]));
  let checkingCrops = false;
  for (const { id, bounds, assetId, shared } of crops) {
    const query = assets.get(assetId);
    const asset = shared ?? query?.data;
    if (!asset && query?.isPending) {
      checkingCrops = true;
      continue;
    }
    const width = asset?.media.width;
    const height = asset?.media.height;
    if (!width || !height) {
      parameters.issues.set(id, {
        kind: 'crop',
        message: t('runAssets.couldNotReadTheImageDimensions'),
      });
    } else if (width < bounds.width || height < bounds.height) {
      parameters.issues.set(id, {
        kind: 'crop',
        message: t('runAssets.theCropExtendsPastTheImage', bounds.width, bounds.height),
      });
    }
  }
  return { ...parameters, visibleRows, sharedAssets, checkingCrops };
}
