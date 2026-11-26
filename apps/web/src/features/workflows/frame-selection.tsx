import { useRef } from 'react';
import type { CSSProperties, KeyboardEvent, PointerEvent, ReactNode } from 'react';
import 'konva/lib/shapes/Image.js';
import { Image as CanvasImage, Layer, Stage } from 'react-konva/lib/ReactKonvaCore.js';
import { size as tokens } from '@comfyshop/tokens';
import { t } from '../../app/i18n';
import {
  CanvasZoom,
  canvasPoint,
  fitCanvas,
  transformCanvas,
  useCanvasViewport,
} from './canvas-viewport';
import type { CanvasPoint } from './canvas-viewport';
import { FrameHandles, frameHandleAt } from './frame-handles';
import type { FrameHandle } from './frame-handles';
import type { Box } from './crop-box';

/** All edits use deltas from pointer-down in original pixels, including when zoomed. */
export default function FrameSelection({
  image,
  box,
  shade,
  handles = true,
  onDrag,
  onCancel,
  onPick,
  children,
}: {
  image: HTMLImageElement;
  box: Box;
  shade?: boolean;
  handles?: boolean;
  onDrag: (handle: FrameHandle | undefined, delta: CanvasPoint, commit: boolean) => void;
  onCancel: () => void;
  onPick?: (point: CanvasPoint) => boolean;
  children?: ReactNode;
}) {
  const element = useRef<HTMLDivElement>(null);
  const gesture = useRef<{ id: number; start: CanvasPoint; handle?: FrameHandle } | null>(null);
  function cancel() {
    if (gesture.current) {
      gesture.current = null;
      onCancel();
    }
  }
  const viewport = useCanvasViewport(element, cancel);
  const { size } = viewport;
  const imageSize = { width: image.naturalWidth, height: image.naturalHeight };
  const view = transformCanvas(fitCanvas(size, imageSize), viewport.camera);
  const point = (event: PointerEvent<HTMLDivElement>) =>
    canvasPoint(view, viewport.localPoint(event));
  function start(event: PointerEvent<HTMLDivElement>) {
    event.currentTarget.focus({ preventScroll: true });
    if (viewport.start(event) || !event.isPrimary || event.button !== 0 || !view.scale) return;
    const handle = frameHandleAt(event);
    const p = point(event);
    const picked = !handle && onPick?.(p);
    if (
      !handle &&
      !picked &&
      (p.x < box.x || p.x > box.x + box.width || p.y < box.y || p.y > box.y + box.height)
    )
      return;
    event.currentTarget.setPointerCapture(event.pointerId);
    gesture.current = { id: event.pointerId, start: p, handle };
  }
  function drag(event: PointerEvent<HTMLDivElement>, commit: boolean) {
    const edit = gesture.current;
    if ((commit ? viewport.end(event) : viewport.move(event)) || edit?.id !== event.pointerId)
      return;
    const p = point(event);
    if (commit) gesture.current = null;
    onDrag(edit.handle, { x: p.x - edit.start.x, y: p.y - edit.start.y }, commit);
  }
  function release(event: PointerEvent<HTMLDivElement>) {
    viewport.end(event);
    if (gesture.current?.id === event.pointerId) cancel();
  }
  function nudge(event: KeyboardEvent, handle?: FrameHandle) {
    const keys: Record<string, [number, number]> = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    };
    const delta = keys[event.key];
    if (!delta || gesture.current) return;
    event.preventDefault();
    event.stopPropagation();
    const step = event.shiftKey ? 10 : 1;
    onDrag(handle, { x: delta[0] * step, y: delta[1] * step }, true);
  }
  const compact =
    Math.min(box.width, box.height) * view.scale < 2 * Number.parseFloat(tokens.touch);
  const frame: CSSProperties = {
    left: view.x + box.x * view.scale,
    top: view.y + box.y * view.scale,
    width: box.width * view.scale,
    height: box.height * view.scale,
  };
  return (
    <>
      <div
        className="canvas-editor-viewport"
        tabIndex={0}
        role="group"
        aria-label={t('canvasView.label')}
        ref={element}
        data-panning={viewport.panning}
        {...viewport.keys}
        onKeyDown={(event) => {
          viewport.keys.onKeyDown(event);
          if (event.target === event.currentTarget) nudge(event);
        }}
        onPointerDown={start}
        onPointerMove={(event) => drag(event, false)}
        onPointerUp={(event) => drag(event, true)}
        onPointerCancel={release}
        onLostPointerCapture={release}
      >
        {view.scale > 0 && (
          <>
            <div className="canvas-editor-stage" aria-hidden="true">
              <Stage width={size.width} height={size.height}>
                <Layer
                  listening={false}
                  x={view.x}
                  y={view.y}
                  scaleX={view.scale}
                  scaleY={view.scale}
                  clipX={0}
                  clipY={0}
                  clipWidth={imageSize.width}
                  clipHeight={imageSize.height}
                >
                  <CanvasImage image={image} />
                  {children}
                </Layer>
              </Stage>
            </div>
            {shade && (
              <div
                className="crop-shade"
                aria-hidden="true"
                style={{
                  left: view.x,
                  top: view.y,
                  width: imageSize.width * view.scale,
                  height: imageSize.height * view.scale,
                }}
              >
                <span style={{ ...frame, left: box.x * view.scale, top: box.y * view.scale }} />
              </div>
            )}
            <div className="outpaint-image-hit" aria-hidden="true" style={frame} />
            <div
              className="outpaint-frame"
              role="group"
              aria-label={t('frame.selection')}
              style={frame}
            >
              {handles && <FrameHandles compact={compact} onKeyDown={nudge} />}
            </div>
          </>
        )}
      </div>
      <CanvasZoom view={viewport} />
    </>
  );
}
