/** 展示公共或个人作品，详情只加载该作品选中的成品。 */
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router';
import type { Artifact, Work } from '@comfyshop/api-client';
import { Button, Select, Tabs } from '@comfyshop/ui';
import { useWorks, useWorkspace } from '../app/use-workspace';
import type { ReplayAction } from '../domain/types';
import { workflowCategoryFilters } from '../domain/workflow-categories';
import type { RequireAuth } from '../features/auth/login-dialog';
import { authorPath, workLink } from '../app/workflow-route';
import { ArtifactCollection, useArtifactPages } from './artifact-collection';
import { BrowseDialog } from './browse-dialog-content';
import { CopyLink } from './copy-link';
import { CoverDialog } from './cover-dialog';
import { DeleteButton } from './delete-button';
import { MediaCollection } from './media-grid';
import { RecordedInputs } from './recorded-inputs';
import { ProfileAvatar } from './profile-avatar';
import type { CardView } from './media-grid';
import { useAction } from './use-action';
import { useCollectionNavigation, useCollectionSelection } from './use-collection-navigation';
import type { CollectionPages } from './use-collection-navigation';

function workCard(work: Work): CardView {
  const author = work.authorProfile.nickname ?? work.author;
  return {
    label: `查看作品 ${work.title}`,
    title: work.title,
    media: work.media,
    coverImage: work.coverImage,
    detail: (
      <>
        <ProfileAvatar name={author} src={work.authorProfile.avatarUrl} />
        <span className="profile-name">{author}</span>
        <span>
          {work.assetCount} 份成品{!work.published && ' · 已取消公开'}
        </span>
      </>
    ),
  };
}

