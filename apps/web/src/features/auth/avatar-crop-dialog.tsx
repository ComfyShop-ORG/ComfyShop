import { t } from '../../app/i18n.ts';
import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Button, Dialog, DialogClose, DialogContent, RangeSlider } from '@comfyshop/ui';
import { useAction } from '../../components/use-action';
import { useDialogFocus } from '../../components/use-dialog-focus';
import { avatarCropArea, constrainAvatarCrop } from '../../data/avatar-crop';
import type { AvatarCrop } from '../../data/avatar-crop';

const directions = new Map<string, readonly [number, number]>([
  ['ArrowLeft', [-1, 0]],
  ['ArrowRight', [1, 0]],
  ['ArrowUp', [0, -1]],
  ['ArrowDown', [0, 1]],
]);

function paintCrop(
  context: CanvasRenderingContext2D,
  image: ImageBitmap,
  area: ReturnType<typeof avatarCropArea>,
) {
  const { width, height } = context.canvas;
  context.clearRect(0, 0, width, height);
  context.drawImage(image, area.left, area.top, area.side, area.side, 0, 0, width, height);
}

async function croppedFile(image: ImageBitmap, area: ReturnType<typeof avatarCropArea>) {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 256;
  const context = canvas.getContext('2d');
  if (!context) throw new Error(t('avatarCropDialog.thisBrowserCouldNotCropThe'));
  paintCrop(context, image, area);
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'));
  if (!blob) throw new Error(t('avatarCropDialog.couldNotCreateTheCroppedAvatar'));
  return new File([blob], 'avatar.png', { type: blob.type });
}

export function AvatarCropDialog({
  source,
  save,
  onClose,
  restoreFocus,
}: {
  source: Blob;
  save: (file: File) => Promise<void>;
  onClose: () => void;
  restoreFocus: () => void;
}) {
  const hintId = useId();
  const preview = useRef<HTMLCanvasElement>(null);
  const pointer = useRef<{ id: number; x: number; y: number } | null>(null);
  const { titleRef, focusProps } = useDialogFocus(restoreFocus);
  const [decodedPreview, setDecodedPreview] = useState<{
    image: ImageBitmap;
    context: CanvasRenderingContext2D;
  }>();
  const [crop, setCrop] = useState<AvatarCrop>({ x: 0, y: 0, zoom: 100 });
  const [loadError, setLoadError] = useState('');
  const action = useAction(t('accountDialog.couldNotUpdateAvatar'));

  useEffect(() => {
    let active = true;
    let bitmap: ImageBitmap | undefined;
    void (async () => {
      try {
        // 预览和上传都使用同一个已按 EXIF 转正的静止画面。
        const decoded = await createImageBitmap(source, { imageOrientation: 'from-image' });
        if (!active) {
          decoded.close();
          return;
        }
        if (decoded.width * decoded.height > 20_000_000) {
          decoded.close();
          setLoadError(t('avatarCropDialog.theAvatarCannotExceedMegapixels'));
          return;
        }
        const context = preview.current?.getContext('2d');
        if (!context) {
          decoded.close();
          setLoadError(t('avatarCropDialog.thisBrowserCouldNotCropThe'));
          return;
        }
        bitmap = decoded;
        setDecodedPreview({ image: decoded, context });
      } catch {
        if (active) setLoadError(t('avatarCropDialog.couldNotReadThisImage'));
      }
    })();
    return () => {
      active = false;
      bitmap?.close();
    };
  }, [source]);

  const image = decodedPreview?.image;
  const area = useMemo(() => (image ? avatarCropArea(image, crop) : undefined), [image, crop]);
  const ready = !!area && !loadError;
  useLayoutEffect(() => {
    if (decodedPreview && area) paintCrop(decodedPreview.context, decodedPreview.image, area);
  }, [decodedPreview, area]);

  function move(x: number, y: number) {
    if (!image || action.busy) return;
    setCrop((previous) =>
      constrainAvatarCrop(image, { ...previous, x: previous.x + x, y: previous.y + y }),
    );
  }
  function zoom(value: number) {
    if (!image) return;
    setCrop((previous) =>
      constrainAvatarCrop(image, {
        zoom: value,
        x: (previous.x * value) / previous.zoom,
        y: (previous.y * value) / previous.zoom,
      }),
    );
  }

  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open && !action.busy) onClose();
      }}
    >
      <DialogContent
        size="compact"
        className="avatar-crop-dialog"
        aria-describedby={hintId}
        {...focusProps}
      >
        <header className="account-heading">
          <div className="account-identity">
            <Dialog.Title ref={titleRef} tabIndex={-1}>
              {t('avatarCropDialog.cropAvatar')}
            </Dialog.Title>
            <Dialog.Description className="form-hint" id={hintId}>
              {t('avatarCropDialog.dragTheImageOrUseThe')}
            </Dialog.Description>
          </div>
          <DialogClose label={t('common.close')} disabled={action.busy} />
        </header>
        <form
          className="avatar-crop-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (!image || !area || !ready) return;
            void action.run(async () => {
              await save(await croppedFile(image, area));
              onClose();
            });
          }}
        >
          <div
            className="avatar-crop-viewport"
            role="group"
            aria-label={t('avatarCropDialog.avatarCropArea')}
            aria-describedby={hintId}
            tabIndex={ready && !action.busy ? 0 : undefined}
            hidden={!!loadError}
            data-ready={ready && !action.busy}
            onPointerDown={(event) => {
              if (!ready || action.busy || event.button !== 0 || pointer.current) return;
              event.currentTarget.setPointerCapture(event.pointerId);
              event.currentTarget.focus({ preventScroll: true });
              pointer.current = { id: event.pointerId, x: event.clientX, y: event.clientY };
            }}
            onPointerMove={(event) => {
              const active = pointer.current;
              if (active?.id !== event.pointerId) return;
              const length = event.currentTarget.getBoundingClientRect().width;
              if (!length) return;
              move((event.clientX - active.x) / length, (event.clientY - active.y) / length);
              active.x = event.clientX;
              active.y = event.clientY;
            }}
            onLostPointerCapture={(event) => {
              if (pointer.current?.id === event.pointerId) pointer.current = null;
            }}
            onKeyDown={(event) => {
              const direction = directions.get(event.key);
              if (!direction || !ready || action.busy) return;
              event.preventDefault();
              const step = event.shiftKey ? 0.1 : 0.025;
              move(direction[0] * step, direction[1] * step);
            }}
          >
            <canvas ref={preview} width={512} height={512} aria-hidden="true" />
            {!ready && !loadError && (
              <p className="form-hint" role="status">
                {t('avatarCropDialog.loadingImage')}
              </p>
            )}
          </div>
          {ready && (
            <RangeSlider
              label={t('avatarCropDialog.zoom')}
              min={100}
              max={400}
              value={crop.zoom}
              onValueChange={zoom}
              detail={`${crop.zoom}%`}
              thumbProps={{ 'aria-valuetext': `${crop.zoom}%` }}
              disabled={action.busy}
            />
          )}
          {(loadError || action.error) && (
            <p className="form-error" role="alert">
              {loadError || action.error}
            </p>
          )}
          <div className="account-form-footer">
            <Dialog.Close asChild>
              <Button variant="ghost" disabled={action.busy}>
                {t('deleteButton.cancel')}
              </Button>
            </Dialog.Close>
            <Button type="submit" variant="primary" disabled={!ready || action.busy}>
              {action.busy ? t('avatarCropDialog.saving') : t('avatarCropDialog.saveAvatar')}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog.Root>
  );
}
