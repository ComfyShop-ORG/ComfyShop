import { useRef, useState } from 'react';
import type { PointerEvent, RefObject } from 'react';
import { DividerVerticalIcon, DragHandleDots2Icon } from '@radix-ui/react-icons';
import { Button, Dialog, DialogClose, DialogContent, TrackSlider } from '@comfyshop/ui';
import type { Artifact, Asset, ApiClient } from '@comfyshop/api-client';
import { t } from '../app/i18n';
import {
  CanvasZoom,
  fitCanvas,
  transformCanvas,
  useCanvasImage,
  useCanvasViewport,
} from '../features/workflows/canvas-viewport';
import { useDialogFocus } from './use-dialog-focus';
import { useRecordedInputs } from './recorded-inputs';

type Alignment = NonNullable<Awaited<ReturnType<ApiClient['taskInputs']>>['comparisons']>[string];

function ComparisonView({
  asset,
  artifact,
  frame,
  titleRef,
}: {
  asset: Asset;
  artifact: Artifact;
  frame: Alignment;
  titleRef: RefObject<HTMLHeadingElement | null>;
}) {
  const source = useCanvasImage(asset.media.src);
  const output = useCanvasImage(artifact.media.src);
  const valid =
    source &&
    output &&
    source.naturalWidth === asset.media.width &&
    source.naturalHeight === asset.media.height &&
    output.naturalWidth === artifact.media.width &&
    output.naturalHeight === artifact.media.height;
  const failed = source === null || output === null || (source && output && !valid);

  const [split, setSplit] = useState(50);
  const gesture = useRef<{ id: number; previous: number } | null>(null);
  const element = useRef<HTMLDivElement>(null);
  function cancel() {
    if (gesture.current) {
      setSplit(gesture.current.previous);
      gesture.current = null;
    }
  }
  const viewport = useCanvasViewport(element, cancel, !valid);
  const box = transformCanvas(fitCanvas(viewport.size, frame), viewport.camera);
  const w = frame.width * box.scale,
    h = frame.height * box.scale;
  function update(event: PointerEvent<HTMLDivElement>) {
    if (w > 0)
      setSplit(
        Math.round(Math.max(0, Math.min(100, (100 * (viewport.localPoint(event).x - box.x)) / w))),
      );
  }
  function release(event: PointerEvent<HTMLDivElement>) {
    viewport.end(event);
    if (gesture.current?.id === event.pointerId) cancel();
  }
  return (
    <div className="canvas-editor-form">
      <div className="compact-dialog-heading canvas-editor-heading">
        <div className="canvas-editor-title">
          <Dialog.Title ref={titleRef} tabIndex={-1}>
            {t('comparison.title')}
          </Dialog.Title>
        </div>
        <div className="canvas-editor-toolbar comparison-toolbar">
          <Button variant="ghost" size="small" disabled={!valid} onClick={() => setSplit(100)}>
            {t('comparison.original')}
          </Button>
          <TrackSlider
            label={t('comparison.divider')}
            value={split}
            min={0}
            max={100}
            step={1}
            disabled={!valid}
            thumbProps={{ 'aria-valuetext': t('comparison.percent', split) }}
            onValueChange={setSplit}
          />
          <Button variant="ghost" size="small" disabled={!valid} onClick={() => setSplit(0)}>
            {t('comparison.output')}
          </Button>
        </div>
        <div className="compact-dialog-footer">
          <DialogClose label={t('common.close')} />
        </div>
      </div>
      <div className="canvas-editor-body">
        <div
          ref={element}
          className="canvas-editor-viewport comparison-viewport"
          role="group"
          aria-label={t('comparison.title')}
          tabIndex={0}
          {...viewport.keys}
          data-panning={viewport.panning}
          onPointerDown={(event) => {
            event.currentTarget.focus({ preventScroll: true });
            if (viewport.start(event) || !event.isPrimary || event.button !== 0 || !valid) return;
            const p = viewport.localPoint(event);
            if (p.x < box.x || p.x > box.x + w || p.y < box.y || p.y > box.y + h) return;
            gesture.current = { id: event.pointerId, previous: split };
            event.currentTarget.setPointerCapture(event.pointerId);
            update(event);
          }}
          onPointerMove={(event) => {
            if (!viewport.move(event) && gesture.current?.id === event.pointerId) update(event);
          }}
          onPointerUp={(event) => {
            if (!viewport.end(event) && gesture.current?.id === event.pointerId) {
              update(event);
              gesture.current = null;
            }
          }}
          onLostPointerCapture={release}
          onPointerCancel={release}
        >
          {valid && box.scale > 0 ? (
            <div
              className="comparison-frame"
              style={{ left: box.x, top: box.y, width: w, height: h }}
            >
              <img src={artifact.media.src} alt={t('comparison.output')} draggable={false} />
              <div
                className="comparison-original outpaint-frame-fill"
                style={{ clipPath: 'inset(0 ' + (100 - split) + '% 0 0)' }}
              >
                <img
                  src={asset.media.src}
                  alt={t('comparison.original')}
                  draggable={false}
                  style={{
                    left: frame.x * box.scale,
                    top: frame.y * box.scale,
                    width: source.naturalWidth * box.scale,
                    height: source.naturalHeight * box.scale,
                  }}
                />
              </div>
              {split > 0 && split < 100 && (
                <div
                  className="comparison-divider"
                  aria-hidden="true"
                  style={{ left: split + '%' }}
                >
                  <DragHandleDots2Icon />
                </div>
              )}
            </div>
          ) : (
            <p role={failed ? 'alert' : 'status'}>
              {t(failed ? 'outpaint.previewUnavailable' : 'common.loading')}
            </p>
          )}
        </div>
        <CanvasZoom view={viewport} disabled={!valid} />
        {valid && (
          <div className="canvas-editor-status">
            <span>{t('frame.size', output.naturalWidth, output.naturalHeight)}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export function ResultComparison({ artifact }: { artifact: Artifact }) {
  const { titleRef, focusProps } = useDialogFocus();
  const query = useRecordedInputs(artifact.taskId);
  const [open, setOpen] = useState(false);
  const frame = query.data?.comparisons?.[artifact.outputNodeId];
  const { width, height } = artifact.media;
  if (!frame || !width || !height || artifact.outputSlot !== 'images') return null;
  const aligned = frame.width === width && frame.height === height;
  const scaled =
    frame.uniformUpscale &&
    width >= frame.width &&
    height >= frame.height &&
    width * frame.height === height * frame.width;
  if (!aligned && !scaled) return null;
  const asset = query.data?.assets.find((a) => a.id === frame.assetId);
  if (!asset?.media.width || !asset.media.height) return null;
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button size="small">
          <DividerVerticalIcon />
          {t('comparison.title')}
        </Button>
      </Dialog.Trigger>
      {open && (
        <DialogContent className="canvas-editor-dialog" {...focusProps}>
          <ComparisonView asset={asset} artifact={artifact} frame={frame} titleRef={titleRef} />
        </DialogContent>
      )}
    </Dialog.Root>
  );
}
