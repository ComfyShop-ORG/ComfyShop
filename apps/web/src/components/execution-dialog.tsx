/** 单次执行的详情弹框：浏览成品与生成参数，删除成品、发布作品和载入历史参数。 */
import { useId, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { Artifact, Execution, Work } from '@comfyshop/api-client';
import { Button, Tabs } from '@comfyshop/ui';
import { useWorkspace } from '../app/use-workspace';
import type { ReplayAction } from '../domain/types';
import { ArtifactDisplay, AssetGallery, useArtifactPages } from './artifact-collection';
import { BrowseDialog } from './browse-dialog-content';
import { CollectionStatus } from './collection-status';
import { CoverDialog } from './cover-dialog';
import { DeleteButton } from './delete-button';
import { durationLabel } from './generation-stage';
import { ExecutionPublicationBar } from './execution-publication-bar';
import { PublishWorkDialog } from './publish-work-dialog';
import { RecordedInputs } from './recorded-inputs';
import {
  collectionFeed,
  useCollectionNavigation,
  useCollectionSelection,
} from './use-collection-navigation';
import type { CollectionPages } from './use-collection-navigation';
import { useAction } from './use-action';
import { useWorkPublication } from './use-work-publication';
import { workLink } from '../app/workflow-route';

export const countLabel = (execution: Execution) =>
  [
    execution.imageCount ? `${execution.imageCount} 张图片` : '',
    execution.videoCount ? `${execution.videoCount} 个视频` : '',
    execution.audioCount ? `${execution.audioCount} 份音频` : '',
    execution.modelCount ? `${execution.modelCount} 个 3D 模型` : '',
  ]
    .filter(Boolean)
    .join(' · ');

export function ExecutionDialog({
  initialExecution,
  pages,
  select,
  onClose,
  restoreFocus,
  onReplay,
}: {
  initialExecution: Execution;
  pages: CollectionPages<Execution>;
  select: (execution: Execution) => void;
  onClose: () => void;
  restoreFocus?: () => void;
  onReplay?: ReplayAction;
}) {
  const { api, state } = useWorkspace();
  const queries = useQueryClient();
  const [execution, setExecution] = useState(initialExecution);
  const [tab, setTab] = useState('artifacts');
  const [publishedWork, setPublishedWork] = useState<Work>();
  const [editingCoverId, setEditingCoverId] = useState<string>();
  const coverAction = useRef<HTMLButtonElement>(null);
  // 只有一份成品时在本弹框内放大，不再叠加一层预览。
  const [expanded, setExpanded] = useState(false);
  const query = useArtifactPages({ executionId: execution.id });
  const workflow = useQuery({
    queryKey: ['workflows', 'detail', state.userId, execution.workflowId],
    queryFn: ({ signal }) => api.workflow(execution.workflowId, signal),
  });
  const [scrollRoot, setScrollRoot] = useState<HTMLDivElement | null>(null);
  const {
    selected,
    select: selectAsset,
    fallbackRef: galleryRef,
    open: openAsset,
    close: closeAsset,
    restoreFocus: restoreAssetFocus,
  } = useCollectionSelection<Artifact>();
  const selectionHintId = useId();
  const { busy, error, run: action, clearError } = useAction('操作失败', execution.id);
  if (execution.id !== initialExecution.id) {
    setExecution(initialExecution);
    setTab('artifacts');
  }
  const feed = collectionFeed(query);
  const { items } = feed;
  const artifactCount = execution.artifactCount;
  const editingCover = editingCoverId === execution.id;
  const single = artifactCount === 1 ? items[0] : null;
  // 挂在当前可见的发布入口上：未选择时是“发布作品”，选择中是“下一步”。
  const publicationAction = useRef<HTMLButtonElement>(null);
  function focusPublicationAction() {
    requestAnimationFrame(() => publicationAction.current?.focus({ preventScroll: true }));
  }
  const publication = useWorkPublication(
    execution.id,
    items,
    single,
    () => galleryRef.current?.focus({ preventScroll: true }),
    focusPublicationAction,
  );
  const { selecting } = publication;
  const navigation = useCollectionNavigation(
    pages,
    execution.id,
    select,
    busy || selecting || editingCover || !!publication.draft || !!selected,
  );
  // 多份成品里点开的那一份在本弹框内放大，方向键和两侧箭头改为在成品之间切换。
  const assetNavigation = useCollectionNavigation(
    query,
    selected?.id ?? '',
    (asset) => {
      clearError();
      selectAsset(asset);
    },
    busy || editingCover,
  );
  function leaveAsset() {
    closeAsset();
    requestAnimationFrame(restoreAssetFocus);
  }
  // 发布工作流会公开它的最新版本。只有这次执行来自最新版本时，才能先发布工作流再发布作品；
  // 来自其他未发布版本的结果由平台在提交时说明原因。
  const draftWorkflow =
    workflow.data?.published === false && workflow.data.versionId === execution.versionId
      ? workflow.data
      : undefined;
  const canStartPublication = items.length > 0 && !busy && !navigation?.pending;
  function beginPublication() {
    setTab('artifacts');
    publication.begin();
  }
  function refresh(...scopes: Array<'executions' | 'artifacts' | 'workflows'>) {
    const keys = scopes.length ? scopes : (['executions', 'artifacts', 'workflows'] as const);
    return Promise.all(keys.map((key) => queries.invalidateQueries({ queryKey: [key] })));
  }
  /** 单份成品的操作。`positionMs` 是视频当前的播放位置，用来把这一刻的画面选作组封面。 */
  function assetActions(asset: Artifact, positionMs: number) {
    const isCover = !execution.coverImage && asset.id === execution.coverArtifactId;
    const chosenFrame = isCover ? (execution.coverFrameMs ?? 0) : null;
    return (
      <>
        {asset.media.video ? (
          <>
            <Button
              size="small"
              disabled={busy || chosenFrame === positionMs}
              onClick={() =>
                void action(async () => {
                  setExecution(
                    await api.setExecutionCover(execution.id, {
                      artifactId: asset.id,
                      frameMs: positionMs,
                    }),
                  );
                  await refresh('executions');
                })
              }
            >
              {chosenFrame === positionMs ? '当前组封面' : '用当前画面作组封面'}
            </Button>
            {isCover && (
              <span className="form-hint" role="status">
                {chosenFrame ? `组封面取自 ${durationLabel(chosenFrame)}` : '组封面取自首帧'}
              </span>
            )}
          </>
        ) : (
          asset.media.kind === 'image' &&
          (artifactCount > 1 || !!execution.coverImage) && (
            <Button
              size="small"
              disabled={busy || isCover}
              onClick={() =>
                void action(async () => {
                  setExecution(await api.setExecutionCover(execution.id, { artifactId: asset.id }));
                  await refresh('executions');
                })
              }
            >
              {isCover ? '当前组封面' : '设为组封面'}
            </Button>
          )
        )}
        <DeleteButton
          label="删除成品"
          done="已删除成品"
          undo={() => ({
            label: '撤销',
            run: async () => {
              const restored = await api.restoreArtifact(asset.id);
              setExecution((current) => (current.id === restored.id ? restored : current));
              await refresh();
            },
          })}
          description={`将隐藏「${asset.filename}」，原文件保留在平台存储。`}
          disabled={busy || selecting || !!navigation?.pending}
          onDelete={async () => {
            const next = await api.deleteArtifact(asset.id);
            if (next.artifactCount > 0) await refresh();
            return next;
          }}
          onDeleted={(next) => {
            clearError();
            if (next.artifactCount === 0) {
              onClose();
              void refresh();
            } else {
              setExecution(next);
              closeAsset();
            }
          }}
        />
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
      </>
    );
  }
  return (
    <BrowseDialog
      className="result-dialog"
      itemId={selected?.id ?? execution.id}
      title={execution.workflowName}
      navigation={selected ? assetNavigation : navigation}
      onClose={onClose}
      onEscape={() => {
        if (selected) leaveAsset();
        else if (expanded) setExpanded(false);
        else return false;
        return true;
      }}
      restoreFocus={restoreFocus}
      actions={
        <>
          {!selecting && artifactCount > 0 && (
            <Button
              ref={coverAction}
              size="small"
              disabled={busy || navigation?.pending}
              onClick={() => setEditingCoverId(execution.id)}
            >
              更换封面
            </Button>
          )}
          {onReplay && (
            <Button
              size="small"
              disabled={busy}
              onClick={(event) => {
                const source = event.currentTarget;
                void action(async () => {
                  const replay = await api.replayExecution(execution.id);
                  onClose();
                  onReplay(replay, source);
                });
              }}
            >
              载入参数
            </Button>
          )}
          {!selecting && !draftWorkflow && !publication.published && (
            <Button
              ref={publicationAction}
              size="small"
              disabled={!canStartPublication || workflow.isPending}
              onClick={beginPublication}
            >
              {artifactCount > 1 ? '选择成品发布' : '发布作品'}
            </Button>
          )}
          {!selecting && artifactCount > 1 && (
            <DeleteButton
              label="删除整组结果"
              done="已删除这组结果"
              undo={() => ({
                label: '撤销',
                run: async () => {
                  await api.restoreExecutionArtifacts(execution.id);
                  await refresh();
                },
              })}
              description="将隐藏本次执行剩余的所有成品，原文件保留在平台存储。"
              disabled={busy || navigation?.pending}
              onDelete={() => api.deleteExecutionArtifacts(execution.id)}
              onDeleted={() => {
                onClose();
                void refresh();
              }}
            />
          )}
        </>
      }
    >
      <Tabs.Root key={execution.id} className="dialog-tabs" value={tab} onValueChange={setTab}>
        <div className="dialog-tab-row">
          <Tabs.List className="dialog-tab-list" aria-label="执行结果">
            <Tabs.Trigger value="artifacts" asChild>
              <Button size="small" variant="ghost">
                成品
              </Button>
            </Tabs.Trigger>
            <Tabs.Trigger value="inputs" asChild disabled={selecting}>
              <Button size="small" variant="ghost">
                生成参数
              </Button>
            </Tabs.Trigger>
          </Tabs.List>
          <div className="preview-caption">
            <span>
              {countLabel(execution)} · 第 {execution.index + 1} 次执行
            </span>
            <span>{new Date(execution.created).toLocaleString('zh-CN')}</span>
          </div>
        </div>
        <Tabs.Content value="artifacts" className="collection-scroll" ref={setScrollRoot}>
          <div
            ref={galleryRef}
            tabIndex={-1}
            aria-describedby={selecting ? selectionHintId : undefined}
            className={single || selected ? 'single-artifact' : undefined}
          >
            {single ? (
              <ArtifactDisplay
                artifact={single}
                expanded={expanded}
                onOpen={() => setExpanded(!expanded)}
                actions={(position) => assetActions(single, position)}
              />
            ) : (
              <>
                {selected && (
                  <ArtifactDisplay
                    key={selected.id}
                    artifact={selected}
                    expanded
                    closeLabel="返回成品列表"
                    onOpen={leaveAsset}
                    actions={(position) => assetActions(selected, position)}
                  />
                )}
                <div hidden={!!selected}>
                  <AssetGallery
                    {...feed}
                    resetKey={execution.id}
                    scrollRoot={scrollRoot}
                    selected={selecting ? publication.chosen : undefined}
                    onOpen={(asset, source) => {
                      if (selecting) publication.toggle(asset);
                      else openAsset(asset, source);
                    }}
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
        </Tabs.Content>
        <Tabs.Content value="inputs" className="collection-scroll">
          <RecordedInputs taskId={execution.taskId} values={execution.inputValues} />
        </Tabs.Content>
      </Tabs.Root>
      <ExecutionPublicationBar
        draftWorkflow={draftWorkflow}
        selecting={selecting}
        chosenCount={publication.chosenAssets.length}
        published={publication.published}
        publishedLink={
          publishedWork?.executionId === execution.id ? workLink(publishedWork) : undefined
        }
        canStart={canStartPublication}
        hintId={selectionHintId}
        actionRef={publicationAction}
        onBegin={beginPublication}
        onCancel={publication.cancelSelection}
        onReview={publication.review}
      />
      {error && !selected && (
        <p className="form-error collection-error" role="alert">
          {error}
        </p>
      )}
      {editingCover && (
        <CoverDialog
          key={`cover:${execution.id}`}
          title="更换结果封面"
          record={execution}
          artifacts={query}
          restoreFocus={() => coverAction.current?.focus({ preventScroll: true })}
          onClose={() => setEditingCoverId(undefined)}
          onSave={async (choice) => {
            setExecution(await api.setExecutionCover(execution.id, choice));
            await refresh('executions');
          }}
        />
      )}
      {publication.draft && (
        <PublishWorkDialog
          execution={execution}
          assets={publication.draft}
          outputs={query}
          returnToSelection={selecting}
          restoreFocus={focusPublicationAction}
          onClose={publication.closeDraft}
          onPublished={(work) => {
            setPublishedWork(work);
            publication.completed();
            // 工作流封面取自作品，发布后工作流列表也要刷新。
            void queries.invalidateQueries({ queryKey: ['works'] });
            void queries.invalidateQueries({ queryKey: ['workflows'] });
          }}
        />
      )}
    </BrowseDialog>
  );
}
