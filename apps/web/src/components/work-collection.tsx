/** 展示公共或个人作品，详情只加载该作品选中的成品。 */
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router';
import type { Artifact, Work } from '@comfyshop/api-client';
import { Button, Tabs } from '@comfyshop/ui';
import { useWorks, useWorkspace } from '../app/use-workspace';
import type { ReplayAction } from '../domain/types';
import type { RequireAuth } from '../features/auth/login-dialog';
import { authorPath, workLink } from '../app/workflow-route';
import { ArtifactCollection, useArtifactPages } from './artifact-collection';
import { BrowseDialog } from './browse-dialog-content';
import { CopyLink } from './copy-link';
import { DeleteButton } from './delete-button';
import { MediaCollection } from './media-grid';
import { RecordedInputs } from './recorded-inputs';
import type { CardView } from './media-grid';
import { useAction } from './use-action';
import { useCollectionNavigation, useCollectionSelection } from './use-collection-navigation';
import type { CollectionPages } from './use-collection-navigation';

const workCard = (work: Work): CardView => ({
  label: `查看作品 ${work.title}`,
  title: work.title,
  media: work.media,
  detail: (
    <>
      {work.author}
      <span>
        {work.assetCount} 份成品{!work.published && ' · 已取消公开'}
      </span>
    </>
  ),
});

export function WorkCollection({
  workflowId,
  scope = 'public',
  author,
  scrollRoot,
  emptyAction,
  onReplay,
  replayAfterSignIn,
  requireAuth,
}: {
  workflowId?: string;
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
  const { api } = useWorkspace();
  const query = useWorks(workflowId, scope, author);
  const { selected, select, fallbackRef, open, close, restoreFocus } =
    useCollectionSelection<Work>();
  // 作品链接是工作流地址加 `work` 参数。带着它打开工作流时直接展示这件作品。
  const [params, setParams] = useSearchParams();
  const linkedId = workflowId ? params.get('work') : null;
  const linked = useQuery({
    queryKey: ['works', 'linked', linkedId],
    enabled: !!linkedId,
    queryFn: ({ signal }) => api.work(linkedId!, signal),
    retry: false,
  });
  const linkedWork = linked.data?.workflowId === workflowId ? linked.data : undefined;
  useEffect(() => {
    if (linkedWork) select(linkedWork);
  }, [linkedWork, select]);
  function closeWork() {
    close();
    if (linkedId)
      setParams(
        (current) => {
          current.delete('work');
          return current;
        },
        { replace: true, state: null, preventScrollReset: true },
      );
  }
  return (
    <>
      <div ref={fallbackRef} tabIndex={-1}>
        <MediaCollection
          query={query}
          label="作品"
          resetKey={`${workflowId ?? 'all'}:${scope}:${author ?? ''}`}
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
  const { busy, error, run } = useAction('操作失败', work.id);
  const navigation = useCollectionNavigation(pages, work.id, select, busy);
  const mine = work.owner === state.userId;
  // 作者可以把自己的公开作品指定为工作流封面。来源工作流不可读时不提供这个操作。
  const workflow = useQuery({
    queryKey: ['workflows', 'detail', state.userId, work.workflowId],
    queryFn: ({ signal }) => api.workflow(work.workflowId, signal),
    enabled: mine && work.published,
    retry: false,
  });
  const pinned = workflow.data?.coverWorkId === work.id;
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
    busy,
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
          {mine && work.published && workflow.data?.owner === state.userId && (
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
      <div className="preview-caption">
        <span>
          {work.workflowName} ·{' '}
          <Link className="author-link" to={authorPath(work.author)}>
            {work.author}
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
