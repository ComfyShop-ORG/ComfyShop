import type { CanvasPoint } from './canvas-viewport';

export type SelectionMode = 'add' | 'subtract';
export type MaskTool = 'paint' | 'erase' | SelectionMode;
export type MaskStroke = { tool: 'paint' | 'erase'; diameter: number; points: CanvasPoint[] };
export type MaskRegion = { mode: SelectionMode; region: HTMLCanvasElement };
export type MaskChange = MaskStroke | MaskRegion | 'clear';

function maskContext(canvas: HTMLCanvasElement) {
  const context = canvas.getContext('2d', { willReadFrequently: true });
  if (!context) throw new Error('Canvas unavailable');
  return context;
}

export function maskBitmap(image: HTMLImageElement, scale: number) {
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
  canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
  return canvas;
}

export function regionBitmap(width: number, height: number, alpha: Uint8Array) {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const context = maskContext(canvas);
  const pixels = context.createImageData(width, height);
  for (let i = 0; i < alpha.length; i++) pixels.data[i * 4 + 3] = alpha[i];
  context.putImageData(pixels, 0, 0);
  return canvas;
}

export function paintMaskSegment(
  context: CanvasRenderingContext2D,
  stroke: MaskStroke,
  color: string,
  to: CanvasPoint,
  from?: CanvasPoint,
) {
  context.globalCompositeOperation = stroke.tool === 'erase' ? 'destination-out' : 'source-over';
  context.beginPath();
  if (from && (from.x !== to.x || from.y !== to.y)) {
    context.lineWidth = stroke.diameter;
    context.lineCap = 'round';
    context.strokeStyle = color;
    context.moveTo(from.x, from.y);
    context.lineTo(to.x, to.y);
    context.stroke();
  } else {
    context.fillStyle = color;
    context.arc(to.x, to.y, stroke.diameter / 2, 0, 2 * Math.PI);
    context.fill();
  }
}

/** Preview ink and exported pixels use the same coordinates and brush geometry. */
export function renderMask(
  canvas: HTMLCanvasElement,
  image: HTMLImageElement,
  original: HTMLImageElement | undefined,
  changes: readonly MaskChange[],
  color: string,
  sourceAlpha = false,
) {
  const context = maskContext(canvas);
  const { width, height } = canvas;
  const clear = changes.lastIndexOf('clear');
  context.resetTransform();
  context.clearRect(0, 0, width, height);
  context.globalCompositeOperation = 'source-over';
  if (original && clear === -1) {
    context.drawImage(original, 0, 0, width, height);
    const pixels = context.getImageData(0, 0, width, height);
    for (let offset = 0; offset < pixels.data.length; offset += 4)
      pixels.data[offset + 3] = sourceAlpha ? 255 - pixels.data[offset + 3] : pixels.data[offset];
    context.putImageData(pixels, 0, 0);
  }
  context.setTransform(width / image.naturalWidth, 0, 0, height / image.naturalHeight, 0, 0);
  for (const stroke of changes.slice(clear + 1)) {
    if (stroke === 'clear') continue;
    if ('region' in stroke) {
      context.globalCompositeOperation = stroke.mode === 'add' ? 'source-over' : 'destination-out';
      context.imageSmoothingEnabled = false;
      context.drawImage(stroke.region, 0, 0, image.naturalWidth, image.naturalHeight);
    } else {
      stroke.points.forEach((point, index) =>
        paintMaskSegment(context, stroke, color, point, stroke.points[index - 1]),
      );
    }
  }
  context.globalCompositeOperation = 'source-in';
  context.fillStyle = color;
  context.fillRect(0, 0, image.naturalWidth, image.naturalHeight);
  context.globalCompositeOperation = 'source-over';
  context.imageSmoothingEnabled = true;
  return context;
}

export async function maskFile(
  image: HTMLImageElement,
  original: HTMLImageElement | undefined,
  changes: readonly MaskChange[],
  sourceAlpha = false,
) {
  const canvas = maskBitmap(image, 1);
  // The exact-size PNG encodes paint in RGB for the work machine's red channel.
  try {
    const context = renderMask(canvas, image, original, changes, 'white', sourceAlpha);
    context.resetTransform();
    context.globalCompositeOperation = 'destination-over';
    context.fillStyle = 'black';
    context.fillRect(0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'));
    if (!blob) throw new Error('Mask export failed');
    return new File([blob], 'mask.png', { type: 'image/png' });
  } finally {
    canvas.width = canvas.height = 1;
  }
}
