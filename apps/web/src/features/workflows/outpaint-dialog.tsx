import { lazy, Suspense, useId, useState } from 'react';
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  Crosshair2Icon,
  FrameIcon,
  ResetIcon,
} from '@radix-ui/react-icons';
import {
  Button,
  Dialog,
  DialogContent,
  Field,
  FieldHelp,
  IconButton,
  Input,
  Popover,
} from '@comfyshop/ui';
import { t } from '../../app/i18n';
import { DialogActions } from '../../components/dialog-actions';
import { useDialogFocus } from '../../components/use-dialog-focus';
import { FrameRatios, frameRatios } from './frame-ratios';
import { useCanvasImage } from './canvas-viewport';
import {
  outpaintSides,
  outpaintSize,
  placeOutpaintImage,
  samePadding,
  validPadding,
} from './outpaint-fields';
import type { OutpaintEditor, OutpaintPadding, OutpaintSide } from './outpaint-fields';

const OutpaintCanvas = lazy(() => import('./outpaint-canvas'));
const emptyPadding = { left: 0, top: 0, right: 0, bottom: 0 };
type Framing = { padding: OutpaintPadding; ratio: string };

function paddingForRatio(
  image: HTMLImageElement,
  [w, h]: readonly [number, number],
  maximum: OutpaintPadding,
  step: number,
) {
  const difference = image.naturalHeight * w - image.naturalWidth * h;
  const right = Math.ceil(Math.max(0, difference) / (h * step)) * step;
  const bottom = Math.ceil(Math.max(0, -difference) / (w * step)) * step;
  if (right > maximum.left + maximum.right || bottom > maximum.top + maximum.bottom) return null;
  return placeOutpaintImage({ left: 0, top: 0, right, bottom }, maximum, step);
}

