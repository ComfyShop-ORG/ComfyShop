import type { Asset, InputValue } from '@comfyshop/api-client';
import type { InputPatch } from './form-values';
import type { ParameterRow } from './parameter-layout';

export function maskEditorFor(
  source: ParameterRow,
  visibleRows: ReadonlyMap<string, ParameterRow>,
  values: Record<string, InputValue>,
  sharedAssets: ReadonlyMap<string, Asset>,
  changeInputs: (patch: InputPatch) => void,
) {
  const binding = source.presentation?.mask;
  if (!binding || (binding.channelFieldId && values[binding.channelFieldId] !== 'red')) return;
  const mask = visibleRows.get(binding.fieldId);
  if (mask?.kind !== 'image' || mask.acceptedContentTypes?.includes('image/png') === false) return;
  const value = values[mask.id];
  const assetId = value && typeof value === 'object' ? value.assetId : null;
  return {
    nativeAlpha: !binding.channelFieldId,
    assetId,
    sharedAsset: assetId ? sharedAssets.get(assetId) : undefined,
    apply: (asset: Asset | null) =>
      changeInputs({ [mask.id]: asset ? { assetId: asset.id } : null }),
    replaceImage: (image: InputValue) => changeInputs({ [source.id]: image, [mask.id]: null }),
  };
}

export type MaskEditor = NonNullable<ReturnType<typeof maskEditorFor>>;
