/** 虚拟瀑布流，按实际滚动容器和卡片尺寸渲染媒体集合，并按需读取下一页。 */
import { Children, forwardRef, isValidElement, useCallback, useRef, useState } from 'react';
import type { ComponentType, HTMLAttributes, ReactElement } from 'react';
import { useMasonry, usePositioner, useResizeObserver } from 'masonic';
import { layout } from '@comfyshop/tokens';
import { useScrollMetrics } from './use-scroll-metrics';

export type MediaRendererProps<T> = { data: T; index: number; width: number };
interface FeedProps<T extends { id: string }> {
  items: T[];
  render: ComponentType<MediaRendererProps<T>>;
  resetKey: string;
  scrollRoot?: HTMLElement | null;
  hasNextPage?: boolean;
  loading?: boolean;
  loadMore?: () => Promise<unknown>;
  label: string;
  /** 条目比列数少时减少列数，让仅有的几张卡片占满宽度，至少保留两列。 */
  fillSparse?: boolean;
}

const columnCount = (width: number) =>
  width < layout.smallBreakpoint
    ? layout.columnsSmall
    : width < layout.mediumBreakpoint
      ? layout.columnsMedium
      : width < layout.largeBreakpoint
        ? layout.columnsDesktop
        : width < layout.wideBreakpoint
          ? layout.columnsLarge
          : layout.columnsWide;

// Masonic's interval tree returns visible cells in tree order. Sort the public
// item keys at the container boundary so keyboard and screen-reader order agree.
const OrderedContainer = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  function OrderedContainer({ children, ...props }, ref) {
    const ordered = Children.toArray(children).sort((a, b) =>
      isValidElement(a) && isValidElement(b) ? String(a.key).localeCompare(String(b.key)) : 0,
    );
    return (
      <div {...props} ref={ref}>
        {ordered}
      </div>
    );
  },
);

/**
 * 工作流、作品和结果共用的瀑布流。每个 `items` 成员使用稳定 ID。
 * `resetKey` 代表当前集合，筛选变化时换键，追加页时保留测量缓存。
 * 弹框内传实际的 `scrollRoot`，页面列表省略它以使用窗口滚动。
 */
export function MediaMasonry<T extends { id: string }>({ resetKey, ...props }: FeedProps<T>) {
  const [before, remember] = useState(() => ({
    identity: resetKey,
    ids: props.items.map((item) => item.id),
    revision: 0,
  }));
  // Appending pages retains measurements. Removing, replacing or reordering any
  // index must discard Masonic's position cache, including changes after page 1.
  const changed =
    before.identity !== resetKey ||
    before.ids.length > props.items.length ||
    before.ids.some((id, index) => props.items[index]?.id !== id);
  if (changed || before.ids.length !== props.items.length)
    remember({
      identity: resetKey,
      ids: props.items.map((item) => item.id),
      revision: before.revision + (changed ? 1 : 0),
    });
  return <Feed key={resetKey + ':' + before.revision} {...props} />;
}

function Feed<T extends { id: string }>({
  items,
  render,
  scrollRoot = null,
  hasNextPage,
  loading,
  loadMore,
  label,
  fillSparse,
}: Omit<FeedProps<T>, 'resetKey'>) {
  const outer = useRef<HTMLDivElement>(null);
  const metrics = useScrollMetrics(outer, scrollRoot);
  const inFlight = useRef(false);
  const onRender = useCallback(
    (_start: number, end: number) => {
      if (!hasNextPage || loading || !loadMore || inFlight.current || end < items.length - 4)
        return;
      inFlight.current = true;
      void loadMore().then(
        () => {
          inFlight.current = false;
        },
        () => {
          inFlight.current = false;
        },
      );
    },
    [hasNextPage, items.length, loadMore, loading],
  );
  return (
    <div ref={outer} className="media-feed" aria-label={label} aria-busy={loading}>
      {metrics.width > 0 && items.length > 0 && (
        <VirtualGrid
          items={items}
          render={render}
          onRender={onRender}
          columnLimit={fillSparse && !hasNextPage ? Math.max(2, items.length) : undefined}
          {...metrics}
        />
      )}
      {loading && (
        <div className="media-loading" role="status" aria-label="加载中">
          <span />
        </div>
      )}
    </div>
  );
}

function VirtualGrid<T extends { id: string }>({
  items,
  render,
  onRender,
  columnLimit,
  width,
  height,
  scrollTop,
  isScrolling,
}: {
  items: T[];
  render: ComponentType<MediaRendererProps<T>>;
  onRender: (start: number, end: number) => void;
  columnLimit?: number;
  width: number;
  height: number;
  scrollTop: number;
  isScrolling: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const positioner = usePositioner({
    width,
    columnCount: Math.min(columnCount(width), columnLimit ?? Infinity),
    columnGutter: layout.gap,
    rowGutter: layout.gap,
  });
  const resizeObserver = useResizeObserver(positioner);
  // Masonic 4 declares its element using the pre-React 19 global JSX namespace.
  return useMasonry({
    items,
    positioner,
    resizeObserver,
    containerRef,
    height,
    scrollTop,
    isScrolling,
    render,
    itemKey: (item, index) => `${String(index).padStart(12, '0')}/${item.id}`,
    as: OrderedContainer,
    onRender,
    role: 'list',
    tabIndex: -1,
    overscanBy: 2,
    itemHeightEstimate: 280,
  }) as ReactElement;
}
