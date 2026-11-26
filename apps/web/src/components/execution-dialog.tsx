/** 单次执行的详情弹框：浏览成品与生成参数，删除成品、发布作品和载入历史参数。 */
import { locale } from '../app/language.ts';
import { t } from '../app/i18n.ts';
import { refreshPublishedContent } from '../app/publication-queries';
import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router';
import type { Artifact, Execution, Work } from '@comfyshop/api-client';
import { Button, Tabs } from '@comfyshop/ui';
import { useWorkspace } from '../app/use-workspace';
import { projectsPath, workspaceKey, workspacePath } from '../app/workspace-scope';
import { useResultRoute } from '../app/result-route';
import type { ReplayAction } from '../domain/types';
import { assetUsageKey, useAssetLibraryActions } from '../features/assets/asset-queries';
import { TaskProjectButton } from '../features/projects/task-project-button';
import {
  ArtifactDisplay,
  ArtifactTabs,
  AssetGallery,
  useArtifactPages,
} from './artifact-collection';
import { BrowseDialog } from './browse-dialog-content';
import { CollectionStatus } from './collection-status';
import { CoverDialog } from './cover-dialog';
import { DeleteButton } from './delete-button';
import { durationLabel } from './generation-stage';
import { ExecutionPublicationBar } from './execution-publication-bar';
import { useNotify } from './notify';
import { PublishWorkDialog } from './publish-work-dialog';
import { RecordedInputs } from './recorded-inputs';
import {
  collectionFeed,
  useCollectionFocus,
  useCollectionNavigation,
} from './use-collection-navigation';
import type { CollectionPages } from './use-collection-navigation';
import { useAction } from './use-action';
import { useWorkPublication } from './use-work-publication';
import { workLink } from '../app/workflow-route';
import { ContinueInpaint } from '../features/workflows/continue-inpaint';