function OutpaintDialog({
  src,
  editor,
  onClose,
}: {
  src: string;
  editor: OutpaintEditor;
  onClose: () => void;
}) {
  const { fields, step } = editor;
  const id = useId();
  const formId = `outpaint-${id}`;
  const { titleRef, focusProps } = useDialogFocus();
  const image = useCanvasImage(src);
  const [preview, setPreview] = useState<OutpaintPadding | null>(null);
  const [manual, setManual] = useState<{ side: OutpaintSide; text: string } | null>(null);
  const maximum = {
    left: fields.left.maximum,
    top: fields.top.maximum,
    right: fields.right.maximum,
    bottom: fields.bottom.maximum,
  };

  const [history, setHistory] = useState<{ items: Framing[]; index: number }>(() => {
    const padding = {
      left: fields.left.value,
      top: fields.top.value,
      right: fields.right.value,
      bottom: fields.bottom.value,
    };
    return {
      items: [{ padding, ratio: samePadding(padding, emptyPadding) ? 'original' : 'custom' }],
      index: 0,
    };
  });
  const current = history.items[history.index];
  const initial = history.items[0];
  const manualValue = manual?.text ? Number(manual.text) : NaN;
  const manualFrame =
    manual && validPadding(manualValue, maximum[manual.side], step)
      ? {
          padding: { ...current.padding, [manual.side]: manualValue },
          ratio: manualValue === current.padding[manual.side] ? current.ratio : 'custom',
        }
      : null;
  const invalidManual = manual !== null && manualFrame === null;
  const framing = manualFrame ?? current;
  const { ratio } = framing;
  const padding = preview ?? framing.padding;
  const centered = placeOutpaintImage(padding, maximum, step);
  const { width, height } = image ? outpaintSize(image, padding) : { width: 0, height: 0 };
  const presets = [
    { value: 'original', label: t('outpaint.originalSize'), aspect: null, padding: emptyPadding },
    ...frameRatios.map(([w, h]) => ({
      value: `${w}:${h}`,
      label: `${w}:${h}`,
      aspect: w / h,
      padding: image ? paddingForRatio(image, [w, h], maximum, step) : null,
    })),
  ];

  function commit(next: Framing) {
    setPreview(null);
    setManual(null);
    setHistory((prior) => {
      const before = prior.items[prior.index];
      if (before.ratio === next.ratio && samePadding(before.padding, next.padding)) return prior;
      const items = [...prior.items.slice(0, prior.index + 1), next];
      return { items, index: items.length - 1 };
    });
  }

  function navigateHistory(direction: -1 | 1) {
    setPreview(null);
    setManual(null);
    setHistory((prior) => ({
      ...prior,
      index: Math.max(0, Math.min(prior.items.length - 1, prior.index + direction)),
    }));
  }

  const previewStatus = (
    <p className="canvas-editor-viewport" role="status">
      {t(image === null ? 'outpaint.previewUnavailable' : 'common.loading')}
    </p>
  );

  return (
    <DialogContent className="canvas-editor-dialog outpaint-dialog" {...focusProps}>
      <form
        id={formId}
        className="canvas-editor-form"
        onSubmit={(event) => {
          event.preventDefault();
          event.stopPropagation();
          if (!image || invalidManual || preview) return;
          editor.onApply(
            Object.fromEntries(outpaintSides.map((side) => [fields[side].id, padding[side]])),
          );
          onClose();
        }}
      >
        <div className="compact-dialog-heading canvas-editor-heading outpaint-heading">
          <div className="canvas-editor-title">
            <Dialog.Title ref={titleRef} tabIndex={-1}>
              {t('outpaint.title')}
            </Dialog.Title>
            <FieldHelp
              label={t('common.fieldHelp', t('outpaint.title'))}
              help={t('outpaint.dragHelp') + ' ' + t('canvasView.help')}
            />
          </div>
          <div className="canvas-editor-toolbar outpaint-toolbar">
            <FrameRatios
              presets={presets.map((preset) => ({ ...preset, disabled: !preset.padding }))}
              ratio={ratio}
              disabled={!image || !!preview}
              onChange={(value) => {
                const chosen = presets.find((preset) => preset.value === value);
                if (chosen?.padding) commit({ padding: chosen.padding, ratio: value });
              }}
            />
            <div className="outpaint-tools">
              <IconButton
                label={t('outpaint.center')}
                size="large"
                disabled={!image || !!preview || samePadding(padding, centered)}
                onClick={() => commit({ padding: centered, ratio })}
              >
                <Crosshair2Icon aria-hidden="true" />
              </IconButton>
              <IconButton
                label={t('outpaint.undo')}
                size="large"
                disabled={!!preview || history.index === 0}
                onClick={() => navigateHistory(-1)}
              >
                <ArrowLeftIcon aria-hidden="true" />
              </IconButton>
              <IconButton
                label={t('outpaint.redo')}
                size="large"
                disabled={!!preview || history.index === history.items.length - 1}
                onClick={() => navigateHistory(1)}
              >
                <ArrowRightIcon aria-hidden="true" />
              </IconButton>
              <IconButton
                label={t('outpaint.reset')}
                size="large"
                disabled={
                  !!preview ||
                  (ratio === initial.ratio &&
                    samePadding(padding, initial.padding) &&
                    !invalidManual)
                }
                onClick={() => commit(initial)}
              >
                <ResetIcon aria-hidden="true" />
              </IconButton>
              <Popover.Root
                onOpenChange={(open) => {
                  if (open || !manual) return;
                  if (manualFrame) commit(manualFrame);
                  else setManual(null);
                }}
              >
                <Popover.Trigger asChild>
                  <Button
                    variant="ghost"
                    size="large"
                    className="outpaint-precision"
                    disabled={!image || !!preview}
                  >
                    {t('outpaint.precision')}
                  </Button>
                </Popover.Trigger>
                <Popover.Portal>
                  <Popover.Content
                    className="ui-menu outpaint-padding-panel"
                    aria-label={t('outpaint.precision')}
                    side="bottom"
                    align="center"
                    sideOffset={8}
                    collisionPadding={12}
                  >
                    <div className="outpaint-padding">
                      {outpaintSides.map((side) => (
                        <Field key={side} label={fields[side].label} htmlFor={`${id}-${side}`}>
                          <Input
                            id={`${id}-${side}`}
                            form={formId}
                            type="number"
                            inputMode="numeric"
                            min={0}
                            max={maximum[side]}
                            step={step}
                            required
                            value={manual?.side === side ? manual.text : padding[side]}
                            aria-invalid={(manual?.side === side && invalidManual) || undefined}
                            aria-describedby={
                              manual?.side === side && invalidManual ? `${id}-issue` : undefined
                            }
                            onChange={(event) => setManual({ side, text: event.target.value })}
                            onBlur={
                              manual?.side === side && manualFrame
                                ? () => commit(manualFrame)
                                : undefined
                            }
                          />
                        </Field>
                      ))}
                    </div>
                    {invalidManual && (
                      <p className="form-error" id={`${id}-issue`} role="alert">
                        {t('outpaint.checkPadding', step)}
                      </p>
                    )}
                  </Popover.Content>
                </Popover.Portal>
              </Popover.Root>
            </div>
          </div>
          <DialogActions busy={false} error="">
            <Button type="submit" variant="primary" disabled={!image || invalidManual || !!preview}>
              {t('runParameterDialog.apply')}
            </Button>
          </DialogActions>
        </div>
        <div className="canvas-editor-body">
          <Suspense fallback={previewStatus}>
            {image ? (
              <OutpaintCanvas
                image={image}
                padding={padding}
                maximum={maximum}
                step={step}
                onPreview={setPreview}
                onChange={(next, resized) =>
                  commit({
                    padding: next,
                    ratio: resized && !samePadding(current.padding, next) ? 'custom' : ratio,
                  })
                }
              />
            ) : (
              previewStatus
            )}
          </Suspense>
          {image && (
            <div className="canvas-editor-status outpaint-dimensions">
              <span>{t('outpaint.outputSize', width, height)}</span>
              <span>
                {t(
                  'outpaint.imageCoverage',
                  Math.round((image.naturalWidth * image.naturalHeight * 100) / (width * height)),
                )}
              </span>
            </div>
          )}
        </div>
      </form>
    </DialogContent>
  );
}

export function OutpaintAction({
  src,
  editor,
  disabled,
}: {
  src: string;
  editor: OutpaintEditor;
  disabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button size="small" variant="ghost" disabled={disabled}>
          <FrameIcon />
          {t('outpaint.title')}
        </Button>
      </Dialog.Trigger>
      {open && <OutpaintDialog src={src} editor={editor} onClose={() => setOpen(false)} />}
    </Dialog.Root>
  );
}
