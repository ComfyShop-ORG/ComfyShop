import { useLayoutEffect, useRef, useState } from 'react';
import type { PointerEvent } from 'react';
import 'konva/lib/shapes/Image.js';
import type { Layer as KonvaLayer } from 'konva/lib/Layer.js';
import { Image as CanvasImage, Layer, Stage } from 'react-konva/lib/ReactKonvaCore.js';
import { t } from '../../app/i18n';
import {
  CanvasZoom,
  canvasPoint,
  fitCanvas,
  transformCanvas,
  useCanvasViewport,
} from './canvas-viewport';
import type { CanvasPoint } from './canvas-viewport';
import { maskBitmap, paintMaskSegment, renderMask } from './mask-bitmap';
import type { MaskChange, MaskStroke, MaskTool, SelectionMode } from './mask-bitmap';

export default function MaskCanvas({
  image,
  original,
  sourceAlpha,
  changes,
  diameter,
  tool,
  disabled,
  selecting,
  onDraw,
  onCommit,
  onSelect,
}: {
  image: HTMLImageElement;
  original?: HTMLImageElement;
  sourceAlpha: boolean;
  changes: readonly MaskChange[];
  diameter: number;
  tool: MaskTool;
  disabled: boolean;
  selecting: boolean;
  onDraw: (drawing: boolean) => void;
  onCommit: (stroke: MaskStroke) => void;
  onSelect: (point: CanvasPoint, mode: SelectionMode) => void;
}) {
  const { naturalWidth: width, naturalHeight: height } = image;
  const [bitmap] = useState(() => maskBitmap(image, Math.min(1, 2048 / Math.max(width, height))));
  const [cursor, setCursor] = useState<CanvasPoint | null>(null);
  const layer = useRef<KonvaLayer>(null);
  const context = useRef<CanvasRenderingContext2D>(null);
  const ink = useRef('');
  const pending = useRef<{ id: number; stroke: MaskStroke } | null>(null);
  const tap = useRef<{ id: number; start: CanvasPoint } | null>(null);
  const element = useRef<HTMLDivElement>(null);
  const viewport = useCanvasViewport(element, cancelStroke, disabled);
  const view = transformCanvas(fitCanvas(viewport.size, { width, height }), viewport.camera);
  const imageBox = { x: view.x, y: view.y, width: width * view.scale, height: height * view.scale };

  useLayoutEffect(() => {
    const surface = element.current;
    if (!surface) return;
    ink.current = getComputedStyle(surface).getPropertyValue('--color-accent').trim();
    context.current = renderMask(bitmap, image, original, changes, ink.current, sourceAlpha);
    layer.current?.batchDraw();
  }, [bitmap, image, original, sourceAlpha, changes]);

  function cancelStroke() {
    tap.current = null;
    if (!pending.current) return;
    pending.current = null;
    onDraw(false);
    context.current = renderMask(bitmap, image, original, changes, ink.current, sourceAlpha);
    layer.current?.batchDraw();
  }

  function append(stroke: MaskStroke, point: CanvasPoint) {
    const current = context.current;
    if (!current) return;
    const previous = stroke.points.at(-1);
    if (previous && previous.x === point.x && previous.y === point.y) return;
    stroke.points.push(point);
    paintMaskSegment(current, stroke, ink.current, point, previous);
    layer.current?.batchDraw();
  }

  function pointerDown(event: PointerEvent<HTMLDivElement>) {
    event.currentTarget.focus({ preventScroll: true });
    if (viewport.start(event) || !event.isPrimary || event.button !== 0 || !view.scale) return;
    const local = viewport.localPoint(event);
    const point = canvasPoint(view, local);
    if (point.x < 0 || point.y < 0 || point.x >= width || point.y >= height) return;
    if (tool === 'add' || tool === 'subtract') {
      if (!selecting) {
        tap.current = { id: event.pointerId, start: local };
        event.currentTarget.setPointerCapture(event.pointerId);
      }
      return;
    }
    const stroke = { tool, diameter, points: [] };
    pending.current = { id: event.pointerId, stroke };
    event.currentTarget.setPointerCapture(event.pointerId);
    onDraw(true);
    append(stroke, point);
  }

  function pointerMove(event: PointerEvent<HTMLDivElement>) {
    if (viewport.move(event)) {
      setCursor(null);
      return;
    }
    if (disabled || !view.scale) return;
    const local = viewport.localPoint(event);
    const start = tap.current?.start;
    if (start && Math.hypot(local.x - start.x, local.y - start.y) > 8) tap.current = null;
    const point = canvasPoint(view, local);
    setCursor(
      event.pointerType !== 'touch' &&
        point.x >= 0 &&
        point.x <= width &&
        point.y >= 0 &&
        point.y <= height
        ? local
        : null,
    );
    const edit = pending.current;
    if (edit?.id === event.pointerId) append(edit.stroke, point);
  }

  function pointerUp(event: PointerEvent<HTMLDivElement>) {
    const edit = pending.current;
    if (viewport.end(event)) return;
    const point = canvasPoint(view, viewport.localPoint(event));
    if (tap.current?.id === event.pointerId) {
      tap.current = null;
      if (
        (tool === 'add' || tool === 'subtract') &&
        point.x >= 0 &&
        point.x < width &&
        point.y >= 0 &&
        point.y < height
      )
        onSelect({ x: point.x / width, y: point.y / height }, tool);
      return;
    }
    if (edit?.id !== event.pointerId) return;
    append(edit.stroke, point);
    pending.current = null;
    onDraw(false);
    onCommit(edit.stroke);
  }

  function pointerCancel(event: PointerEvent<HTMLDivElement>) {
    if (
      !viewport.end(event) &&
      (pending.current?.id === event.pointerId || tap.current?.id === event.pointerId)
    )
      cancelStroke();
  }

  return (
    <>
      <div
        className="canvas-editor-viewport mask-canvas"
        ref={element}
        tabIndex={0}
        role="group"
        aria-label={t('mask.canvas')}
        aria-keyshortcuts="+ - 0 Space"
        data-panning={viewport.panning}
        aria-busy={selecting}
        {...viewport.keys}
        onPointerDown={pointerDown}
        onPointerMove={pointerMove}
        onPointerUp={pointerUp}
        onPointerCancel={pointerCancel}
        onLostPointerCapture={pointerCancel}
        onPointerLeave={() => setCursor(null)}
      >
        {view.scale > 0 && (
          <div className="canvas-editor-stage" aria-hidden="true">
            <Stage width={viewport.size.width} height={viewport.size.height}>
              <Layer listening={false}>
                <CanvasImage image={image} {...imageBox} />
              </Layer>
              <Layer listening={false} ref={layer} opacity={0.48}>
                <CanvasImage image={bitmap} {...imageBox} />
              </Layer>
            </Stage>
          </div>
        )}
        {!disabled && (tool === 'paint' || tool === 'erase') && cursor && !viewport.panning && (
          <div
            aria-hidden="true"
            className="mask-brush-cursor"
            style={{
              left: cursor.x,
              top: cursor.y,
              width: diameter * view.scale,
              height: diameter * view.scale,
            }}
          />
        )}
      </div>
      <CanvasZoom view={viewport} disabled={disabled} />
    </>
  );
}
