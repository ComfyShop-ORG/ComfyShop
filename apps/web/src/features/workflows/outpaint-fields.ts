import type { InputValue } from '@comfyshop/api-client';
import type { ParameterRow } from './parameter-layout';

export const outpaintSides = ['left', 'top', 'right', 'bottom'] as const;
export type OutpaintSide = (typeof outpaintSides)[number];
export type OutpaintPadding = Record<OutpaintSide, number>;

export function validPadding(value: number, maximum: number, step: number) {
  return Number.isSafeInteger(value) && value >= 0 && value <= maximum && value % step === 0;
}

function paddingField(field: ParameterRow | undefined, values: Record<string, InputValue>) {
  if (!field || field.kind !== 'integer' || field.integerAsString || field.maximum == null) return;
  const step = Number(field.step ?? 1);
  if (Number(field.minimum ?? 0) !== 0 || !Number.isSafeInteger(step) || step < 1) return;
  const maximum = Math.floor(Number(field.maximum) / step) * step;
  if (!Number.isSafeInteger(maximum) || maximum < 0) return;
  const value = values[field.id];
  return {
    id: field.id,
    label: field.displayName || field.label,
    maximum,
    step,
    value: typeof value === 'number' && validPadding(value, maximum, step) ? value : 0,
  };
}

export function outpaintEditorFor(
  image: ParameterRow,
  visibleRows: ReadonlyMap<string, ParameterRow>,
  values: Record<string, InputValue>,
  onApply: (patch: Record<string, number>) => void,
) {
  const mapping = image.presentation?.outpaint;
  if (!mapping) return;
  const [left, top, right, bottom] = outpaintSides.map((side) =>
    paddingField(visibleRows.get(mapping[side]), values),
  );
  if (!left || !top || !right || !bottom) return;
  const step = left.step;
  if ([top, right, bottom].some((field) => field.step !== step)) return;
  return { fields: { left, top, right, bottom }, step, onApply };
}

export type OutpaintEditor = NonNullable<ReturnType<typeof outpaintEditorFor>>;

export function outpaintSize(image: HTMLImageElement, padding: OutpaintPadding) {
  return {
    width: image.naturalWidth + padding.left + padding.right,
    height: image.naturalHeight + padding.top + padding.bottom,
  };
}

function clampImageOffset(
  offset: number,
  total: number,
  step: number,
  before: number,
  after: number,
) {
  return Math.min(total, before, Math.max(0, total - after, Math.round(offset / step) * step));
}

/** Reposition the original inside a fixed frame. With no offset, center it. */
export function placeOutpaintImage(
  padding: OutpaintPadding,
  maximum: OutpaintPadding,
  step: number,
  offset?: { x: number; y: number },
) {
  const horizontal = padding.left + padding.right;
  const vertical = padding.top + padding.bottom;
  const left = clampImageOffset(
    offset?.x ?? horizontal / 2,
    horizontal,
    step,
    maximum.left,
    maximum.right,
  );
  const top = clampImageOffset(
    offset?.y ?? vertical / 2,
    vertical,
    step,
    maximum.top,
    maximum.bottom,
  );
  return { left, top, right: horizontal - left, bottom: vertical - top };
}

export function samePadding(left: OutpaintPadding, right: OutpaintPadding) {
  return outpaintSides.every((side) => left[side] === right[side]);
}
