/** 作品、结果和成品共用的卡片列表：瀑布流、卡片外观、加载与空状态。 */
import { createContext, useContext } from 'react';
import type { ReactNode } from 'react';
import type { Media } from '@comfyshop/api-client';
import { MediaMasonry } from '@comfyshop/media';
import type { MediaRendererProps } from '@comfyshop/media';
import { Button } from '@comfyshop/ui';
import { CollectionStatus } from './collection-status';
import { MediaCardContent } from './media-cards';
import { collectionFeed } from './use-collection-navigation';
import type { CollectionPages } from './use-collection-navigation';

type Entry = { id: string };
/** 一张卡片的内容。`pressed` 用于可选择的列表，`badge` 叠加在卡片上。 */
export type CardView = {
  label: string;
  title: string;
  media: Media | null;
  coverImage?: Media | null;
  detail?: ReactNode;
  pressed?: boolean;
  disabled?: boolean;
  badge?: ReactNode;
};
type GridActions = {
  view: (item: Entry) => CardView;
  open: (item: Entry, source: HTMLElement) => void;
};
const GridContext = createContext<GridActions | null>(null);

function GridCard({ data, index, width }: MediaRendererProps<Entry>) {
  const { view, open } = useContext(GridContext)!;
  const card = view(data);
  return (
    <article className="media-card">
      <Button
        variant="ghost"
        className="media-card-open"
        aria-label={card.label}
        aria-pressed={card.pressed}
        disabled={card.disabled}
        onClick={(event) => open(data, event.currentTarget)}
      >
        <MediaCardContent
          media={card.media}
          coverImage={card.coverImage}
          title={card.title}
          width={width}
          index={index}
          detail={card.detail}
        />
        {card.badge}
      </Button>
    </article>
  );
}

type GridProps<Item extends Entry> = {
  label: string;
  /** 代表当前集合，筛选或来源变化时更换。 */
  resetKey: string;
  scrollRoot?: HTMLElement | null;
  fillSparse?: boolean;
  view: (item: Item) => CardView;
  onOpen: (item: Item, source: HTMLElement) => void;
};

/** 渲染一组已加载的条目。分页由调用方通过 `hasNextPage`、`loadMore` 提供。 */
export function MediaGrid<Item extends Entry>({
  view,
  onOpen,
  ...feed
}: GridProps<Item> & {
  items: Item[];
  hasNextPage?: boolean;
  loading?: boolean;
  loadMore?: () => Promise<unknown>;
}) {
  return (
    <GridContext.Provider value={{ view, open: onOpen } as unknown as GridActions}>
      <MediaMasonry<Entry> {...feed} render={GridCard} />
    </GridContext.Provider>
  );
}

/** 渲染一个分页查询的全部已加载页，并在出错或为空时显示状态。 */
export function MediaCollection<Item extends Entry>({
  query,
  emptyLabel,
  emptyAction,
  ...grid
}: GridProps<Item> & {
  query: CollectionPages<Item> & {
    isFetching: boolean;
    isError: boolean;
    isPending: boolean;
    error: Error | null;
    refetch: () => unknown;
  };
  /** 列表为空时显示的文字。不传时由调用方自己呈现空状态。 */
  emptyLabel?: string;
  emptyAction?: ReactNode;
}) {
  const feed = collectionFeed(query);
  return (
    <>
      <MediaGrid {...grid} {...feed} />
      <CollectionStatus
        pending={query.isPending}
        error={query.error}
        empty={!!emptyLabel && !feed.items.length}
        retry={query.refetch}
        label={emptyLabel ?? ''}
        action={emptyAction}
      />
    </>
  );
}
