import { useContext } from 'react';
import { Link } from 'react-router';
import { Button } from '@comfyshop/ui';
import { MediaMasonry } from '@comfyshop/media';
import { CardActions } from '../../components/card-actions';
import { WorkflowCard } from '../../components/media-cards';
import { CollectionStatus } from '../../components/collection-status';
import { collectionFeed } from '../../components/use-collection-navigation';
import { useWorkflowPages } from '../../app/use-workspace';
import type { WorkflowFilters } from '../../domain/types';

export function WorkflowCollection({
  scope = 'public',
  category = 'all',
  search = '',
  sort = 'updated',
  author,
  onReset,
}: Partial<WorkflowFilters> & { onReset?: () => void }) {
  const actions = useContext(CardActions);
  const filters = { scope, category, search, sort, author };
  const { pages: query, resetKey } = useWorkflowPages(filters);
  const feed = collectionFeed(query);
  const label =
    scope === 'mine' ? '我的工作流' : scope === 'favorites' ? '收藏的工作流' : '公共工作流';
  return (
    <>
      <CardActions.Provider
        value={{
          ...actions,
          openWorkflow: (workflow, source) => actions.openWorkflow(workflow, source, filters),
        }}
      >
        <MediaMasonry {...feed} label={label} render={WorkflowCard} resetKey={resetKey} />
      </CardActions.Provider>
      <CollectionStatus
        pending={query.isPending}
        error={query.error}
        empty={!feed.items.length}
        retry={query.refetch}
        label={
          search
            ? '无结果'
            : author
              ? '这位作者还没有公开的工作流'
              : scope === 'favorites'
                ? '暂无收藏'
                : scope === 'mine'
                  ? '导入 ComfyUI 工作流 JSON 开始配置。'
                  : '暂无工作流'
        }
        action={
          scope === 'favorites' ? (
            <Button asChild size="small">
              <Link to="/">浏览工作流</Link>
            </Button>
          ) : onReset && (search || author || category !== 'all') ? (
            <Button size="small" onClick={onReset}>
              {search ? '清除关键词' : author ? '浏览全部工作流' : '查看全部'}
            </Button>
          ) : null
        }
      />
    </>
  );
}
