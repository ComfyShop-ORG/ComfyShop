import type { Asset, InputValue } from '@comfyshop/api-client';
import { pixelField } from './crop-box';
import type { Box, ImageSize } from './crop-box';
import type { FrameHandle } from './frame-handles';
import type { ParameterRow } from './parameter-layout';
import type { InputPatch } from './form-values';

const rotations = ['none', '90 degrees', '180 degrees', '270 degrees'] as const;
export type Placement = { x: number; y: number; scale: number; turn: number };
export type PlacementSource = {
  field: string;
  assetId: string | null;
  shared?: Asset;
  alpha: boolean;
  initial: Placement;
  xMax: number;
  yMax: number;
  scale?: { id: string; min: number; max: number; step: number };
  rotation?: string;
  xId: string;
  yId: string;
};

export function placementEditorFor(
  row: ParameterRow,
  visible: ReadonlyMap<string, ParameterRow>,
  values: Record<string, InputValue>,
  shared: ReadonlyMap<string, Asset>,
  apply: (patch: InputPatch) => void,
) {
  if (!row.presentation?.layers?.length) return;
  const layers: PlacementSource[] = [];
  for (const field of row.presentation.layers) {
    if (values[field.resize] !== false) return;
    const x = pixelField(visible.get(field.x), values[field.x], 0);
    const y = pixelField(visible.get(field.y), values[field.y], 0);
    const source = visible.get(field.image);
    const scale = field.scale ? values[field.scale] : 1;
    const rotation = field.rotation ? values[field.rotation] : 'none';
    const turn = rotations.findIndex((value) => value === rotation);
    if (
      !x ||
      !y ||
      !source ||
      typeof scale !== 'number' ||
      !Number.isFinite(scale) ||
      scale <= 0 ||
      turn < 0
    )
      return;
    const value = values[field.image];
    const assetId = value && typeof value === 'object' ? value.assetId : null;
    const size = field.scale ? visible.get(field.scale) : undefined;
    const scaleControl =
      size && size.kind === 'number'
        ? {
            id: size.id,
            min: Number(size.minimum),
            max: Number(size.maximum),
            step: Number(size.step),
          }
        : undefined;
    if (
      scaleControl &&
      !(scaleControl.min > 0 && scaleControl.max >= scaleControl.min && scaleControl.step > 0)
    )
      return;
    const angle = field.rotation ? visible.get(field.rotation) : undefined;
    layers.push({
      field: field.x,
      assetId,
      shared: assetId ? shared.get(assetId) : undefined,
      alpha: field.alpha,
      initial: { x: x.value, y: y.value, scale, turn },
      xMax: x.maximum,
      yMax: y.maximum,
      scale: scaleControl,
      rotation:
        angle && rotations.every((entry) => angle.choices.includes(entry)) ? angle.id : undefined,
      xId: x.id,
      yId: y.id,
    });
  }
  return {
    layers,
    apply(placements: Placement[]) {
      const patch: InputPatch = {};
      layers.forEach((layer, i) => {
        const p = placements[i];
        patch[layer.xId] = p.x;
        patch[layer.yId] = p.y;
        if (layer.scale) patch[layer.scale.id] = p.scale;
        if (layer.rotation) patch[layer.rotation] = rotations[p.turn];
      });
      apply(patch);
    },
  };
}
export type PlacementEditor = NonNullable<ReturnType<typeof placementEditorFor>>;

// ImageScaleBy uses Python round(), including ties to even.
function scaledPixels(value: number) {
  const floor = Math.floor(value);
  return Math.max(1, value - floor === 0.5 ? floor + (floor % 2) : Math.round(value));
}
export function layerBox(p: Placement, image: ImageSize): Box {
  const w = scaledPixels(image.width * p.scale),
    h = scaledPixels(image.height * p.scale);
  return { x: p.x, y: p.y, width: p.turn % 2 ? h : w, height: p.turn % 2 ? w : h };
}

export function moveLayer(
  p: Placement,
  x: number,
  y: number,
  layer: PlacementSource,
  base: ImageSize,
) {
  return {
    ...p,
    x: Math.max(0, Math.min(layer.xMax, base.width - 1, Math.round(x))),
    y: Math.max(0, Math.min(layer.yMax, base.height - 1, Math.round(y))),
  };
}

export function dragLayer(
  p: Placement,
  layer: PlacementSource,
  image: ImageSize,
  base: ImageSize,
  handle: FrameHandle | undefined,
  dx: number,
  dy: number,
): Placement {
  if (!handle) return moveLayer(p, p.x + dx, p.y + dy, layer, base);
  if (!layer.scale) return p;
  const before = layerBox(p, image);
  const hx = 'horizontal' in handle ? (handle.horizontal === 'left' ? -1 : 1) : 0;
  const hy = 'vertical' in handle ? (handle.vertical === 'top' ? -1 : 1) : 0;
  const delta =
    hx && (!hy || Math.abs(dx / before.width) >= Math.abs(dy / before.height))
      ? (hx * dx) / before.width
      : (hy * dy) / before.height;
  const { min, max, step } = layer.scale;
  const scale = Number(
    Math.min(
      max,
      Math.max(min, min + Math.round((p.scale * (1 + delta) - min) / step) * step),
    ).toFixed(8),
  );
  const next = { ...p, scale };
  const after = layerBox(next, image);
  return moveLayer(
    next,
    p.x + ((before.width - after.width) * (1 - hx)) / 2,
    p.y + ((before.height - after.height) * (1 - hy)) / 2,
    layer,
    base,
  );
}