export const countLabel = (execution: Execution) =>
  [
    execution.imageCount ? t('executionDialog.images', execution.imageCount) : '',
    execution.videoCount ? t('executionDialog.videos', execution.videoCount) : '',
    execution.audioCount ? t('executionDialog.audioFiles', execution.audioCount) : '',
    execution.modelCount ? t('executionDialog.dModels', execution.modelCount) : '',
    execution.textCount ? t('executionDialog.textFiles', execution.textCount) : '',
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
  showSourceTask,
  projectId,
}: {
  initialExecution: Execution;
  pages: CollectionPages<Execution>;
  select: (execution: Execution) => void;
  onClose: () => void;
  restoreFocus?: () => void;
  onReplay?: ReplayAction;
  showSourceTask?: boolean;
  projectId?: string;
}) {
  const { api, state, workspaceScope, canEditWorkspace, canManageWorkspace } = useWorkspace();
  const library = useAssetLibraryActions();
  const notify = useNotify();
  const queries = useQueryClient();
  const [execution, setExecution] = useState(initialExecution);
  const [tab, setTab] = useState('artifacts');
  const [publishedWork, setPublishedWork] = useState<Work>();
  const [editingCoverId, setEditingCoverId] = useState<string>();
  const coverAction = useRef<HTMLButtonElement>(null);
  const { resultId, artifactId, openArtifact, closeArtifact } = useResultRoute();
  const query = useArtifactPages({ executionId: execution.id });
  const workflow = useQuery({
    queryKey: [
      'workflows',
      'detail',
      state.userId,
      execution.workflowId,
      ...workspaceKey(workspaceScope),
    ],
    queryFn: ({ signal }) => api.workflow(execution.workflowId, signal),
    enabled: canManageWorkspace,
  });
  const [scrollRoot, setScrollRoot] = useState<HTMLDivElement | null>(null);
  const {
    fallbackRef: galleryRef,
    rememberFocus: rememberAssetFocus,
    restoreFocus: restoreAssetFocus,
  } = useCollectionFocus();
  const selectionHintId = useId();
  const {
    busy,
    error,
    run: action,
    clearError,
  } = useAction(t('app.theActionFailed'), execution.id);
  if (execution.id !== initialExecution.id) {
    setExecution(initialExecution);
    setTab('artifacts');
  }
  const feed = collectionFeed(query);
  const { items } = feed;
  const assetId = resultId === execution.id ? artifactId : null;
  const selected = items.find((asset) => asset.id === assetId);
  const { data: artifactPages, hasNextPage, isFetching, isError, fetchNextPage } = query;
  useEffect(() => {
    if (assetId && !selected && hasNextPage && !isFetching && !isError)
      void fetchNextPage({ cancelRefetch: false });
  }, [assetId, selected, hasNextPage, isFetching, isError, fetchNextPage]);
  const artifactCount = execution.artifactCount;
  const editingCover = editingCoverId === execution.id;
  const single = artifactCount === 1 ? items[0] : null;
  const listPosition = useRef({ executionId: '', assetId: '', top: 0 });
  const previousAsset = useRef<string | null>(null);
  useLayoutEffect(() => {
    const prior = previousAsset.current;
    previousAsset.current = assetId;
    const gallery = galleryRef.current;
    if (!prior || assetId || !scrollRoot || !gallery) return;
    const position = listPosition.current;
    const focusId = position.executionId === execution.id ? position.assetId : prior;
    const stillListed = artifactPages?.pages.some((page) =>
      page.items.some((item) => item.id === focusId),
    );
    // 全屏切回弹框时瀑布流会按宽度重算。等同一张卡片稳定后交还焦点。
    const expires = performance.now() + 400;
    let frame = 0;
    let stable = 0;
    const restore = (now: number) => {
      if (position.executionId === execution.id) scrollRoot.scrollTop = position.top;
      const cards = Array.from(gallery.querySelectorAll<HTMLElement>('[data-media-id]'));
      const card = cards.find((item) => item.dataset.mediaId === focusId);
      if (card?.getClientRects().length) {
        stable = document.activeElement === card ? stable + 1 : 0;
        if (!stable) card.focus({ preventScroll: true });
      } else stable = 0;
      if (stillListed && stable < 5 && now < expires) frame = requestAnimationFrame(restore);
      else if (!card || document.activeElement !== card) restoreAssetFocus();
    };
    frame = requestAnimationFrame(restore);
    return () => cancelAnimationFrame(frame);
  }, [assetId, execution.id, galleryRef, scrollRoot, restoreAssetFocus, artifactPages]);
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
    busy || selecting || editingCover || !!publication.draft || !!assetId,
  );
  // 多份成品里点开的那一份在本弹框内放大，方向键和两侧箭头改为在成品之间切换。
  const assetNavigation = useCollectionNavigation(
    query,
    selected?.id ?? '',
    (asset) => {
      clearError();
      openArtifact(execution.id, asset.id);
    },
    busy || editingCover,
  );
  function showAsset(asset: Artifact, source: HTMLElement) {
    rememberAssetFocus(source);
    listPosition.current = {
      executionId: execution.id,
      assetId: asset.id,
      top: scrollRoot?.scrollTop ?? 0,
    };
    openArtifact(execution.id, asset.id);
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
    const keys = scopes.length
      ? scopes.map((key) => [key])
      : [['executions'], ['artifacts'], ['workflows'], assetUsageKey(state.userId, workspaceScope)];
    return Promise.all(keys.map((queryKey) => queries.invalidateQueries({ queryKey })));
  }
  /** 单份成品的操作。`positionMs` 是视频当前的播放位置，用来把这一刻的画面选作组封面。 */
  function assetActions(asset: Artifact, positionMs: number) {
    const isCover = !execution.coverImage && asset.id === execution.coverArtifactId;
    const chosenFrame = isCover ? (execution.coverFrameMs ?? 0) : null;
    return (
      <>
        {asset.media.kind === 'image' && (
          <ContinueInpaint
            key={asset.id}
            artifact={asset}
            sourceWorkflowId={execution.workflowId}
            projectId={projectId}
            disabled={busy || selecting || !!navigation?.pending}
          />
        )}
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
              {chosenFrame === positionMs
                ? t('executionDialog.currentResultCover')
                : t('executionDialog.useThisFrameAsTheResult')}
            </Button>
            {isCover && (
              <span className="form-hint" role="status">
                {chosenFrame
                  ? t('executionDialog.coverFrameAt', durationLabel(chosenFrame))
                  : t('executionDialog.coverUsesTheFirstFrame')}
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
              {isCover
                ? t('executionDialog.currentResultCover')
                : t('executionDialog.setAsResultCover')}
            </Button>
          )
        )}
        {asset.media.kind !== 'text' &&
          (asset.media.kind !== '3d' || asset.contentType === 'model/gltf-binary') && (
            <Button
              size="small"
              disabled={busy || selecting || !!navigation?.pending}
              onClick={() =>
                void action(async () => {
                  await library.saveArtifact(asset.id);
                  notify(t('assetLibrary.saved'));
                })
              }
            >
              {t('assetLibrary.save')}
            </Button>
          )}
        <DeleteButton
          label={t('executionDialog.deleteOutput')}
          done={t('executionDialog.outputDeleted')}
          undo={() => ({
            label: t('executionDialog.undo'),
            run: async () => {
              const restored = await api.restoreArtifact(asset.id);
              setExecution((current) => (current.id === restored.id ? restored : current));
              await refresh();
            },
          })}
          description={t('executionDialog.willBeHiddenTheOriginalFile', asset.filename)}
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
              if (assetId) closeArtifact();
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
      onClose={assetId ? closeArtifact : onClose}
      restoreFocus={restoreFocus}
      actions={
        <>
          {canEditWorkspace && !selecting && artifactCount > 0 && (
            <Button
              ref={coverAction}
              size="small"
              disabled={busy || navigation?.pending}
              onClick={() => setEditingCoverId(execution.id)}
            >
              {t('executionDialog.changeCover')}
            </Button>
          )}
          {canEditWorkspace && onReplay && (
            <Button
              size="small"
              disabled={busy}
              onClick={(event) => {
                const source = event.currentTarget;
                void action(async () => {
                  const replay = await api.replayExecution(execution.id);
                  onReplay(replay, source);
                });
              }}
            >
              {t('executionDialog.loadParameters')}
            </Button>
          )}
          {showSourceTask && !selecting && (
            <Button asChild size="small" variant="ghost">
              <Link
                to={
                  projectId
                    ? `${projectsPath(workspaceScope, projectId)}?${new URLSearchParams({ tab: 'tasks', task: execution.taskId })}`
                    : `${workspacePath(workspaceScope, 'tasks')}?${new URLSearchParams({ task: execution.taskId })}`
                }
                state={{ fromResult: true }}
              >
                {t('executionDialog.viewSourceTask')}
              </Link>
            </Button>
          )}
          {!selecting && (
            <TaskProjectButton
              taskId={execution.taskId}
              ownerId={execution.taskOwnerId}
              projectId={execution.projectId}
              disabled={busy || navigation?.pending}
              onChanged={(next) => {
                setExecution((current) => ({ ...current, projectId: next }));
                if (projectId && next !== projectId) onClose();
              }}
            />
          )}
          {canManageWorkspace && !selecting && !draftWorkflow && !publication.published && (
            <Button
              ref={publicationAction}
              size="small"
              disabled={!canStartPublication || workflow.isPending}
              onClick={beginPublication}
            >
              {artifactCount > 1
                ? t('executionDialog.selectOutputsToPublish')
                : t('executionDialog.publishWork')}
            </Button>
          )}
          {canEditWorkspace && !selecting && artifactCount > 1 && (
            <DeleteButton
              label={t('executionDialog.deleteResult')}
              done={t('executionDialog.resultDeleted')}
              undo={() => ({
                label: t('executionDialog.undo'),
                run: async () => {
                  await api.restoreExecutionArtifacts(execution.id);
                  await refresh();
                },
              })}
              description={t('executionDialog.allRemainingOutputsFromThisRun')}
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
          <ArtifactTabs label={t('executionDialog.runResults')} inputsDisabled={selecting} />
          <div className="preview-caption">
            <span>{t('executionDialog.run', countLabel(execution), execution.index + 1)}</span>
            <span>{new Date(execution.created).toLocaleString(locale)}</span>
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
                compare
                artifact={single}
                expanded={selected?.id === single.id}
                onOpen={(source) =>
                  selected?.id === single.id ? closeArtifact() : showAsset(single, source)
                }
                actions={
                  canEditWorkspace ? (position) => assetActions(single, position) : undefined
                }
              />
            ) : (
              <>
                {selected && (
                  <ArtifactDisplay
                    compare
                    key={selected.id}
                    artifact={selected}
                    expanded
                    closeLabel={t('artifactCollection.backToOutputs')}
                    onOpen={closeArtifact}
                    actions={
                      canEditWorkspace ? (position) => assetActions(selected, position) : undefined
                    }
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
                      else showAsset(asset, source);
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
              label={t('artifactCollection.noOutputsYet')}
            />
            {assetId && !selected && !query.isPending && !hasNextPage && !isError && (
              <div className="inline-status" role="alert">
                {t('executionDialog.thisOutputIsUnavailable')}
                <Button size="small" onClick={closeArtifact}>
                  {t('artifactCollection.backToOutputs')}
                </Button>
              </div>
            )}
          </div>
        </Tabs.Content>
        <Tabs.Content value="inputs" className="collection-scroll">
          <RecordedInputs
            taskId={execution.taskId}
            values={execution.inputValues}
            effectivePrompt={execution.effectivePrompt}
            promptExpanded={execution.promptExpanded}
          />
        </Tabs.Content>
      </Tabs.Root>
      {canManageWorkspace && (
        <ExecutionPublicationBar
          draftWorkflow={draftWorkflow}
          selecting={selecting}
          chosenCount={publication.chosenAssets.length}
          published={publication.published}
          publishedLink={
            publishedWork?.executionId === execution.id ? workLink(publishedWork) : undefined
          }
          worksPath={workspacePath(workspaceScope, 'artworks')}
          canStart={canStartPublication}
          hintId={selectionHintId}
          actionRef={publicationAction}
          onBegin={beginPublication}
          onCancel={publication.cancelSelection}
          onReview={publication.review}
        />
      )}
      {error && !selected && (
        <p className="form-error collection-error" role="alert">
          {error}
        </p>
      )}
      {canEditWorkspace && editingCover && (
        <CoverDialog
          key={`cover:${execution.id}`}
          title={t('executionDialog.changeResultCover')}
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
      {canManageWorkspace && publication.draft && (
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
            void refreshPublishedContent(queries);
          }}
        />
      )}
    </BrowseDialog>
  );
}
