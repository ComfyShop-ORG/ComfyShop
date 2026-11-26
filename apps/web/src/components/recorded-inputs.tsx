import { t } from '../app/i18n.ts';
import { useQuery } from '@tanstack/react-query';
import type { InputValue } from '@comfyshop/api-client';
import { size } from '@comfyshop/tokens';
import { Button } from '@comfyshop/ui';
import { workspaceKey } from '../app/workspace-scope';
import { useWorkspace } from '../app/use-workspace';
import { cardThumbnail } from '../data/card-thumbnail';

const previewEdge = Number.parseFloat(size['parameter-preview']);

export function useRecordedInputs(taskId?: string, workId?: string) {
  const { api, state, workspaceScope } = useWorkspace();
  return useQuery({
    queryKey: ['recorded-inputs', state.userId, taskId, workId, ...workspaceKey(workspaceScope)],
    enabled: workId ? true : !!state.userId && !!taskId,
    queryFn: ({ signal }) =>
      workId ? api.workInputs(workId, signal) : api.taskInputs(taskId!, signal),
    staleTime: Infinity,
  });
}

/**
 * 按字段名称列出一组已保存的参数。
 * @param taskId 本人任务的输入定义，包含参考素材。
 * @param workId 作品公开的输入，访客也能读取。两者指定其一。
 */
export function RecordedInputs({
  taskId,
  workId,
  values,
  effectivePrompt,
  promptExpanded,
}: {
  taskId?: string;
  workId?: string;
  values: Record<string, InputValue>;
  effectivePrompt?: string | null;
  promptExpanded?: boolean | null;
}) {
  const query = useRecordedInputs(taskId, workId);
  if (query.error)
    return (
      <div className="inline-status" role="alert">
        {query.error.message}
        <Button size="small" onClick={() => void query.refetch()}>
          {t('app.retry')}
        </Button>
      </div>
    );
  if (!query.data)
    return (
      <div className="empty-state" role="status">
        {t('recordedInputs.loadingParameters')}
      </div>
    );

  const { fields, assets, version } = query.data;
  const byId = new Map(fields.map((field) => [field.id, field]));
  const assetsById = new Map(assets.map((asset) => [asset.id, asset]));
  const ids = [
    ...fields.filter(({ id }) => Object.hasOwn(values, id)).map(({ id }) => id),
    ...Object.keys(values).filter((id) => !byId.has(id)),
  ];
  return (
    <>
      <div className="recorded-version">
        <span className="muted">{t('recordedInputs.workflowVersion')}</span>
        <span>v{version}</span>
      </div>
      {ids.length || effectivePrompt ? (
        <dl className="recorded-inputs">
          {effectivePrompt && (
            <div className="recorded-input">
              <dt>
                {t('recordedInputs.effectivePrompt')}
                {promptExpanded != null && (
                  <small>
                    {promptExpanded ? t('recordedInputs.expanded') : t('recordedInputs.original')}
                  </small>
                )}
              </dt>
              <dd>{effectivePrompt}</dd>
            </div>
          )}
          {ids.map((id) => {
            const field = byId.get(id);
            const value = values[id];
            const asset = value && typeof value === 'object' ? assetsById.get(value.assetId) : null;
            const media = asset?.media;
            const thumbnail =
              media?.width && media.height
                ? cardThumbnail(
                    media,
                    (previewEdge * media.width) / Math.max(media.width, media.height),
                  )
                : null;
            return (
              <div className="recorded-input" key={id}>
                <dt>
                  {field?.label || field?.inputName || id}
                  {field && (
                    <small>
                      {field.nodeTitle || t('recordedInputs.node')} · {field.nodeId} /{' '}
                      {field.inputName}
                    </small>
                  )}
                </dt>
                <dd>
                  {asset ? (
                    <a
                      className={thumbnail ? 'recorded-image' : undefined}
                      href={asset.media.video || asset.media.src}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {thumbnail && (
                        <img
                          src={thumbnail.src}
                          srcSet={thumbnail.srcSet}
                          width={asset.media.width ?? undefined}
                          height={asset.media.height ?? undefined}
                          alt=""
                          loading="lazy"
                          decoding="async"
                        />
                      )}
                      <span>{asset.filename}</span>
                    </a>
                  ) : (
                    inputText(value)
                  )}
                </dd>
              </div>
            );
          })}
        </dl>
      ) : (
        <div className="empty-state">{t('recordedInputs.noParameters')}</div>
      )}
    </>
  );
}

function inputText(value: InputValue) {
  if (value === null) return <span className="muted">{t('recordedInputs.notSet')}</span>;
  if (value === '') return <span className="muted">{t('recordedInputs.emptyText')}</span>;
  if (typeof value === 'boolean') return value ? t('recordedInputs.on') : t('recordedInputs.off');
  if (typeof value === 'object') return value.assetId;
  return String(value);
}
