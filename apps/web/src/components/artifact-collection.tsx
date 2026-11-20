/** 展示同一次执行或作品中的成品，复用预览与原文件下载。 */
import { useState } from 'react';
import type { ReactNode } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import {
  CheckIcon,
  DownloadIcon,
  EnterFullScreenIcon,
  ExitFullScreenIcon,
} from '@radix-ui/react-icons';
import type { Artifact } from '@comfyshop/api-client';
import { Button } from '@comfyshop/ui';
import { useWorkspace } from '../app/use-workspace';
import { MediaPreview } from './media-preview';
import { MediaGrid } from './media-grid';
import { CollectionStatus } from './collection-status';
import { collectionFeed } from './use-collection-navigation';

export function AssetGallery({
  selected,
  ...grid
}: {
  items: Artifact[];
  onOpen: (asset: Artifact, source: HTMLElement) => void;
  /** 提供时列表进入选择模式，卡片显示勾选状态。 */
  selected?: ReadonlySet<string>;
  scrollRoot?: HTMLElement | null;
  resetKey: string;
  hasNextPage?: boolean;
  loading?: boolean;
  loadMore?: () => Promise<unknown>;
}) {
  return (
    <MediaGrid
      {...grid}
      label="成品"
      view={(asset) => {
        const chosen = selected?.has(asset.id);
        return {
          label: `${selected ? '选择' : '查看'} ${asset.filename}`,
          title: asset.filename,
          media: asset.media,
          pressed: selected ? chosen : undefined,
          detail: (
            <>
              <span className="media-card-output">
                {asset.outputNodeTitle || '输出'}
                {asset.outputNodeId && ` · ${asset.outputNodeId}`}
              </span>
              <span className="media-card-dimensions">
                {asset.media.width} × {asset.media.height}
              </span>
            </>
          ),
          badge: selected && (
            <span className="media-selection" data-selected={chosen} aria-hidden="true">
              <CheckIcon />
            </span>
          ),
        };
      }}
    />
  );
}

function DownloadArtifact({ artifact }: { artifact: Artifact }) {
  return (
    <Button size="small" asChild>
      <a
        href={`${artifact.media.video || artifact.media.src}?download=true`}
        download={artifact.filename}
      >
        <DownloadIcon />
        下载原文件
      </a>
    </Button>
  );
}

function fileSizeLabel(bytes: number) {
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(2)} MiB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
  return `${bytes} B`;
}

/**
 * 单份成品的展示。
 * @param onOpen 放大入口。点击图片或「放大查看」时调用，再次调用退出放大。
 * @param expanded 当前已在所在弹框内放大。弹框随之占满视口并收起其余内容。
 * @param actions 追加的操作。传函数时收到视频当前的播放位置（毫秒），图片为 0。
 */
export function ArtifactDisplay({
  artifact,
  onOpen,
  expanded = false,
  closeLabel = '退出放大',
  actions,
}: {
  artifact: Artifact;
  onOpen?: (source: HTMLElement) => void;
  expanded?: boolean;
  /** 放大状态下退出按钮的文字。从多份成品里点开的单件用「返回成品列表」。 */
  closeLabel?: string;
  actions?: ReactNode | ((positionMs: number) => ReactNode);
}) {
  const [positionMs, setPositionMs] = useState(0);
  return (
    <div className="artifact-display" data-expanded={expanded}>
      <div className="artifact-stage">
        {onOpen && !artifact.media.video ? (
          // 鼠标点图片即可放大。键盘使用下方的「放大查看」按钮，这里不进入 Tab 顺序。
          <span
            className="artifact-zoom"
            tabIndex={-1}
            onClick={(event) => onOpen(event.currentTarget)}
          >
            <MediaPreview media={artifact.media} name={artifact.filename} />
          </span>
        ) : (
          <MediaPreview
            media={artifact.media}
            name={artifact.filename}
            autoPlay
            onPosition={typeof actions === 'function' ? setPositionMs : undefined}
          />
        )}
      </div>
      <div className="artifact-info">
        <div className="preview-caption">
          <span>
            {onOpen && (
              <>
                {artifact.filename}
                <br />
              </>
            )}
            {artifact.outputNodeTitle || '输出'}
            {artifact.outputNodeId && ` · ${artifact.outputNodeId}`}
            {artifact.outputSlot && ` / ${artifact.outputSlot}`} · {artifact.outputIndex + 1}
          </span>
          <span>
            {artifact.media.width} × {artifact.media.height} · {fileSizeLabel(artifact.size)}
          </span>
        </div>
        <div className="collection-actions">
          {onOpen && (
            <Button size="small" onClick={(event) => onOpen(event.currentTarget)}>
              {expanded ? <ExitFullScreenIcon /> : <EnterFullScreenIcon />}
              {expanded ? closeLabel : '放大查看'}
            </Button>
          )}
          <DownloadArtifact artifact={artifact} />
          {typeof actions === 'function' ? actions(positionMs) : actions}
        </div>
      </div>
    </div>
  );
}

type ArtifactSource = { executionId?: string; workId?: string };

export function useArtifactPages(source: ArtifactSource) {
  const { api, state } = useWorkspace();
  return useInfiniteQuery({
    queryKey: ['artifacts', state.userId, source],
    enabled: !!(source.executionId || source.workId),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      source.executionId
        ? api.artifacts({ execution_id: source.executionId, cursor: pageParam }, signal)
        : api.workArtifacts(source.workId!, pageParam, signal),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
  });
}

/**
 * 作品里的成品：一份时直接展示，多份时用瀑布流，点开其中一份后在原处放大。
 * @param query 成品分页，由所在弹框读取，弹框同时用它在放大的成品之间切换。
 * @param focused 多份成品中当前放大的那一份。
 * @param expanded 只有一份成品时的放大状态。
 */
export function ArtifactCollection({
  query,
  resetKey,
  scrollRoot,
  focused,
  onFocus,
  expanded,
  onExpandedChange,
}: {
  query: ReturnType<typeof useArtifactPages>;
  resetKey: string;
  scrollRoot?: HTMLElement | null;
  focused: Artifact | null;
  onFocus: (artifact: Artifact | null) => void;
  expanded: boolean;
  onExpandedChange: (expanded: boolean) => void;
}) {
  const feed = collectionFeed(query);
  const { items } = feed;
  const single = items.length === 1 && !query.hasNextPage ? items[0] : null;
  return (
    <div className={single || focused ? 'single-artifact' : undefined}>
      {single ? (
        <ArtifactDisplay
          artifact={single}
          expanded={expanded}
          onOpen={() => onExpandedChange(!expanded)}
        />
      ) : (
        <>
          {focused && (
            <ArtifactDisplay
              key={focused.id}
              artifact={focused}
              expanded
              closeLabel="返回成品列表"
              onOpen={() => onFocus(null)}
            />
          )}
          <div hidden={!!focused}>
            <AssetGallery
              {...feed}
              onOpen={(asset) => onFocus(asset)}
              resetKey={resetKey}
              scrollRoot={scrollRoot}
            />
          </div>
        </>
      )}
      <CollectionStatus
        pending={query.isPending}
        error={query.error}
        empty={!items.length}
        retry={query.refetch}
        label="暂无成品"
      />
    </div>
  );
}
