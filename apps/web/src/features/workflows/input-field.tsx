import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Cross2Icon, UploadIcon } from '@radix-ui/react-icons';
import { Field, FileInput, IconButton } from '@comfyshop/ui';
import type { InputValue, WorkflowInput } from '@comfyshop/api-client';
import { useWorkspace } from '../../app/use-workspace';
import { createRequestId } from '../../data/request-id';
import { MediaPreview } from '../../components/media-preview';
import { ParameterValueField } from './parameter-value-field';
import type { ParameterRow } from './parameter-layout';

function AssetInput({
  field,
  value,
  onChange,
  onBusy,
}: {
  field: WorkflowInput;
  value: InputValue;
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
    enabled: !!assetId,
    queryFn: ({ signal }) => api.asset(assetId!, signal),
  });
  return (
    <div className="asset-input">
      {asset.data && (
        <div className="asset-preview">
          <MediaPreview media={asset.data.media} name={asset.data.filename} />
          <div className="asset-caption">
            <span>{asset.data.filename}</span>
            <IconButton label={`移除${field.label}`} onClick={() => onChange(null)}>
              <Cross2Icon />
            </IconButton>
          </div>
        </div>
      )}
      <FileInput
        id={`input-${field.id}`}
        aria-label={field.label}
        accept={
          field.kind === 'video'
            ? 'video/mp4,video/webm'
            : 'image/png,image/jpeg,image/webp,image/gif'
        }
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
        {busy ? '上传中' : assetId ? '替换素材' : field.kind === 'video' ? '上传视频' : '上传图片'}
      </FileInput>
      {(error || asset.error) && (
        <p className="form-error" role="alert">
          {error || asset.error?.message}
        </p>
      )}
    </div>
  );
}

export function InputField({
  field,
  help,
  value,
  onChange,
  onBusy,
}: {
  field: ParameterRow;
  help?: string;
  value: InputValue;
  onChange: (value: InputValue) => void;
  onBusy: (id: string, busy: boolean) => void;
}) {
  if (field.kind === 'image' || field.kind === 'video') {
    return (
      <Field
        label={field.label}
        htmlFor={`input-${field.id}`}
        detail={!field.primary ? field.nodeTitle : undefined}
        help={help}
      >
        <AssetInput field={field} value={value} onChange={onChange} onBusy={onBusy} />
      </Field>
    );
  }
  return <ParameterValueField field={field} help={help} value={value} onChange={onChange} />;
}
