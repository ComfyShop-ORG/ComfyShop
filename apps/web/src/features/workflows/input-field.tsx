import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Cross2Icon, UploadIcon } from '@radix-ui/react-icons';
import { Field, FileInput, IconButton } from '@comfyshop/ui';
import type { Asset, InputValue, WorkflowForm, WorkflowInput } from '@comfyshop/api-client';
import { useWorkspace } from '../../app/use-workspace';
import { createRequestId } from '../../data/request-id';
import { MediaPreview } from '../../components/media-preview';
import { ParameterValueField } from './parameter-value-field';
import { assetInputTypes, isAssetInput } from './parameter-layout';
import type { ParameterRow } from './parameter-layout';
import { promptWithoutAspect } from './output-specification';

type CropRegions = WorkflowForm['imageCrops'][string];

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
      aria-label="四视图裁切预览"
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
  onChange,
  onBusy,
}: {
  field: WorkflowInput;
  id: string;
  kind: keyof typeof assetInputTypes;
  value: InputValue;
  sharedAsset?: Asset;
  issueId?: string;
  crops?: CropRegions;
  onChange: (value: InputValue) => void;
  onBusy: (id: string, busy: boolean) => void;
}) {
  const { api, state } = useWorkspace();
  const queries = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const assetId = value && typeof value === 'object' ? value.assetId : null;
  const asset = useQuery({
    queryKey: ['asset', state.userId, assetId],
    enabled: !!assetId && !sharedAsset,
    queryFn: ({ signal }) => api.asset(assetId!, signal),
  });
  const selected = sharedAsset ?? asset.data;
  const message = error || (sharedAsset ? null : asset.error?.message);
  const width = selected?.media.width;
  const height = selected?.media.height;
  const cropWidth = crops?.length && Math.max(...crops.map(({ x, width }) => x + width));
  const cropHeight = crops?.length && Math.max(...crops.map(({ y, height }) => y + height));
  const outOfBounds =
    width && height && cropWidth && cropHeight && (width < cropWidth || height < cropHeight);
  return (
    <div className="asset-input">
      {selected && (
        <div className="asset-preview">
          {crops?.length && width && height ? (
            <AssetCropPreview asset={selected} regions={crops} width={width} height={height} />
          ) : (
            <MediaPreview media={selected.media} name={selected.filename} />
          )}
          <div className="asset-caption">
            <span>{selected.filename}</span>
            <IconButton label={`移除${field.label}`} onClick={() => onChange(null)}>
              <Cross2Icon />
            </IconButton>
          </div>
        </div>
      )}
      <FileInput
        id={id}
        aria-label={field.label}
        aria-invalid={issueId ? true : undefined}
        aria-describedby={issueId}
        accept={assetInputTypes[kind].accept}
        disabled={busy}
        onChange={(event) => {
          void (async () => {
            const file = event.currentTarget.files?.[0];
            event.currentTarget.value = '';
            if (!file) return;
            if (file.size > 256 * 1024 * 1024) {
              setError('素材不能超过 256 MB');
              return;
            }
            const request = new AbortController();
            controller.current = request;
            setBusy(true);
            onBusy(field.id, true);
            setError('');
            try {
              const uploaded = await api.uploadAsset(file, createRequestId(), request.signal);
              if (request.signal.aborted) return;
              if (uploaded.media.kind !== kind) {
                setError(`文件类型与「${field.label}」不匹配`);
                return;
              }
              queries.setQueryData(['asset', state.userId, uploaded.id], uploaded);
              onChange({ assetId: uploaded.id });
            } catch (error) {
              if (!request.signal.aborted)
                setError(error instanceof Error ? error.message : '上传失败');
            } finally {
              setBusy(false);
              onBusy(field.id, false);
            }
          })();
        }}
      >
        <UploadIcon />
        {busy ? '上传中' : assetId ? '替换素材' : assetInputTypes[kind].label}
      </FileInput>
      {!!cropWidth && !!cropHeight && (
        <p className={outOfBounds ? 'form-error' : 'form-hint'} role="status">
          {width && height ? `当前图片 ${width} × ${height} 像素。` : ''}
          {outOfBounds ? '裁切区域超出图片边界。' : ''}
          裁切区域至少需要 {cropWidth} × {cropHeight} 像素。
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
        >
          <AssetInput
            field={field}
            id={id}
            kind={field.kind}
            value={value}
            sharedAsset={sharedAsset}
            issueId={issueId}
            crops={crops}
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
      {linkedAspect && <p className="form-hint">画幅由尺寸选项自动带入。</p>}
      {row.presentation?.guidance && <p className="form-hint">{row.presentation.guidance}</p>}
    </>
  );
}
