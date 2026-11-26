import { useEffect, useEffectEvent, useLayoutEffect, useRef, useState } from 'react';
import type { KeyboardEvent, PointerEvent, RefObject } from 'react';
import { MagnifyingGlassIcon, MinusIcon, PlusIcon } from '@radix-ui/react-icons';
import { Button, IconButton, Popover } from '@comfyshop/ui';
import { t } from '../../app/i18n';

export type CanvasPoint = { x: number; y: number };
export type CanvasView = CanvasPoint & { scale: number };
type Size = { width: number; height: number };
type ViewportSize = Size & { gutter: number; background: string };

const fit: CanvasView = { x: 0, y: 0, scale: 1 };
const maxZoom = 8;

export function fitCanvas(size: ViewportSize, content: Size): CanvasView {
  const scale = Math.max(
    0,
    Math.min(
      (size.width - size.gutter * 2) / content.width,
      (size.height - size.gutter * 2) / content.height,
    ),
  );
  return {
    x: (size.width - content.width * scale) / 2,
    y: (size.height - content.height * scale) / 2,
    scale,
  };
}

export function canvasPoint(view: CanvasView, point: CanvasPoint): CanvasPoint {
  return { x: (point.x - view.x) / view.scale, y: (point.y - view.y) / view.scale };
}

export function transformCanvas(view: CanvasView, camera: CanvasView): CanvasView {
  return {
    x: view.x * camera.scale + camera.x,
    y: view.y * camera.scale + camera.y,
    scale: view.scale * camera.scale,
  };
}

function midpoint(a: CanvasPoint, b: CanvasPoint): CanvasPoint {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

function distance(a: CanvasPoint, b: CanvasPoint) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

/** Owns view gestures for both editors. Coordinates of the content stay in original pixels. */
export function useCanvasViewport(
  element: RefObject<HTMLDivElement | null>,
  cancelEdit: () => void,
  disabled = false,
) {
  const [size, setSize] = useState<ViewportSize>({
    width: 0,
    height: 0,
    gutter: 0,
    background: '',
  });
  const [camera, setCamera] = useState(fit);
  const [panning, setPanning] = useState(false);
  const space = useRef(false);
  const mousePan = useRef<{ id: number; point: CanvasPoint } | null>(null);
  const touches = useRef(new Map<number, CanvasPoint>());
  const pinching = useRef(false);

  useLayoutEffect(() => {
    const viewport = element.current;
    if (!viewport) return;
    const measure = () => {
      const styles = getComputedStyle(viewport);
      const next = {
        width: viewport.clientWidth,
        height: viewport.clientHeight,
        gutter: Number.parseFloat(styles.paddingLeft),
        background: styles.backgroundColor,
      };
      setSize((previous) =>
        previous.width === next.width &&
        previous.height === next.height &&
        previous.gutter === next.gutter &&
        previous.background === next.background
          ? previous
          : next,
      );
    };
    const resize = new ResizeObserver(measure);
    resize.observe(viewport);
    measure();
    return () => resize.disconnect();
  }, [element]);

  function localPoint(event: { clientX: number; clientY: number }) {
    const rect = element.current?.getBoundingClientRect();
    return { x: event.clientX - (rect?.left ?? 0), y: event.clientY - (rect?.top ?? 0) };
  }

  function moveView(from: CanvasPoint, to: CanvasPoint, factor = 1) {
    setCamera((previous) => {
      const scale = Math.min(maxZoom, Math.max(1, previous.scale * factor));
      if (scale === 1) return fit;
      const anchor = canvasPoint(previous, from);
      return { x: to.x - anchor.x * scale, y: to.y - anchor.y * scale, scale };
    });
  }

  function zoomBy(factor: number) {
    const center = { x: size.width / 2, y: size.height / 2 };
    moveView(center, center, factor);
  }

  const wheel = useEffectEvent((event: WheelEvent) => {
    event.preventDefault();
    if (disabled || !event.deltaY) return;
    element.current?.focus({ preventScroll: true });
    const point = localPoint(event);
    const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? 120 : 1);
    cancelEdit();
    moveView(point, point, Math.exp(-Math.max(-160, Math.min(160, delta)) / 420));
  });

  useEffect(() => {
    const viewport = element.current;
    const onWheel = (event: WheelEvent) => wheel(event);
    viewport?.addEventListener('wheel', onWheel, { passive: false });
    return () => viewport?.removeEventListener('wheel', onWheel);
  }, [element]);

  function start(event: PointerEvent<HTMLDivElement>) {
    if (disabled) return true;
    const point = localPoint(event);
    if (event.pointerType === 'touch') {
      touches.current.set(event.pointerId, point);
      event.currentTarget.setPointerCapture(event.pointerId);
      if (touches.current.size > 1) {
        if (!pinching.current) cancelEdit();
        pinching.current = true;
        setPanning(true);
      }
      return pinching.current;
    }
    if (event.button !== 1 && !(space.current && event.button === 0)) return false;
    event.preventDefault();
    cancelEdit();
    event.currentTarget.setPointerCapture(event.pointerId);
    mousePan.current = { id: event.pointerId, point };
    setPanning(true);
    return true;
  }

  function move(event: PointerEvent<HTMLDivElement>) {
    const point = localPoint(event);
    const pan = mousePan.current;
    if (pan?.id === event.pointerId) {
      moveView(pan.point, point);
      pan.point = point;
      return true;
    }
    const fingers = touches.current;
    const previous = fingers.get(event.pointerId);
    if (!previous) return false;
    const before = [...fingers.values()];
    fingers.set(event.pointerId, point);
    if (!pinching.current) return false;
    const after = [...fingers.values()];
    if (after.length > 1) {
      const start = distance(before[0], before[1]);
      if (start > 0)
        moveView(
          midpoint(before[0], before[1]),
          midpoint(after[0], after[1]),
          distance(after[0], after[1]) / start,
        );
    } else {
      moveView(previous, point);
    }
    return true;
  }

  function end(event: PointerEvent<HTMLDivElement>) {
    if (mousePan.current?.id === event.pointerId) {
      mousePan.current = null;
      setPanning(false);
      return true;
    }
    const handled = pinching.current && touches.current.has(event.pointerId);
    touches.current.delete(event.pointerId);
    if (handled && touches.current.size === 0) {
      pinching.current = false;
      setPanning(false);
    }
    return handled;
  }

  function keyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (disabled || event.target !== event.currentTarget) return;
    if (event.code === 'Space') {
      event.preventDefault();
      space.current = true;
    } else if (event.key === '+' || event.key === '=' || event.key === '-' || event.key === '0') {
      event.preventDefault();
      if (event.key === '0') setCamera(fit);
      else zoomBy(event.key === '-' ? 1 / 1.25 : 1.25);
    }
  }

  function releaseSpace() {
    space.current = false;
  }

  return {
    size,
    camera,
    localPoint,
    start,
    move,
    end,
    panning,
    zoomBy,
    fit: () => setCamera(fit),
    keys: { onKeyDown: keyDown, onKeyUp: releaseSpace, onBlur: releaseSpace },
  };
}

