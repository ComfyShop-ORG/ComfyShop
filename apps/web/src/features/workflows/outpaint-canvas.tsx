import { useRef, useState } from 'react';
import type { KeyboardEvent, PointerEvent } from 'react';
import 'konva/lib/shapes/Image.js';
import { Image as CanvasImage, Layer, Stage } from 'react-konva/lib/ReactKonvaCore.js';
import { FrameHandles, frameHandleAt } from './frame-handles';
import type { FrameHandle as Handle } from './frame-handles';
import { t } from '../../app/i18n';
import {
  CanvasZoom,
  canvasPoint,
  fitCanvas,
  transformCanvas,
  useCanvasViewport,
} from './canvas-viewport';
import type { CanvasPoint, CanvasView } from './canvas-viewport';
import { outpaintSize, placeOutpaintImage, samePadding } from './outpaint-fields';
import type { OutpaintPadding, OutpaintSide } from './outpaint-fields';

type Gesture = {
  handle?: Handle;
  pointerId: number;
  start: CanvasPoint;
  padding: OutpaintPadding;
  view: CanvasView;
};

function resizeFrame(
  padding: OutpaintPadding,
  handle: Handle,
  { x, y }: CanvasPoint,
  maximum: OutpaintPadding,
  step: number,
) {
  const next = { ...padding };
  const resize = (side: OutpaintSide, delta: number) =>
    Math.min(maximum[side], Math.max(0, Math.round((padding[side] + delta) / step) * step));
  if ('horizontal' in handle) {
    next[handle.horizontal] = resize(handle.horizontal, handle.horizontal === 'left' ? -x : x);
  }
  if ('vertical' in handle) {
    next[handle.vertical] = resize(handle.vertical, handle.vertical === 'top' ? -y : y);
  }
  return next;
}

function resizedView(
  { x, y, scale }: CanvasView,
  before: OutpaintPadding,
  after: OutpaintPadding,
): CanvasView {
  return {
    x: x + (before.left - after.left) * scale,
    y: y + (before.top - after.top) * scale,
    scale,
  };
}

