/** 本人结果列表。打开卡片后由执行详情弹框处理成品、发布和重跑。 */
import { Link } from 'react-router';
import { DownloadIcon } from '@radix-ui/react-icons';
import type { Execution } from '@comfyshop/api-client';
import { Button } from '@comfyshop/ui';
import { useExecutions } from '../app/use-workspace';
import type { ReplayAction } from '../domain/types';
import { ExecutionDialog, countLabel } from './execution-dialog';
import { MediaCollection } from './media-grid';
import { MediaPreview } from './media-preview';
import type { CardView } from './media-grid';
import { collectionFeed, useCollectionSelection } from './use-collection-navigation';

/** 结果卡片。`scoped` 表示列表只属于一个工作流，卡片改以生成时间区分彼此。 */
const executionCard =
  (scoped: boolean) =>
  (execution: Execution): CardView => {
    const created = new Date(execution.created);
    return {
      label: `查看 ${execution.workflowName} 在 ${created.toLocaleString('zh-CN')} 的第 ${execution.index + 1} 次执行`,
      title: scoped
        ? created.toLocaleString('zh-CN', {
            month: 'numeric',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          })
        : execution.workflowName,
      media: execution.media,
      detail: (
        <>
          {countLabel(execution)}
          {!scoped && <span>{created.toLocaleDateString('zh-CN')}</span>}
        </>
      ),
    };
  };

export function ExecutionCollection({
  workflowId,
  taskId,
  scrollRoot,
  quietEmpty,
  featured,
  onReplay,
}: {
  workflowId?: string;
  taskId?: string;
  scrollRoot?: HTMLElement | null;
  /** 调用方已经在别处说明了当前状态时，空列表不再显示「暂无结果」。 */
  quietEmpty?: boolean;
  /** 列表只有一次执行时放大展示它，用于刚完成的提交。 */
  featured?: boolean;
  onReplay?: ReplayAction;
}) {
  const query = useExecutions(workflowId, taskId);
  const { selected, select, fallbackRef, open, close, restoreFocus } =
    useCollectionSelection<Execution>();
  const { items } = collectionFeed(query);
  const hero = featured && items.length === 1 && !query.hasNextPage ? items[0] : null;
  return (
    <>
      {hero?.media && (
        <div className="generation-hero">
          {hero.media.video ? (
            <MediaPreview media={hero.media} name={hero.workflowName} autoPlay />
          ) : (
            <span
              className="artifact-zoom"
              tabIndex={-1}
              onClick={(event) => open(hero, event.currentTarget)}
            >
              <MediaPreview media={hero.media} name={hero.workflowName} />
            </span>
          )}
          <div className="collection-actions">
            <Button
              size="small"
              variant="primary"
              onClick={(event) => open(hero, event.currentTarget)}
            >
              查看与发布
            </Button>
            {hero.imageCount + hero.videoCount === 1 ? (
              <Button size="small" asChild>
                <a href={`${hero.media.video || hero.media.src}?download=true`} download>
                  <DownloadIcon />
                  下载原文件
                </a>
              </Button>
            ) : (
              <span className="muted">{countLabel(hero)}</span>
            )}
          </div>
        </div>
      )}
      <div ref={fallbackRef} tabIndex={-1} hidden={!!hero?.media}>
        <MediaCollection
          query={query}
          label="我的结果"
          resetKey={`${workflowId ?? 'all'}:${taskId ?? 'all'}`}
          scrollRoot={scrollRoot}
          fillSparse={!!scrollRoot}
          view={executionCard(!!workflowId)}
          onOpen={open}
          emptyLabel={quietEmpty ? undefined : '暂无结果'}
          emptyAction={
            !workflowId &&
            !taskId && (
              <Button size="small" asChild>
                <Link to="/workspace/tasks">查看任务</Link>
              </Button>
            )
          }
        />
      </div>
      {selected && (
        <ExecutionDialog
          initialExecution={selected}
          pages={query}
          select={select}
          onClose={close}
          restoreFocus={restoreFocus}
          onReplay={onReplay}
        />
      )}
    </>
  );
}
