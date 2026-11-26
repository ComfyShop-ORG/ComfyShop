import { lazy, Suspense, useState } from 'react';
import { CropIcon, Crosshair2Icon } from '@radix-ui/react-icons';
import { Button, Dialog, IconButton } from '@comfyshop/ui';
import { t } from '../../app/i18n';
import { useCanvasImage } from './canvas-viewport';
import { boxKeys, clipCrop, cropForRatio, dragCrop, moveCrop } from './crop-box';
import type { Box, CropEditor } from './crop-box';
import { FrameEditor, FrameHistoryTools } from './frame-editor';
import { frameRatios, FrameRatios } from './frame-ratios';
import { useFrameHistory } from './use-frame-history';

const FrameSelection = lazy(() => import('./frame-selection'));
const title = () => t('cropBox.title');
const help = () => t('cropBox.help');
const sameBox = (a: Box, b: Box) => boxKeys.every((key) => a[key] === b[key]);

function CropDialog({
  image,
  editor,
  close,
}: {
  image: HTMLImageElement;
  editor: CropEditor;
  close: () => void;
}) {
  const size = { width: image.naturalWidth, height: image.naturalHeight };
  const { maximum } = editor;
  const history = useFrameHistory({ box: clipCrop(editor.initial, size, maximum), ratio: '' });
  const current = history.current;
  const [preview, setPreview] = useState<Box | null>(null);
  const box = preview ?? current.box;
  const presets = [
    { value: 'original', label: t('outpaint.originalSize'), aspect: size.width / size.height },
    ...frameRatios.map(([w, h]) => ({ value: w + ':' + h, label: w + ':' + h, aspect: w / h })),
  ];
  const ratio = presets.find((p) => p.value === current.ratio)?.aspect ?? null;
  const centered = moveCrop(
    box,
    (size.width - box.width) / 2,
    (size.height - box.height) / 2,
    size,
    maximum,
  );
  function commit(next: Box, aspect = current.ratio) {
    setPreview(null);
    if (!sameBox(next, current.box) || aspect !== current.ratio)
      history.commit({ box: next, ratio: aspect });
  }
  return (
    <FrameEditor
      title={title()}
      help={help()}
      onApply={
        preview
          ? undefined
          : () => {
              editor.apply(box);
              close();
            }
      }
      status={
        <>
          <span>{t('frame.size', box.width, box.height)}</span>
          <span>
            X {box.x} · Y {box.y}
          </span>
        </>
      }
      toolbar={
        <div className="canvas-editor-toolbar outpaint-toolbar">
          <FrameRatios
            ratio={current.ratio}
            presets={presets.map((p) => ({
              ...p,
              aspect: p.value === 'original' ? null : p.aspect,
            }))}
            disabled={!!preview}
            onChange={(value) => {
              const preset = presets.find((p) => p.value === value);
              commit(preset ? cropForRatio(box, size, maximum, preset.aspect) : box, value);
            }}
          />
          <div className="outpaint-tools">
            <IconButton
              size="large"
              label={t('outpaint.center')}
              disabled={!!preview || sameBox(box, centered)}
              onClick={() => commit(centered)}
            >
              <Crosshair2Icon />
            </IconButton>
            <FrameHistoryTools
              {...history}
              changed={current !== history.initial}
              reset={() => history.commit(history.initial)}
            />
          </div>
        </div>
      }
    >
      <Suspense fallback={<p role="status">{t('common.loading')}</p>}>
        <FrameSelection
          image={image}
          box={box}
          shade
          onCancel={() => setPreview(null)}
          onDrag={(handle, delta, end) => {
            const next = dragCrop(current.box, handle, delta.x, delta.y, size, maximum, ratio);
            if (end) commit(next);
            else setPreview(next);
          }}
        />
      </Suspense>
    </FrameEditor>
  );
}

export function CropAction({
  src,
  editor,
  disabled,
}: {
  src: string;
  editor: CropEditor;
  disabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  const image = useCanvasImage(open ? src : undefined);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button size="small" variant="ghost" disabled={disabled}>
          <CropIcon />
          {title()}
        </Button>
      </Dialog.Trigger>
      {open &&
        (image ? (
          <CropDialog image={image} editor={editor} close={() => setOpen(false)} />
        ) : (
          <FrameEditor title={title()} help={help()}>
            <p className="canvas-editor-viewport" role="status">
              {t(image === null ? 'outpaint.previewUnavailable' : 'common.loading')}
            </p>
          </FrameEditor>
        ))}
    </Dialog.Root>
  );
}
