/** 展示同一次执行或作品中的成品，复用预览与原文件下载。 */
import { t } from '../app/i18n.ts';
import { useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { CheckIcon, EnterFullScreenIcon, ExitFullScreenIcon } from '@radix-ui/react-icons';
import type { Artifact } from '@comfyshop/api-client';
import { Button, Tabs, TabsList } from '@comfyshop/ui';
import { workspaceKey } from '../app/workspace-scope';
import { useWorkspace } from '../app/use-workspace';
import { fileSizeLabel } from '../data/download';
import { ResultComparison } from './result-comparison';
import { DownloadOriginal } from './download-original';
import { MediaPreview } from './media-preview';
import { MediaGrid } from './media-grid';
import { CollectionStatus } from './collection-status';
import { collectionFeed } from './use-collection-navigation';

export function ArtifactTabs({
  label,
  inputsDisabled = false,
}: {
  label: string;
  inputsDisabled?: boolean;
}) {
  return (
    <TabsList className="dialog-tab-list" aria-label={label}>
      <Tabs.Trigger value="artifacts" asChild>
        <Button size="small" variant="ghost">
          {t('artifactCollection.outputs')}
        </Button>
      </Tabs.Trigger>
      <Tabs.Trigger value="inputs" asChild disabled={inputsDisabled}>
        <Button size="small" variant="ghost">
          {t('executionDialog.generationParameters')}
        </Button>
      </Tabs.Trigger>
    </TabsList>
  );
}

const fileFormats: Record<string, string> = {
  'audio/aac': 'AAC',
  'audio/flac': 'FLAC',
  'audio/mp4': 'M4A',
  'audio/mpeg': 'MP3',
  'audio/ogg': 'OGG',
  'audio/wav': 'WAV',
  'audio/webm': 'WebM',
  'audio/x-matroska': 'Matroska',
  'audio/x-pcm': 'PCM',
  'audio/x-mulaw': 'μ-law',
  'audio/x-alaw': 'A-law',
  'text/plain': 'TXT',
  'application/json': 'JSON',
  'image/svg+xml': 'SVG',
  'model/gltf-binary': 'GLB',
  'application/x-fbx': 'FBX',
  'model/obj': 'OBJ',
  'model/mtl': 'MTL',
  'model/stl': 'STL',
  'model/vnd.usdz+zip': 'USDZ',
  'model/3mf': '3MF',
  'application/zip': 'ZIP',
};

function artifactFormat({ contentType, media }: Artifact) {
  return fileFormats[contentType] ?? `${media.width} × ${media.height}`;
}

export function AssetGallery({
  selected,
  disabled,
  ...grid
}: {
  items: Artifact[];
  onOpen: (asset: Artifact, source: HTMLElement) => void;
  /** 提供时列表进入选择模式，卡片显示勾选状态。 */
  selected?: ReadonlySet<string>;
  disabled?: boolean;
  scrollRoot?: HTMLElement | null;
  resetKey: string;
  hasNextPage?: boolean;
  loading?: boolean;
  loadMore?: () => Promise<unknown>;
}) {
  return (
    <MediaGrid
      {...grid}
      label={t('artifactCollection.outputs')}
      view={(asset) => {
        const chosen = selected?.has(asset.id);
        return {
          label: `${selected ? t('artifactCollection.select') : t('artifactCollection.view')} ${asset.filename}`,
          title: asset.filename,
          media: asset.media,
          pressed: selected ? chosen : undefined,
          disabled,
          detail: (
            <>
              <span className="media-card-output">
                {asset.outputNodeTitle || t('artifactCollection.output')}
                {asset.outputNodeId && ` · ${asset.outputNodeId}`}
              </span>
              <span className="media-card-dimensions">{artifactFormat(asset)}</span>
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
  closeLabel = t('artifactCollection.exitZoom'),
  actions,
  compare = false,
}: {
  artifact: Artifact;
  compare?: boolean;
  onOpen?: (source: HTMLElement) => void;
  expanded?: boolean;
  /** 放大状态下退出按钮的文字。从多份成品里点开的单件用「返回成品列表」。 */
  closeLabel?: string;
  actions?: ReactNode | ((positionMs: number) => ReactNode);
}) {
  const [positionMs, setPositionMs] = useState(0);
  const stage = useRef<HTMLDivElement>(null);
  return (
    <div className="artifact-display" data-expanded={expanded}>
      <div className="artifact-stage" ref={stage} tabIndex={artifact.media.video ? -1 : undefined}>
        {onOpen && artifact.media.kind === 'image' ? (
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
            keyboardScope="dialog"
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
            {artifact.outputNodeTitle || t('artifactCollection.output')}
            {artifact.outputNodeId && ` · ${artifact.outputNodeId}`}
            {artifact.outputSlot && ` / ${artifact.outputSlot}`} · {artifact.outputIndex + 1}
          </span>
          <span>
            {artifactFormat(artifact)} · {fileSizeLabel(artifact.size)}
          </span>
        </div>
        <div className="collection-actions">
          {onOpen && (expanded || artifact.media.kind !== 'audio') && (
            <Button
              size="small"
              onClick={(event) => {
                onOpen(event.currentTarget);
                if (!expanded && artifact.media.video)
                  stage.current?.focus({ preventScroll: true });
              }}
            >
              {expanded ? <ExitFullScreenIcon /> : <EnterFullScreenIcon />}
              {expanded ? closeLabel : t('artifactCollection.zoomIn')}
            </Button>
          )}
          {compare && artifact.media.kind === 'image' && (
            <ResultComparison key={artifact.id} artifact={artifact} />
          )}
          <DownloadOriginal media={artifact.media} filename={artifact.filename} />
          {typeof actions === 'function' ? actions(positionMs) : actions}
        </div>
      </div>
    </div>
  );
}

type ArtifactSource = { executionId?: string; workId?: string };

export function useArtifactPages(source: ArtifactSource) {
  const { api, state, workspaceScope } = useWorkspace();
  return useInfiniteQuery({
    queryKey: ['artifacts', state.userId, source, ...workspaceKey(workspaceScope)],
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
              closeLabel={t('artifactCollection.backToOutputs')}
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
        label={t('artifactCollection.noOutputsYet')}
      />
    </div>
  );
}
