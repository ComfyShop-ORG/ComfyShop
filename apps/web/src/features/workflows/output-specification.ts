import { t } from '../../app/i18n.ts';
import type { InputValue, WorkflowForm } from '@comfyshop/api-client';

/** 与 ComfyUI 的 Python round 一样，正好位于两档中间时取偶数档。 */
function roundToEven(value: number) {
  const lower = Math.floor(value);
  return value - lower === 0.5 && lower % 2 === 0 ? lower : Math.round(value);
}

function aspect(value: InputValue) {
  return typeof value === 'string' ? /^([1-9]\d*):([1-9]\d*)(?:\s|$)/.exec(value) : null;
}

/** ResolutionSelector 使用 1024² 像素作为一个 MP。 */
export function ratioDimensions(
  ratio: InputValue,
  megapixels: InputValue,
  multiple: InputValue,
  roundTo?: number | null,
  latentMultiple?: number | null,
  modelMultiple?: number | null,
): [number, number] | null {
  const parts = aspect(ratio);
  if (
    !parts ||
    typeof megapixels !== 'number' ||
    !Number.isFinite(megapixels) ||
    megapixels <= 0 ||
    typeof multiple !== 'number' ||
    !Number.isSafeInteger(multiple) ||
    multiple <= 0
  )
    return null;
  const width = Number(parts[1]);
  const height = Number(parts[2]);
  const scale = Math.sqrt((megapixels * 1024 * 1024) / (width * height));
  const step = multiple;
  function dimension(size: number) {
    const selected = roundToEven((size * scale) / step) * step;
    const rounded = roundTo ? roundToEven(selected / roundTo) * roundTo : selected;
    const latent = latentMultiple ? Math.floor(rounded / latentMultiple) * latentMultiple : rounded;
    return modelMultiple ? roundToEven(latent / modelMultiple) * modelMultiple : latent;
  }
  const result = [dimension(width), dimension(height)] as const;
  return result.every((size) => Number.isSafeInteger(size) && size > 0) ? [...result] : null;
}

export function promptWithoutAspect(text: string) {
  return text.replace(/^Aspect ratio:[ \t]*\d+:\d+[ \t]*(?:\r?\n|$)/i, '');
}

export function promptWithAspect(text: InputValue, ratio: InputValue): InputValue {
  const parts = aspect(ratio);
  return parts && typeof text === 'string'
    ? `Aspect ratio: ${parts[1]}:${parts[2]}\n${promptWithoutAspect(text)}`
    : text;
}

export function referenceFrameCount(
  seconds: InputValue,
  { framesPerSecond, minimumFrames, frameStep }: WorkflowForm['referenceTimelines'][number],
) {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds)) return null;
  const count = Math.max(minimumFrames, roundToEven(seconds * framesPerSecond));
  if (!Number.isSafeInteger(count)) return null;
  return count + ((frameStep - ((count - minimumFrames) % frameStep)) % frameStep);
}

export function referenceTimeIssue(seconds: InputValue, count: number, fps: number) {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds))
    return t('outputSpecification.enterAReferenceFrameTimestamp');
  const frame = roundToEven(seconds * fps);
  return frame < -count || frame >= count
    ? t('outputSpecification.timestampFallsOutsideTheClipThe', ((count - 1) / fps).toFixed(2))
    : null;
}
