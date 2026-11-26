/** 展示公共或个人作品，详情只加载该作品选中的成品。 */
import { t } from '../app/i18n.ts';
import { refreshPublishedContent } from '../app/publication-queries';
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router';
import type { Artifact, Work } from '@comfyshop/api-client';
import { Button, Select, Tabs } from '@comfyshop/ui';
import { useWorks, useWorkspace } from '../app/use-workspace';
import type { ReplayAction } from '../domain/types';
import { useWorkflowListFilters } from '../app/use-workflow-list-filters';
import { workflowCategoryMenu } from '../domain/workflow-categories';
import type { RequireAuth } from '../features/auth/login-dialog';
import { workLink } from '../app/workflow-route';
import { workspaceKey, workspacePath } from '../app/workspace-scope';
import { ArtifactCollection, ArtifactTabs, useArtifactPages } from './artifact-collection';
import { BrowseDialog } from './browse-dialog-content';
import { CopyLink } from './copy-link';
import { CoverDialog } from './cover-dialog';
import { DeleteButton } from './delete-button';
import { MediaCollection } from './media-grid';
import { PageToolbar } from './page-toolbar';
import { RecordedInputs } from './recorded-inputs';
import { AttributionLinks, CardAttribution } from './publication-attribution';
import type { CardView } from './media-grid';
import { useAction } from './use-action';
import { useCollectionNavigation, useCollectionSelection } from './use-collection-navigation';
import type { CollectionPages } from './use-collection-navigation';

function workCard(work: Work, showTeam = false): CardView {
  return {
    label: t('workCollection.viewWork', work.title),
    title: work.title,
    media: work.media,
    coverImage: work.coverImage,
    detail: (
      <>
        <CardAttribution content={work} showTeam={showTeam} />
        <span className={work.published ? 'media-card-dimensions' : undefined}>
          {t('workCollection.outputCount', work.assetCount)}
          {!work.published && t('workCollection.unpublished')}
        </span>
      </>
    ),
  };
}

function publicWorkCard(work: Work): CardView {
  return workCard(work, true);
}

export function WorkCollection({
  workflowId,
  versionId,
  linkedWork,
  onLinkedWorkClose,
  scope = 'public',
  author,
  publicTeamId,
  projectId,
  scrollRoot,
  referenceWidth,
  emptyAction,
  onReplay,
  replayAfterSignIn,
  requireAuth,
}: {
  workflowId?: string;
  versionId?: string;
  linkedWork?: Work;
  onLinkedWorkClose?: () => void;
  scope?: 'public' | 'mine';
  /** 只看这位作者公开的作品，值为账号名。 */
  author?: string;
  publicTeamId?: string;
  projectId?: string;
  scrollRoot?: HTMLElement | null;
  referenceWidth?: string;
  emptyAction?: ReactNode;
  onReplay?: ReplayAction;
  /** 访客点「载入参数」时，登录后由不随身份重建的页面载入这件作品的参数。 */
  replayAfterSignIn?: (source: { workId: string }) => void;
  requireAuth?: RequireAuth;
}) {
  const filters = useWorkflowListFilters();
  const { workspaceScope, canManageWorkspace } = useWorkspace();
  const category = workflowId ? 'all' : filters.category;
  const query = useWorks(workflowId, scope, author, category, versionId, publicTeamId, projectId);
  const { selected, select, fallbackRef, open, close, restoreFocus } =
    useCollectionSelection<Work>();
  useEffect(() => {
    if (linkedWork) select(linkedWork);
  }, [linkedWork, select]);
  function closeWork() {
    close();
    if (linkedWork) onLinkedWorkClose?.();
  }
  return (
    <>
      {!workflowId && (
        <PageToolbar>
          <Select
            label={t('workCollection.workCategory')}
            value={category}
            options={workflowCategoryMenu}
            onValueChange={filters.setCategory}
          />
        </PageToolbar>
      )}
      <div ref={fallbackRef} tabIndex={-1}>
        <MediaCollection
          query={query}
          label={t('workCollection.works')}
          resetKey={JSON.stringify([
            workspaceScope,
            workflowId,
            versionId,
            scope,
            author,
            publicTeamId,
            category,
            projectId,
          ])}
          scrollRoot={scrollRoot}
          fillSparse={!!scrollRoot}
          referenceWidth={referenceWidth}
          view={scope === 'public' && !author && !publicTeamId ? publicWorkCard : workCard}
          onOpen={open}
          emptyLabel={t('workCollection.noWorksYet')}
          emptyAction={
            emptyAction ??
            (canManageWorkspace && scope === 'mine' && (
              <Button asChild size="small">
                <Link to={workspacePath(workspaceScope, 'results')}>
                  {t('workCollection.publishAWorkFromResults')}
                </Link>
              </Button>
            ))
          }
        />
      </div>
      {selected && (
        <WorkDialog
          work={selected}
          pages={query}
          select={select}
          onClose={closeWork}
          onTeamClick={
            publicTeamId && publicTeamId === selected.publicTeam?.id ? closeWork : undefined
          }
          restoreFocus={restoreFocus}
          onReplay={onReplay}
          replayAfterSignIn={replayAfterSignIn}
          requireAuth={requireAuth}
        />
      )}
    </>
  );
}

