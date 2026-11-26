/** 媒体列表的分页、当前选择和相邻预览，供结果、作品与成品复用。 */
import { t } from '../app/i18n.ts';
import { useCallback, useLayoutEffect, useRef, useState } from 'react';
import type { InfiniteData, UseInfiniteQueryResult } from '@tanstack/react-query';
import { collectionPosition } from '../data/collection-position';
import type { ItemDirection } from '../data/collection-position';

export type CollectionPages<Item> = Pick<
  UseInfiniteQueryResult<InfiniteData<{ items: Item[] }>>,
  'data' | 'hasNextPage' | 'fetchNextPage'
>;

/** 将查询的已加载页按顺序展开，提供列表加载状态和保留进行中请求的翻页入口。 */
export function collectionFeed<Item>(
  query: CollectionPages<Item> & { isFetching: boolean; isError: boolean },
) {
  return {
    items: query.data?.pages.flatMap((page) => page.items) ?? [],
    hasNextPage: query.hasNextPage && !query.isError,
    loading: query.isFetching,
    loadMore: () => query.fetchNextPage({ cancelRefetch: false }),
  };
}

/**
 * 管理打开的条目与其触发元素。关闭后优先聚焦原元素，原卡片已卸载时使用列表容器。
 * `fallbackRef` 挂到可聚焦的列表容器上，恢复焦点时保留滚动位置。
 */
export function useCollectionFocus() {
  const origin = useRef<HTMLElement>(null);
  const fallbackRef = useRef<HTMLDivElement>(null);
  const restoreFocus = useCallback(() => {
    const target = origin.current?.isConnected ? origin.current : fallbackRef.current;
    target?.focus({ preventScroll: true });
  }, []);
  return {
    fallbackRef,
    rememberFocus: (source: HTMLElement) => {
      origin.current = source;
    },
    restoreFocus,
  };
}

export function useCollectionSelection<Item>() {
  const [selected, select] = useState<Item | null>(null);
  const { fallbackRef, rememberFocus, restoreFocus } = useCollectionFocus();
  return {
    selected,
    select,
    fallbackRef,
    open: (item: Item, source: HTMLElement) => {
      rememberFocus(source);
      select(item);
    },
    close: () => select(null),
    restoreFocus,
  };
}

export type CollectionNavigation = {
  position: number;
  /** 集合的总数。还有未读取的分页时未知。 */
  total?: number;
  /** 已读取的条目数。 */
  loaded: number;
  previous: boolean;
  next: boolean;
  pending: boolean;
  error: string;
  move: (direction: ItemDirection, stillActive: () => boolean) => void;
};

/**
 * 根据稳定 ID 查找相邻条目。到已加载页尾并继续向后时先请求下一页。
 * @param pages 当前列表的查询结果。直接打开详情时可省略。
 * @param id 当前查看的条目 ID，位置随已加载列表计算。
 * @param select 切换到相邻项。异步读取详情后可用 `isCurrent` 确认仍应切换。
 * @param locked 执行发布、选择或上传等操作期间暂停切换。
 * @returns 可用方向、位置与切换函数。没有可浏览的集合时返回 undefined。
 */
export function useCollectionNavigation<Item extends { id: string }>(
  pages: CollectionPages<Item> | undefined,
  id: string,
  select: (item: Item, isCurrent: () => boolean) => void | Promise<void>,
  locked = false,
): CollectionNavigation | undefined {
  const request = useRef<AbortController | null>(null);
  const [transition, setTransition] = useState({ id, locked, pending: false, error: '' });
  if (transition.id !== id || transition.locked !== locked)
    setTransition({ id, locked, pending: false, error: '' });
  useLayoutEffect(
    () => () => {
      request.current?.abort();
      request.current = null;
    },
    [id, locked],
  );
  const items = pages?.data?.pages.flatMap((page) => page.items) ?? [];
  const position = collectionPosition(items, id, !!pages?.hasNextPage);
  if (!pages || !position || (items.length < 2 && !pages.hasNextPage)) return undefined;

  const previous = !locked && !transition.pending && !!position.previous;
  const next = !locked && !transition.pending && (!!position.next || position.atPageBoundary);
  return {
    position: position.index + 1,
    total: pages.hasNextPage ? undefined : items.length,
    loaded: items.length,
    previous,
    next,
    pending: transition.pending,
    error: transition.error,
    move(direction, stillActive) {
      if (request.current || !(direction === 1 ? next : previous)) return;
      const attempt = new AbortController();
      // 弹框关闭、被覆盖或当前条目改变时，晚到的结果不能再替换当前预览。
      const isCurrent = () => !attempt.signal.aborted && stillActive();
      request.current = attempt;
      setTransition({ id, locked, pending: true, error: '' });
      void (async () => {
        try {
          let neighbor = direction === 1 ? position.next : position.previous;
          if (!neighbor && direction === 1 && position.atPageBoundary) {
            const result = await pages.fetchNextPage({ cancelRefetch: false });
            if (result.isFetchNextPageError) throw result.error;
            const loaded = result.data?.pages.flatMap((page) => page.items) ?? [];
            neighbor = collectionPosition(loaded, id, result.hasNextPage)?.next;
          }
          if (neighbor && isCurrent()) await select(neighbor, isCurrent);
          if (!attempt.signal.aborted) setTransition({ id, locked, pending: false, error: '' });
        } catch (error) {
          if (!attempt.signal.aborted) {
            setTransition({
              id,
              locked,
              pending: false,
              error:
                error instanceof Error
                  ? error.message
                  : t('useCollectionNavigation.couldNotSwitchItemsTryAgain'),
            });
          }
        } finally {
          if (request.current === attempt) request.current = null;
        }
      })();
    },
  };
}