export function CanvasZoom({
  view,
  disabled,
}: {
  view: ReturnType<typeof useCanvasViewport>;
  disabled?: boolean;
}) {
  const zoom = view.camera.scale;
  const percent = Math.round(zoom * 100);
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <Button
          className="canvas-zoom-trigger"
          disabled={disabled}
          size="large"
          aria-label={t('canvasView.zoom', percent)}
        >
          <MagnifyingGlassIcon aria-hidden="true" />
          <span>{percent}%</span>
        </Button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          className="ui-menu canvas-zoom-menu"
          aria-label={t('canvasView.zoom', percent)}
          align="end"
          side="bottom"
          sideOffset={8}
        >
          <IconButton
            size="large"
            label={t('canvasView.zoomOut')}
            disabled={zoom <= 1}
            onClick={() => view.zoomBy(1 / 1.25)}
          >
            <MinusIcon aria-hidden="true" />
          </IconButton>
          <Button size="large" variant="ghost" onClick={view.fit}>
            {t('canvasView.fit')}
          </Button>
          <IconButton
            size="large"
            label={t('canvasView.zoomIn')}
            disabled={zoom >= maxZoom}
            onClick={() => view.zoomBy(1.25)}
          >
            <PlusIcon aria-hidden="true" />
          </IconButton>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

export function useCanvasImage(src: string | undefined) {
  const [loaded, setLoaded] = useState<{ src: string; image: HTMLImageElement | null }>();
  useEffect(() => {
    if (!src) return;
    const image = new window.Image();
    image.onload = () =>
      setLoaded({ src, image: image.naturalWidth && image.naturalHeight ? image : null });
    image.onerror = () => setLoaded({ src, image: null });
    image.src = src;
    return () => {
      image.onload = null;
      image.onerror = null;
    };
  }, [src]);
  return src && loaded?.src === src ? loaded.image : undefined;
}