function WorkDialog({
  work,
  pages,
  select,
  onClose,
  onTeamClick,
  restoreFocus,
  onReplay,
  replayAfterSignIn,
  requireAuth,
}: {
  work: Work;
  pages: CollectionPages<Work>;
  select: (work: Work) => void;
  onClose: () => void;
  onTeamClick?: () => void;
  restoreFocus: () => void;
  onReplay?: ReplayAction;
  replayAfterSignIn?: (source: { workId: string }) => void;
  requireAuth?: RequireAuth;
}) {
  const { api, state, workspaceScope, workspaceTeam, canManageWorkspace, canEditWorkspace } =
    useWorkspace();
  const queries = useQueryClient();
  const [scrollRoot, setScrollRoot] = useState<HTMLDivElement | null>(null);
  const [editingCoverId, setEditingCoverId] = useState<string>();
  const coverAction = useRef<HTMLButtonElement>(null);
  const editingCover = editingCoverId === work.id;
  const { busy, error, run } = useAction(t('app.theActionFailed'), work.id);
  const navigation = useCollectionNavigation(pages, work.id, select, busy || editingCover);
  const mine =
    canManageWorkspace &&
    (workspaceTeam
      ? work.teamId === workspaceTeam.id
      : !work.teamId && work.owner === state.userId);
  // 作者可以把自己的公开作品指定为工作流封面。来源工作流不可读时不提供这个操作。
  const workflow = useQuery({
    queryKey: [
      'workflows',
      'detail',
      state.userId,
      work.workflowId,
      ...workspaceKey(workspaceScope),
    ],
    queryFn: ({ signal }) => api.workflow(work.workflowId, signal),
    enabled: mine && work.published,
    retry: false,
  });
  const pinned = workflow.data?.coverWorkId === work.id;
  const usesWorkCover =
    work.published &&
    !!workflow.data &&
    (workspaceTeam
      ? workflow.data.teamId === workspaceTeam.id
      : !workflow.data.teamId && workflow.data.owner === state.userId);
  const shared = Object.keys(work.inputValues).length > 0;
  const [tab, setTab] = useState('artifacts');
  // 成品在本弹框内放大：一份成品记 on，多份成品记当前放大的那一份。换作品后失效。
  const [zoom, setZoom] = useState<{ workId: string; on: boolean; asset: Artifact | null }>({
    workId: work.id,
    on: false,
    asset: null,
  });
  const current = zoom.workId === work.id ? zoom : { workId: work.id, on: false, asset: null };
  const artifacts = useArtifactPages({ workId: work.id });
  const focusAsset = (asset: Artifact | null) => setZoom({ ...current, asset });
  const assetNavigation = useCollectionNavigation(
    artifacts,
    current.asset?.id ?? '',
    focusAsset,
    busy || editingCover,
  );
  const outputs = (
    <ArtifactCollection
      query={artifacts}
      resetKey={work.id}
      scrollRoot={scrollRoot}
      focused={current.asset}
      onFocus={focusAsset}
      expanded={current.on}
      onExpandedChange={(on) => setZoom({ ...current, on })}
    />
  );
  return (
    <BrowseDialog
      className="result-dialog"
      itemId={current.asset?.id ?? work.id}
      title={work.title}
      navigation={current.asset ? assetNavigation : navigation}
      onClose={onClose}
      onEscape={() => {
        if (!current.on && !current.asset) return false;
        setZoom({ ...current, on: false, asset: null });
        return true;
      }}
      restoreFocus={restoreFocus}
      actions={
        <>
          {work.published && (
            <CopyLink
              href={workLink(work)}
              title={t('executionPublicationBar.workLink')}
              shareTitle={work.title}
            />
          )}
          {canEditWorkspace && onReplay && (
            <Button
              size="small"
              disabled={busy}
              onClick={(event) => {
                const source = event.currentTarget;
                const replay = () =>
                  run(async () => {
                    const loaded = await api.replayWork(work.id);
                    onClose();
                    onReplay(loaded, source);
                  });
                const reason = t('workCollection.signInToLoadTheParameters');
                // 登录后工作流弹框按新身份重建，这里的回调已不在页面上，交给页面载入。
                if (!state.user && requireAuth && replayAfterSignIn)
                  requireAuth(source, () => replayAfterSignIn({ workId: work.id }), reason);
                else if (requireAuth) requireAuth(source, replay, reason);
                else void replay();
              }}
            >
              {t('executionDialog.loadParameters')}
            </Button>
          )}
          {mine && (
            <Button
              ref={coverAction}
              size="small"
              disabled={busy || navigation?.pending}
              onClick={() => setEditingCoverId(work.id)}
            >
              {t('executionDialog.changeCover')}
            </Button>
          )}
          {mine && usesWorkCover && (
            <Button
              size="small"
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  await api.setWorkflowCover(work.workflowId, { workId: pinned ? null : work.id });
                  await queries.invalidateQueries({ queryKey: ['workflows'] });
                })
              }
            >
              {pinned
                ? t('workCollection.removeAsWorkflowCover')
                : t('workCollection.useAsWorkflowCover')}
            </Button>
          )}
          {mine && work.published && (
            <Button
              size="small"
              variant="ghost"
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  await api.unpublishWork(work.id);
                  await refreshPublishedContent(queries);
                  onClose();
                })
              }
            >
              {t('workCollection.unpublish')}
            </Button>
          )}
          {mine && (
            <DeleteButton
              label={t('workCollection.deleteWork')}
              done={t('workCollection.workDeleted')}
              undo={() => ({
                label: t('executionDialog.undo'),
                run: async () => {
                  await api.restoreWork(work.id);
                  await refreshPublishedContent(queries);
                },
              })}
              description={t('workCollection.willBeRemovedFromPublicView', work.title)}
              disabled={busy || navigation?.pending}
              onDelete={() => api.deleteWork(work.id)}
              onDeleted={() => {
                onClose();
                queries.removeQueries({
                  queryKey: ['artifacts', state.userId, { workId: work.id }],
                });
                void queries.invalidateQueries({
                  queryKey: ['works'],
                  predicate: ({ queryKey }) =>
                    queryKey[2] === undefined || queryKey[2] === work.workflowId,
                });
                void queries.invalidateQueries({ queryKey: ['workflows'] });
                void queries.invalidateQueries({ queryKey: ['public-team'] });
              }}
            />
          )}
        </>
      }
    >
      {editingCover && (
        <CoverDialog
          key={`cover:${work.id}`}
          title={t('workCollection.changeWorkCover')}
          note={
            pinned
              ? t('workCollection.thisWorkIsTheWorkflowCover')
              : usesWorkCover && !workflow.data?.coverWorkId
                ? t('workCollection.ifTheWorkflowUsesThisWork')
                : undefined
          }
          record={work}
          artifacts={artifacts}
          restoreFocus={() => coverAction.current?.focus({ preventScroll: true })}
          onClose={() => setEditingCoverId(undefined)}
          onSave={async (choice) => {
            const updated = await api.setWorkCover(work.id, choice);
            select(updated);
            void queries.invalidateQueries({ queryKey: ['works'] });
            void queries.invalidateQueries({ queryKey: ['workflows'] });
          }}
        />
      )}
      <div className="preview-caption">
        <span>
          {work.workflowName} ·{' '}
          <AttributionLinks content={work} teamTab="works" onTeamClick={onTeamClick} />
        </span>
        <span className="media-card-dimensions">
          {t('workCollection.outputCount', work.assetCount)}
        </span>
      </div>
      {work.description && <p className="work-description">{work.description}</p>}
      {shared ? (
        <Tabs.Root key={work.id} className="dialog-tabs" value={tab} onValueChange={setTab}>
          <ArtifactTabs label={t('workCollection.workContents')} />
          <Tabs.Content value="artifacts" className="collection-scroll" ref={setScrollRoot}>
            {outputs}
          </Tabs.Content>
          <Tabs.Content value="inputs" className="collection-scroll">
            <RecordedInputs workId={work.id} values={work.inputValues} />
          </Tabs.Content>
        </Tabs.Root>
      ) : (
        <div key={work.id} className="collection-scroll" ref={setScrollRoot}>
          {outputs}
        </div>
      )}
      {error && (
        <p className="form-error collection-error" role="alert">
          {error}
        </p>
      )}
    </BrowseDialog>
  );
}
