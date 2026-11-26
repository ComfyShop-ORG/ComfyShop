import type { InputValue } from '@comfyshop/api-client';
import type { FrameHandle } from './frame-handles';
import type { ParameterRow } from './parameter-layout';

export type Box = { x: number; y: number; width: number; height: number };
export type ImageSize = Pick<Box, 'width' | 'height'>;
export const boxKeys = ['x', 'y', 'width', 'height'] as const;

export function pixelField(
  row: ParameterRow | undefined,
  value: InputValue | undefined,
  minimum: number,
) {
  if (
    row?.kind !== 'integer' ||
    row.integerAsString ||
    Number(row.minimum ?? minimum) !== minimum ||
    Number(row.step ?? 1) !== 1 ||
    typeof value !== 'number' ||
    !Number.isSafeInteger(value)
  )
    return;
  const maximum = Number(row.maximum ?? Number.MAX_SAFE_INTEGER);
  if (!Number.isSafeInteger(maximum) || maximum < minimum || value < minimum || value > maximum)
    return;
  return { id: row.id, value, maximum };
}

export function cropEditorFor(
  row: ParameterRow,
  visible: ReadonlyMap<string, ParameterRow>,
  values: Record<string, InputValue>,
  changeInputs: (patch: Record<string, number>) => void,
) {
  const mapping = row.presentation?.crop;
  if (!mapping) return;
  const [x, y, width, height] = boxKeys.map((key) =>
    pixelField(
      visible.get(mapping[key]),
      values[mapping[key]],
      key === 'width' || key === 'height' ? 1 : 0,
    ),
  );
  if (!x || !y || !width || !height) return;
  return {
    initial: { x: x.value, y: y.value, width: width.value, height: height.value },
    maximum: { x: x.maximum, y: y.maximum, width: width.maximum, height: height.maximum },
    apply: (box: Box) =>
      changeInputs(Object.fromEntries(boxKeys.map((key) => [mapping[key], box[key]]))),
  };
}
export type CropEditor = NonNullable<ReturnType<typeof cropEditorFor>>;

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, Math.round(value)));

export function clipCrop(box: Box, image: ImageSize, max: Box): Box {
  const x = clamp(box.x, 0, Math.min(max.x, image.width - 1));
  const y = clamp(box.y, 0, Math.min(max.y, image.height - 1));
  return {
    x,
    y,
    width: clamp(box.width, 1, Math.min(max.width, image.width - x)),
    height: clamp(box.height, 1, Math.min(max.height, image.height - y)),
  };
}

export function moveCrop(box: Box, x: number, y: number, image: ImageSize, max: Box): Box {
  return {
    ...box,
    x: clamp(x, 0, Math.min(max.x, image.width - box.width)),
    y: clamp(y, 0, Math.min(max.y, image.height - box.height)),
  };
}

export function cropForRatio(current: Box, image: ImageSize, max: Box, ratio: number): Box {
  const width = Math.max(
    1,
    Math.min(max.width, image.width, Math.round(Math.min(max.height, image.height) * ratio)),
  );
  const height = clamp(width / ratio, 1, Math.min(max.height, image.height));
  return moveCrop(
    { ...current, width, height },
    current.x + (current.width - width) / 2,
    current.y + (current.height - height) / 2,
    image,
    max,
  );
}

export function dragCrop(
  box: Box,
  handle: FrameHandle | undefined,
  dx: number,
  dy: number,
  image: ImageSize,
  max: Box,
  ratio: number | null,
): Box {
  if (!handle) return moveCrop(box, box.x + dx, box.y + dy, image, max);
  const hx = 'horizontal' in handle ? (handle.horizontal === 'left' ? -1 : 1) : 0;
  const hy = 'vertical' in handle ? (handle.vertical === 'top' ? -1 : 1) : 0;
  const anchorX = box.x + ((1 - hx) * box.width) / 2;
  const anchorY = box.y + ((1 - hy) * box.height) / 2;
  const available = (anchor: number, side: number, end: number) =>
    side < 0 ? anchor : side > 0 ? end - anchor : 2 * Math.min(anchor, end - anchor);
  const maxW = Math.min(max.width, available(anchorX, hx, image.width));
  const maxH = Math.min(max.height, available(anchorY, hy, image.height));
  let width = clamp(box.width + hx * dx, 1, maxW);
  let height = clamp(box.height + hy * dy, 1, maxH);
  if (ratio) {
    const requested = hx && (!hy || Math.abs(dx) >= Math.abs(dy * ratio)) ? width : height * ratio;
    width = clamp(requested, 1, Math.max(1, Math.min(maxW, Math.round(maxH * ratio))));
    height = clamp(width / ratio, 1, maxH);
  }
  return moveCrop(
    { ...box, width, height },
    anchorX - ((1 - hx) * width) / 2,
    anchorY - ((1 - hy) * height) / 2,
    image,
    max,
  );
}