export default function OutpaintCanvas({
  image,
  padding,
  maximum,
  step,
  onPreview,
  onChange,
}: {
  image: HTMLImageElement;
  padding: OutpaintPadding;
  maximum: OutpaintPadding;
  step: number;
  onPreview: (padding: OutpaintPadding | null) => void;
  onChange: (padding: OutpaintPadding, resized: boolean) => void;
}) {
  const [gesture, setGesture] = useState<Gesture | null>(null);
  const element = useRef<HTMLDivElement>(null);
  const viewport = useCanvasViewport(element, cancelEdit);
  const { size, camera } = viewport;
  const [placed, setPlaced] = useState<{
    view: CanvasView;
    padding: OutpaintPadding;
    size: typeof size;
    fits: boolean;
  }>();
  const { naturalWidth, naturalHeight } = image;
  const frame = outpaintSize(image, padding);
  const base =
    placed?.size === size &&
    (placed.fits || camera.scale > 1) &&
    samePadding(placed.padding, padding)
      ? placed.view
      : fitCanvas(size, frame);
  const view = gesture
    ? gesture.handle
      ? resizedView(gesture.view, gesture.padding, padding)
      : gesture.view
    : transformCanvas(base, camera);
  const movable = frame.width > naturalWidth || frame.height > naturalHeight;

  function retainView(nextView: CanvasView, padding: OutpaintPadding) {
    const next = outpaintSize(image, padding);
    const origin = canvasPoint(camera, nextView);
    const scale = nextView.scale / camera.scale;
    const inset = size.gutter / 2;
    const fits =
      origin.x >= inset &&
      origin.y >= inset &&
      origin.x + next.width * scale <= size.width - inset &&
      origin.y + next.height * scale <= size.height - inset;
    setPlaced({ view: { ...origin, scale }, size, padding, fits });
  }

  function cancelEdit() {
    if (!gesture) return;
    setGesture(null);
    onPreview(null);
  }

  function pointerDown(event: PointerEvent<HTMLDivElement>) {
    event.currentTarget.focus({ preventScroll: true });
    if (
      viewport.start(event) ||
      !event.isPrimary ||
      event.button !== 0 ||
      gesture ||
      view.scale <= 0
    )
      return;
    const handle = frameHandleAt(event);
    const start = viewport.localPoint(event);
    const origin = canvasPoint(view, start);
    if (
      !handle &&
      (!movable ||
        origin.x < padding.left ||
        origin.x > padding.left + naturalWidth ||
        origin.y < padding.top ||
        origin.y > padding.top + naturalHeight)
    )
      return;
    event.currentTarget.setPointerCapture(event.pointerId);
    setGesture({ handle, pointerId: event.pointerId, start, padding, view });
    onPreview(padding);
  }

  function paddingAt(event: PointerEvent<HTMLDivElement>, edit: Gesture) {
    const point = viewport.localPoint(event);
    const delta = {
      x: (point.x - edit.start.x) / edit.view.scale,
      y: (point.y - edit.start.y) / edit.view.scale,
    };
    return edit.handle
      ? resizeFrame(edit.padding, edit.handle, delta, maximum, step)
      : placeOutpaintImage(edit.padding, maximum, step, {
          x: edit.padding.left + delta.x,
          y: edit.padding.top + delta.y,
        });
  }

  function pointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!viewport.move(event) && gesture?.pointerId === event.pointerId)
      onPreview(paddingAt(event, gesture));
  }

  function commitResize(view: CanvasView, before: OutpaintPadding, next: OutpaintPadding) {
    retainView(resizedView(view, before, next), next);
    onChange(next, true);
  }

  function pointerUp(event: PointerEvent<HTMLDivElement>) {
    if (viewport.end(event) || gesture?.pointerId !== event.pointerId) return;
    const next = paddingAt(event, gesture);
    setGesture(null);
    if (gesture.handle) commitResize(gesture.view, gesture.padding, next);
    else {
      retainView(gesture.view, next);
      onChange(next, false);
    }
  }

  function pointerCancel(event: PointerEvent<HTMLDivElement>) {
    if (!viewport.end(event) && gesture?.pointerId === event.pointerId) cancelEdit();
  }

  function resizeWithKeys(event: KeyboardEvent<HTMLButtonElement>, handle: Handle) {
    const directions = {
      ArrowLeft: { x: -1, y: 0 },
      ArrowRight: { x: 1, y: 0 },
      ArrowUp: { x: 0, y: -1 },
      ArrowDown: { x: 0, y: 1 },
    };
    const direction = directions[event.key as keyof typeof directions];
    if (!direction || gesture || viewport.panning) return;
    event.preventDefault();
    event.stopPropagation();
    const delta = step * (event.shiftKey ? 4 : 1);
    const next = resizeFrame(
      padding,
      handle,
      { x: direction.x * delta, y: direction.y * delta },
      maximum,
      step,
    );
    commitResize(view, padding, next);
  }

  const frameStyle = {
    left: view.x,
    top: view.y,
    width: frame.width * view.scale,
    height: frame.height * view.scale,
  };
  const imageBox = {
    left: padding.left * view.scale,
    top: padding.top * view.scale,
    width: naturalWidth * view.scale,
    height: naturalHeight * view.scale,
  };
  const activeHandle = gesture?.handle;
  const horizontal = activeHandle && 'horizontal' in activeHandle ? activeHandle.horizontal : null;
  const vertical = activeHandle && 'vertical' in activeHandle ? activeHandle.vertical : null;
  const bands = [
    horizontal && {
      side: horizontal,
      left: horizontal === 'left' ? 0 : imageBox.left + imageBox.width,
      top: imageBox.top,
      width: padding[horizontal] * view.scale,
      height: imageBox.height,
    },
    vertical && {
      side: vertical,
      left: 0,
      top: vertical === 'top' ? 0 : imageBox.top + imageBox.height,
      width: frameStyle.width,
      height: padding[vertical] * view.scale,
    },
  ];

  return (
    <>
      <div
        className="canvas-editor-viewport outpaint-viewport"
        ref={element}
        tabIndex={0}
        role="group"
        aria-label={t('canvasView.label')}
        aria-keyshortcuts="+ - 0 Space"
        data-panning={viewport.panning}
        data-moving={!!gesture && !gesture.handle}
        data-resizing={!!activeHandle}
        {...viewport.keys}
        onPointerDown={pointerDown}
        onPointerMove={pointerMove}
        onPointerUp={pointerUp}
        onPointerCancel={pointerCancel}
        onLostPointerCapture={pointerCancel}
      >
        {view.scale > 0 && (
          <>
            <div className="outpaint-frame-fill" style={frameStyle} aria-hidden="true" />
            <div className="canvas-editor-stage" aria-hidden="true">
              <Stage width={size.width} height={size.height}>
                <Layer listening={false}>
                  <CanvasImage
                    image={image}
                    fill={size.background}
                    x={view.x + imageBox.left}
                    y={view.y + imageBox.top}
                    width={imageBox.width}
                    height={imageBox.height}
                  />
                </Layer>
              </Stage>
            </div>
            {movable && (
              <div
                className="outpaint-image-hit"
                style={{
                  ...imageBox,
                  left: view.x + imageBox.left,
                  top: view.y + imageBox.top,
                }}
                aria-hidden="true"
              />
            )}
            <div
              className="outpaint-frame"
              role="group"
              aria-label={t('outpaint.resizeFrame')}
              style={frameStyle}
            >
              {bands.map(
                (band) =>
                  band &&
                  band.width >= 64 &&
                  band.height >= 24 && (
                    <span
                      key={band.side}
                      className="outpaint-band"
                      aria-hidden="true"
                      style={{
                        left: band.left + band.width / 2,
                        top: band.top + band.height / 2,
                      }}
                    >
                      {t('outpaint.paddingPixels', padding[band.side])}
                    </span>
                  ),
              )}
              <FrameHandles onKeyDown={resizeWithKeys} />
            </div>
          </>
        )}
      </div>
      <CanvasZoom view={viewport} disabled={!!gesture} />
    </>
  );
}
