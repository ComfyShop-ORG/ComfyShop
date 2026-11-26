import { t } from '../../app/i18n.ts';
import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ClipboardIcon, Cross2Icon, LayersIcon, UploadIcon } from '@radix-ui/react-icons';
import { Button, Dialog, Field, FileInput, IconButton } from '@comfyshop/ui';
import { defaultAssetContentTypes } from '@comfyshop/api-client';
import type { Asset, InputValue, WorkflowForm, WorkflowInput } from '@comfyshop/api-client';
import { useWorkspace } from '../../app/use-workspace';
import { createRequestId } from '../../data/request-id';
import { fileSizeLabel } from '../../data/download';
import { MediaPreview } from '../../components/media-preview';
import { useNotify } from '../../components/notify';
import { useAction } from '../../components/use-action';
import { AssetLibraryPicker } from '../assets/asset-library-picker';
import { assetQuery, useAssetLibraryActions } from '../assets/asset-queries';
import { ParameterValueField } from './parameter-value-field';
import { assetInputLabels, isAssetInput } from './parameter-layout';
import type { ParameterRow } from './parameter-layout';
import { promptWithoutAspect } from './output-specification';
import { cropBounds } from './run-assets';
import { OutpaintAction } from './outpaint-dialog';
import type { OutpaintEditor } from './outpaint-fields';
import { CropAction } from './crop-dialog';
import type { CropEditor } from './crop-box';
import { MaskAction } from './mask-dialog';
import type { MaskEditor } from './mask-fields';

import type { PlacementEditor } from './placement-fields';
import { FrameEditor } from './frame-editor';

const PlacementDialog = lazy(() => import('./placement-dialog'));

type CropRegions = WorkflowForm['imageCrops'][string];

const assetExtensions: Record<string, string[]> = {
  'image/bmp': ['.bmp'],
  'image/avif': ['.avif'],
  'image/tiff': ['.tif', '.tiff'],
  'video/quicktime': ['.mov'],
  'video/x-matroska': ['.mkv'],
  'video/x-m4v': ['.m4v'],
  'audio/aac': ['.aac'],
  'audio/flac': ['.flac'],
  'audio/mp4': ['.m4a'],
  'audio/mpeg': ['.mp3'],
  'audio/wav': ['.wav'],
  'audio/ogg': ['.ogg', '.opus'],
  'audio/x-matroska': ['.mka'],
  'audio/x-pcm': ['.raw', '.pcm'],
  'audio/x-mulaw': ['.mulaw', '.ulaw'],
  'audio/x-alaw': ['.alaw'],
  'model/gltf-binary': ['.glb'],
};

function AssetCropPreview({
  asset,
  regions,
  width,
  height,
}: {
  asset: Asset;
  regions: CropRegions;
  width: number;
  height: number;
}) {
  return (
    <div
      className="asset-crop-preview"
      role="group"
      aria-label={t('inputField.fourViewCropPreview')}
      style={{ maxWidth: `calc(var(--size-parameter-preview) * ${width / height})` }}
    >
      <img src={asset.media.src} alt={asset.filename} width={width} height={height} />
      {regions.map((region) => (
        <div
          key={region.label}
          className="asset-crop-region"
          style={{
            left: `${(region.x / width) * 100}%`,
            top: `${(region.y / height) * 100}%`,
            width: `${(region.width / width) * 100}%`,
            height: `${(region.height / height) * 100}%`,
          }}
        >
          <span>{region.label}</span>
        </div>
      ))}
    </div>
  );
}

