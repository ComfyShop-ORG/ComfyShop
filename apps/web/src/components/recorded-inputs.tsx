import { useQuery } from '@tanstack/react-query';
import type { InputValue } from '@comfyshop/api-client';
import { size } from '@comfyshop/tokens';
import { Button } from '@comfyshop/ui';
import { useWorkspace } from '../app/use-workspace';
import { cardThumbnail } from '../data/card-thumbnail';

const previewEdge = Number.parseFloat(size['parameter-preview']);

/**
 * 按字段名称列出一组已保存的参数。
 * @param taskId 本人任务的输入定义，包含参考素材。
 * @param workId 作品公开的输入，访客也能读取。两者指定其一。
 */
export function RecordedInputs({
  taskId,
  workId,
  values,
}: {
  taskId?: string;
  workId?: string;
  values: Record<string, InputValue>;
}) {
  const { api, state } = useWorkspace();
  const query = useQuery({
    queryKey: ['recorded-inputs', state.userId, taskId, workId],
    enabled: workId ? true : !!state.userId && !!taskId,
    queryFn: ({ signal }) =>
      workId ? api.workInputs(workId, signal) : api.taskInputs(taskId!, signal),
    staleTime: Infinity,
  });
  if (query.error)
    return (
      <div className="inline-status" role="alert">
        {query.error.message}
        <Button size="small" onClick={() => void query.refetch()}>
          重试
        </Button>
      </div>
    );
  if (!query.data)
    return (
      <div className="empty-state" role="status">
        正在读取参数
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
        <span className="muted">工作流版本</span>
        <span>v{version}</span>
      </div>
      {ids.length ? (
        <dl className="recorded-inputs">
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
                      {field.nodeTitle || '节点'} · {field.nodeId} / {field.inputName}
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
        <div className="empty-state">暂无参数</div>
      )}
    </>
  );
}

function inputText(value: InputValue) {
  if (value === null) return <span className="muted">未设置</span>;
  if (value === '') return <span className="muted">空文本</span>;
  if (typeof value === 'boolean') return value ? '开启' : '关闭';
  if (typeof value === 'object') return value.assetId;
  return String(value);
}
