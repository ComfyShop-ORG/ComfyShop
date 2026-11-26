import type { KeyboardEvent, PointerEvent } from 'react';
import { Button } from '@comfyshop/ui';
import { t } from '../../app/i18n';

const frameHandles = [
  { key: 'topLeft', x: 0, y: 0, horizontal: 'left', vertical: 'top' },
  { key: 'top', x: 50, y: 0, vertical: 'top' },
  { key: 'topRight', x: 100, y: 0, horizontal: 'right', vertical: 'top' },
  { key: 'right', x: 100, y: 50, horizontal: 'right' },
  { key: 'bottomRight', x: 100, y: 100, horizontal: 'right', vertical: 'bottom' },
  { key: 'bottom', x: 50, y: 100, vertical: 'bottom' },
  { key: 'bottomLeft', x: 0, y: 100, horizontal: 'left', vertical: 'bottom' },
  { key: 'left', x: 0, y: 50, horizontal: 'left' },
] as const satisfies ReadonlyArray<{
  key: string;
  x: number;
  y: number;
  horizontal?: 'left' | 'right';
  vertical?: 'top' | 'bottom';
}>;
export type FrameHandle = (typeof frameHandles)[number];

export function frameHandleAt(event: PointerEvent<HTMLDivElement>) {
  // A mobile browser can send a touch inside the selection to a nearby handle.
  const point = event.currentTarget.ownerDocument.elementFromPoint(event.clientX, event.clientY);
  const key = point?.closest<HTMLElement>('[data-handle]')?.dataset.handle;
  return frameHandles.find((handle) => handle.key === key);
}

export function FrameHandles({
  onKeyDown,
  compact = false,
}: {
  compact?: boolean;
  onKeyDown: (event: KeyboardEvent<HTMLButtonElement>, handle: FrameHandle) => void;
}) {
  const handles = compact
    ? frameHandles.filter((handle) => handle.key === 'topLeft' || handle.key === 'bottomRight')
    : frameHandles;
  return handles.map((handle) => (
    <Button
      key={handle.key}
      variant="ghost"
      size="large"
      className="outpaint-handle"
      data-handle={handle.key}
      data-outside={compact || undefined}
      aria-label={t(`outpaint.handle.${handle.key}`)}
      style={{ left: `${handle.x}%`, top: `${handle.y}%` }}
      onKeyDown={(event) => onKeyDown(event, handle)}
    />
  ));
}