function AssetInput({
  field,
  id,
  kind,
  value,
  sharedAsset,
  issueId,
  crops,
  placement,
  crop,
  outpaint,
  mask,
  maxAssetBytes,
  onChange,
  onBusy,
}: {
  field: WorkflowInput;
  id: string;
  kind: keyof typeof assetInputLabels;
  value: InputValue;
  sharedAsset?: Asset;
  issueId?: string;
  crops?: CropRegions;
  placement?: PlacementEditor;
  crop?: CropEditor;
  outpaint?: OutpaintEditor;
  mask?: MaskEditor;
  maxAssetBytes?: number | null;
  onChange: (value: InputValue) => void;
  onBusy: (id: string, busy: boolean) => void;
}) {
  const { api, state, workspaceScope } = useWorkspace();
  const queries = useQueryClient();
  const library = useAssetLibraryActions();
  const notify = useNotify();
  const [placing, setPlacing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const assetId = value && typeof value === 'object' ? value.assetId : null;
  const save = useAction(undefined, assetId ?? '');
  const asset = useQuery({
    ...assetQuery(api, state.userId, assetId, workspaceScope),
    enabled: !!assetId && !sharedAsset,
  });
  const selected = sharedAsset ?? asset.data;
  const message = error || save.error || (sharedAsset || issueId ? null : asset.error?.message);
  const width = selected?.media.width;
  const height = selected?.media.height;
  const bounds = cropBounds(crops);
  const acceptedKinds = [kind, ...(field.additionalAssetKinds ?? [])];
  const contentTypes =
    field.acceptedContentTypes ??
    acceptedKinds.flatMap((accepted) => [...defaultAssetContentTypes[accepted]]);
  const accept = contentTypes.flatMap((mime) => [mime, ...(assetExtensions[mime] ?? [])]).join(',');
  const imageFormats = contentTypes
    .filter((mime) => mime.startsWith('image/'))
    .map((mime) => (mime === 'image/webp' ? 'WebP' : mime.slice('image/'.length).toUpperCase()))
    .join(', ');
  const formatsId =
    (kind === 'image' && imageFormats) || !contentTypes.length ? `${id}-formats` : undefined;
  const inputDisabled = busy || save.busy || !contentTypes.length;
  const acceptsImages = !!imageFormats;

  function changeAsset(next: { assetId: string } | null) {
    if (mask?.assetId && assetId && next?.assetId !== assetId) mask.replaceImage(next);
    else onChange(next);
  }

  function select(next: Asset) {
    queries.setQueryData(assetQuery(api, state.userId, next.id, workspaceScope).queryKey, next);
    setError('');
    changeAsset({ assetId: next.id });
  }

  async function uploadAsset(file: File, allowed: readonly string[]) {
    if (inputDisabled || controller.current) return;
    if (maxAssetBytes != null && file.size > maxAssetBytes)
      throw new Error(t('inputField.assetSizeLimit', fileSizeLabel(maxAssetBytes)));
    const request = new AbortController();
    controller.current = request;
    setBusy(true);
    onBusy(field.id, true);
    setError('');
    try {
      const uploaded = await api.uploadAsset(file, createRequestId(), request.signal);
      if (request.signal.aborted) return;
      if (!allowed.includes(uploaded.contentType))
        throw new Error(t('inputField.theFileTypeDoesNotMatch', field.label));
      return uploaded;
    } catch (error) {
      if (!request.signal.aborted) throw error;
    } finally {
      controller.current = null;
      setBusy(false);
      onBusy(field.id, false);
    }
  }

  async function upload(file: File) {
    try {
      const uploaded = await uploadAsset(file, contentTypes);
      if (uploaded) select(uploaded);
    } catch (error) {
      const reason = error instanceof Error ? error.message : t('inputField.selectTheAssetAgain');
      setError(t('inputField.couldNotUpload', file.name, reason));
    }
  }

  async function pasteImage() {
    try {
      for (const item of await navigator.clipboard.read()) {
        const mime = item.types.find(
          (type) => contentTypes.includes(type) && type.startsWith('image/'),
        );
        if (!mime) continue;
        const blob = await item.getType(mime);
        if (fileInput.current?.isConnected)
          await upload(
            new File([blob], `clipboard.${mime.slice('image/'.length)}`, { type: mime }),
          );
        return;
      }
      setError(t('inputField.noClipboardImage'));
    } catch {
      setError(t('inputField.pasteImageHelp'));
      fileInput.current?.focus();
    }
  }

  return (
    <div
      className="asset-input"
      onPaste={(event) => {
        if (inputDisabled || !acceptsImages || !event.currentTarget.contains(event.target as Node))
          return;
        const file =
          Array.from(event.clipboardData.files).find(({ type }) => type.startsWith('image/')) ??
          Array.from(event.clipboardData.items)
            .find(({ kind, type }) => kind === 'file' && type.startsWith('image/'))
            ?.getAsFile();
        if (!file) return;
        event.preventDefault();
        void upload(file);
      }}
    >
      {selected && (
        <div className="asset-preview">
          {crops?.length && width && height ? (
            <AssetCropPreview asset={selected} regions={crops} width={width} height={height} />
          ) : (
            <MediaPreview media={selected.media} name={selected.filename} />
          )}
          <div className="asset-caption">
            <span>
              {error ? t('inputField.currentAsset', selected.filename) : selected.filename}
            </span>
            <IconButton
              label={t('inputField.remove', field.label)}
              disabled={busy || save.busy}
              onClick={() => {
                setError('');
                changeAsset(null);
              }}
            >
              <Cross2Icon />
            </IconButton>
          </div>
        </div>
      )}
      {formatsId && (
        <p className="form-hint" id={formatsId}>
          {contentTypes.length
            ? t('inputField.supportedImageFormats', imageFormats)
            : t('inputField.noSupportedFormats')}
        </p>
      )}
      <FileInput
        ref={fileInput}
        id={id}
        aria-label={field.label}
        aria-keyshortcuts={acceptsImages ? 'Control+V Meta+V' : undefined}
        aria-invalid={issueId ? true : undefined}
        aria-describedby={[issueId, formatsId].filter(Boolean).join(' ') || undefined}
        accept={accept}
        disabled={inputDisabled}
        onChange={(event) => {
          const file = event.currentTarget.files?.[0];
          event.currentTarget.value = '';
          if (file) void upload(file);
        }}
      >
        <UploadIcon />
        {busy
          ? t('inputField.uploading')
          : assetId
            ? t('inputField.replaceAsset')
            : assetInputLabels[kind]}
      </FileInput>
      <div className="asset-input-actions">
        {acceptsImages && typeof navigator.clipboard?.read === 'function' && (
          <Button
            size="small"
            variant="ghost"
            disabled={inputDisabled}
            onClick={() => void pasteImage()}
          >
            <ClipboardIcon />
            {t('inputField.pasteImage')}
          </Button>
        )}
        <AssetLibraryPicker
          field={field.label}
          contentTypes={contentTypes}
          disabled={inputDisabled}
          onSelect={select}
        />
        {selected?.media.kind === 'image' && placement && (
          <Dialog.Root open={placing} onOpenChange={setPlacing}>
            <Dialog.Trigger asChild>
              <Button
                size="small"
                variant="ghost"
                disabled={inputDisabled || placement.layers.some((l) => !l.assetId)}
              >
                <LayersIcon />
                {t('layers.title')}
              </Button>
            </Dialog.Trigger>
            {placement.layers.some((l) => !l.assetId) && (
              <span className="form-hint">{t('layers.chooseImages')}</span>
            )}
            {placing && (
              <Suspense
                fallback={
                  <FrameEditor title={t('layers.title')} help={t('layers.help')}>
                    <p role="status">{t('common.loading')}</p>
                  </FrameEditor>
                }
              >
                <PlacementDialog
                  key={selected.id}
                  background={selected}
                  editor={placement}
                  close={() => setPlacing(false)}
                />
              </Suspense>
            )}
          </Dialog.Root>
        )}
        {selected?.media.kind === 'image' && crop && (
          <CropAction
            key={'crop:' + selected.id}
            src={selected.media.src}
            editor={crop}
            disabled={inputDisabled}
          />
        )}
        {selected?.media.kind === 'image' && outpaint && (
          <OutpaintAction
            key={selected.id}
            src={selected.media.src}
            editor={outpaint}
            disabled={inputDisabled}
          />
        )}
        {selected?.media.kind === 'image' && mask && (
          <MaskAction
            key={`mask:${selected.id}`}
            source={selected}
            editor={mask}
            disabled={inputDisabled}
            onSave={async (file) => {
              if (!file) {
                mask.apply(null);
                return true;
              }
              const uploaded = await uploadAsset(file, ['image/png']);
              if (!uploaded) return false;
              queries.setQueryData(
                assetQuery(api, state.userId, uploaded.id, workspaceScope).queryKey,
                uploaded,
              );
              mask.apply(uploaded);
              return true;
            }}
          />
        )}
        {!sharedAsset && selected && (
          <Button
            size="small"
            variant="ghost"
            aria-disabled={busy || save.busy || !!selected.savedAt}
            onClick={() => {
              if (busy || selected.savedAt) return;
              void save.run(async () => {
                await library.save(selected.id);
                notify(t('assetLibrary.saved'));
              });
            }}
          >
            {t(selected.savedAt ? 'assetLibrary.saved' : 'assetLibrary.save')}
          </Button>
        )}
      </div>
      {bounds && ((width && height) || !issueId) && (
        <p className="form-hint" role="status">
          {width && height ? t('inputField.currentImagePixels', width, height) : ''}
          {!issueId && t('inputField.cropAreaRequiresAtLeastPixels', bounds.width, bounds.height)}
        </p>
      )}
      {message && (
        <p className="form-error" role="alert">
          {message}
        </p>
      )}
    </div>
  );
}

export function InputField({
  field: row,
  id = `input-${row.id}`,
  value,
  sharedAsset,
  issue,
  linkedAspect = false,
  crops,
  placement,
  crop,
  outpaint,
  mask,
  maxAssetBytes,
  onChange,
  onBusy,
}: {
  field: ParameterRow;
  id?: string;
  value: InputValue;
  sharedAsset?: Asset;
  issue?: string;
  linkedAspect?: boolean;
  crops?: CropRegions;
  placement?: PlacementEditor;
  crop?: CropEditor;
  outpaint?: OutpaintEditor;
  mask?: MaskEditor;
  maxAssetBytes?: number | null;
  onChange: (value: InputValue) => void;
  onBusy: (id: string, busy: boolean) => void;
}) {
  const field = { ...row, label: row.displayName || row.label };
  const issueId = issue ? `${id}-issue` : undefined;
  const help = row.help ?? undefined;
  return (
    <>
      {isAssetInput(field.kind) ? (
        <Field
          label={field.label}
          htmlFor={id}
          detail={!field.primary ? field.nodeTitle : undefined}
          help={help}
          helpLabel={t('common.fieldHelp', field.label)}
        >
          <AssetInput
            field={field}
            id={id}
            kind={field.kind}
            value={value}
            sharedAsset={sharedAsset}
            issueId={issueId}
            crops={crops}
            placement={placement}
            crop={crop}
            outpaint={outpaint}
            mask={mask}
            maxAssetBytes={maxAssetBytes}
            onChange={onChange}
            onBusy={onBusy}
          />
        </Field>
      ) : (
        <ParameterValueField
          field={field}
          id={id}
          help={help}
          value={linkedAspect && typeof value === 'string' ? promptWithoutAspect(value) : value}
          issueId={issueId}
          onChange={onChange}
        />
      )}
      {issue && (
        <p className="form-error" role="alert" id={issueId}>
          {issue}
        </p>
      )}
      {linkedAspect && <p className="form-hint">{t('inputField.theSizePresetSetsTheAspect')}</p>}
      {row.presentation?.guidance && <p className="form-hint">{row.presentation.guidance}</p>}
    </>
  );
}