export function WorkCollection({
  workflowId,
  versionId,
  linkedWork,
  onLinkedWorkClose,
  scope = 'public',
  author,
  scrollRoot,
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
  scrollRoot?: HTMLElement | null;
  emptyAction?: ReactNode;
  onReplay?: ReplayAction;
  /** 访客点「载入参数」时，登录后由不随身份重建的页面载入这件作品的参数。 */
  replayAfterSignIn?: (source: { workId: string }) => void;
  requireAuth?: RequireAuth;
}) {
  const [params, setParams] = useSearchParams();
  const category = workflowId
    ? 'all'
    : (workflowCategoryFilters.find(({ value }) => value === params.get('category'))?.value ??
      'all');
  const query = useWorks(workflowId, scope, author, category, versionId);
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
        <div className="page-toolbar">
          <Select
            className="sort-select"
            label="作品分类"
            value={category}
            options={workflowCategoryFilters}
            onValueChange={(value) =>
              setParams(
                (current) => {
                  const next = new URLSearchParams(current);
                  if (value === 'all') next.delete('category');
                  else next.set('category', value);
                  return next;
                },
                { replace: true, preventScrollReset: true },
              )
            }
          />
        </div>
      )}
      <div ref={fallbackRef} tabIndex={-1}>
        <MediaCollection
          query={query}
          label="作品"
          resetKey={`${workflowId ?? 'all'}:${versionId ?? ''}:${scope}:${author ?? ''}:${category}`}
          scrollRoot={scrollRoot}
          fillSparse={!!scrollRoot}
          view={workCard}
          onOpen={open}
          emptyLabel="暂无作品"
          emptyAction={
            emptyAction ??
            (scope === 'mine' && (
              <Button asChild size="small">
                <Link to="/workspace/results">从结果发布作品</Link>
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
  restoreFocus,
  onReplay,
  replayAfterSignIn,
  requireAuth,
}: {
  work: Work;
  pages: CollectionPages<Work>;
  select: (work: Work) => void;
  onClose: () => void;
  restoreFocus: () => void;
  onReplay?: ReplayAction;
  replayAfterSignIn?: (source: { workId: string }) => void;
  requireAuth?: RequireAuth;
}) {
  const { api, state } = useWorkspace();
  const queries = useQueryClient();
  const [scrollRoot, setScrollRoot] = useState<HTMLDivElement | null>(null);
  const [editingCoverId, setEditingCoverId] = useState<string>();
  const coverAction = useRef<HTMLButtonElement>(null);
  const editingCover = editingCoverId === work.id;
  const { busy, error, run } = useAction('操作失败', work.id);
  const navigation = useCollectionNavigation(pages, work.id, select, busy || editingCover);
  const mine = work.owner === state.userId;
  // 作者可以把自己的公开作品指定为工作流封面。来源工作流不可读时不提供这个操作。
  const workflow = useQuery({
    queryKey: ['workflows', 'detail', state.userId, work.workflowId],
    queryFn: ({ signal }) => api.workflow(work.workflowId, signal),
    enabled: mine && work.published,
    retry: false,
  });
  const pinned = workflow.data?.coverWorkId === work.id;
  const usesWorkCover = work.published && workflow.data?.owner === state.userId;
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
          {work.published && <CopyLink href={workLink(work)} title="作品链接" />}
          {onReplay && (
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
                const reason = '登录后载入这件作品的参数';
                // 登录后工作流弹框按新身份重建，这里的回调已不在页面上，交给页面载入。
                if (!state.user && requireAuth && replayAfterSignIn)
                  requireAuth(source, () => replayAfterSignIn({ workId: work.id }), reason);
                else if (requireAuth) requireAuth(source, replay, reason);
                else void replay();
              }}
            >
              载入参数
            </Button>
          )}
          {mine && (
            <Button
              ref={coverAction}
              size="small"
              disabled={busy || navigation?.pending}
              onClick={() => setEditingCoverId(work.id)}
            >
              更换封面
            </Button>
          )}
          {mine && usesWorkCover && (
            <Button
              size="small"
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  await api.setWorkflowCover(work.workflowId, pinned ? null : work.id);
                  await queries.invalidateQueries({ queryKey: ['workflows'] });
                })
              }
            >
              {pinned ? '取消工作流封面' : '设为工作流封面'}
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
                  await queries.invalidateQueries({ queryKey: ['works'] });
                  await queries.invalidateQueries({ queryKey: ['workflows'] });
                  onClose();
                })
              }
            >
              取消公开
            </Button>
          )}
          {mine && (
            <DeleteButton
              label="删除作品"
              done="已删除作品"
              undo={() => ({
                label: '撤销',
                run: async () => {
                  await api.restoreWork(work.id);
                  await Promise.all([
                    queries.invalidateQueries({ queryKey: ['works'] }),
                    queries.invalidateQueries({ queryKey: ['workflows'] }),
                  ]);
                },
              })}
              description={`将移除「${work.title}」并撤销该作品的公开访问。源成品可在「结果」查看。`}
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
              }}
            />
          )}
        </>
      }
    >
      {editingCover && (
        <CoverDialog
          key={`cover:${work.id}`}
          title="更换作品封面"
          note={
            pinned
              ? '这件作品用作工作流封面，保存后工作流入口也会更新。'
              : usesWorkCover && !workflow.data?.coverWorkId
                ? '工作流使用这件作品作封面时，入口也会更新。'
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
          <Link className="author-link" to={authorPath(work.author)}>
            {work.authorProfile.nickname ?? work.author}
          </Link>
        </span>
        <span>{work.assetCount} 份成品</span>
      </div>
      {work.description && <p className="work-description">{work.description}</p>}
      {shared ? (
        <Tabs.Root key={work.id} className="dialog-tabs" value={tab} onValueChange={setTab}>
          <Tabs.List className="dialog-tab-list" aria-label="作品内容">
            <Tabs.Trigger value="artifacts" asChild>
              <Button size="small" variant="ghost">
                成品
              </Button>
            </Tabs.Trigger>
            <Tabs.Trigger value="inputs" asChild>
              <Button size="small" variant="ghost">
                生成参数
              </Button>
            </Tabs.Trigger>
          </Tabs.List>
          <Tabs.Content value="artifacts" className="collection-scroll" ref={setScrollRoot}>
            <ArtifactCollection
              query={artifacts}
              resetKey={work.id}
              scrollRoot={scrollRoot}
              focused={current.asset}
              onFocus={focusAsset}
              expanded={current.on}
              onExpandedChange={(on) => setZoom({ ...current, on })}
            />
          </Tabs.Content>
          <Tabs.Content value="inputs" className="collection-scroll">
            <RecordedInputs workId={work.id} values={work.inputValues} />
          </Tabs.Content>
        </Tabs.Root>
      ) : (
        <div key={work.id} className="collection-scroll" ref={setScrollRoot}>
          <ArtifactCollection
            query={artifacts}
            resetKey={work.id}
            scrollRoot={scrollRoot}
            focused={current.asset}
            onFocus={focusAsset}
            expanded={current.on}
            onExpandedChange={(on) => setZoom({ ...current, on })}
          />
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
