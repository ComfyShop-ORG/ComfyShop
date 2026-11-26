/** 本人结果列表。打开卡片后由执行详情弹框处理成品、发布和重跑。 */
import { locale } from '../app/language.ts';
import { t } from '../app/i18n.ts';
import { mediaUrl } from '../data/media-url';
import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { DownloadIcon } from '@radix-ui/react-icons';
import type { Execution } from '@comfyshop/api-client';
import { Button } from '@comfyshop/ui';
import { useExecutions, useWorkspace } from '../app/use-workspace';
import type { ExecutionFilters } from '../app/use-workspace';
import { projectsPath, workspaceKey, workspacePath } from '../app/workspace-scope';
import { useResultRoute } from '../app/result-route';
import type { ReplayAction } from '../domain/types';
import { ExecutionDialog, countLabel } from './execution-dialog';
import { ContinueInpaint } from '../features/workflows/continue-inpaint';
import { durationLabel } from './generation-stage';
import { MediaCollection } from './media-grid';
import { MediaPreview } from './media-preview';
import type { CardView } from './media-grid';
import { collectionFeed, useCollectionFocus } from './use-collection-navigation';

/** 结果卡片。`scoped` 表示列表只属于一个工作流，卡片改以生成时间区分彼此。 */
const executionCard =
  (scoped: boolean) =>
  (execution: Execution): CardView => {
    const created = new Date(execution.created);
    const timestamp = created.toLocaleString(locale, {
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
    const filename = !execution.coverImage ? execution.media?.filename : null;
    const duration = execution.media?.durationMs;
    return {
      label: t(
        'executionCollection.viewRunOfOn',
        execution.workflowName,
        created.toLocaleString(locale),
        execution.index + 1,
      ),
      title: filename || (scoped ? timestamp : execution.workflowName),
      media: execution.media,
      coverImage: execution.coverImage,
      audioCoverFallback: execution.media?.kind === 'audio',
      detail: (
        <>
          {countLabel(execution)}
          {!!duration && <span>{durationLabel(duration)}</span>}
          {filename ? (
            <span title={execution.workflowName}>{timestamp}</span>
          ) : (
            !scoped && <span>{created.toLocaleDateString(locale)}</span>
          )}
        </>
      ),
    };
  };

export function ExecutionCollection({
  workflowId,
  versionId,
  taskId,
  scrollRoot,
  referenceWidth,
  quietEmpty,
  featured,
  onReplay,
  filters,
  projectId,
}: {
  workflowId?: string;
  versionId?: string;
  taskId?: string;
  scrollRoot?: HTMLElement | null;
  referenceWidth?: string;
  /** 调用方已经在别处说明了当前状态时，空列表不再显示「暂无结果」。 */
  quietEmpty?: boolean;
  /** 列表只有一次执行时放大展示它，用于刚完成的提交。 */
  featured?: boolean;
  onReplay?: ReplayAction;
  filters?: ExecutionFilters;
  projectId?: string;
}) {
  const query = useExecutions(workflowId, taskId, versionId, filters, projectId);
  const { api, state, workspaceScope, canEditWorkspace } = useWorkspace();
  const { resultId, openResult, closeResult } = useResultRoute();
  const { fallbackRef, rememberFocus, restoreFocus } = useCollectionFocus();
  const { items } = collectionFeed(query);
  const listed = items.find((item) => item.id === resultId);
  const lookup = useQuery({
    queryKey: ['execution-detail', state.userId, resultId, ...workspaceKey(workspaceScope)],
    enabled: !!state.userId && !!resultId && !listed && !query.isPending,
    queryFn: ({ signal }) => api.execution(resultId!, signal),
    retry: false,
  });
  const result = listed ?? lookup.data;
  const selected =
    result?.id === resultId &&
    (!workflowId || result.workflowId === workflowId) &&
    (!versionId || result.versionId === versionId) &&
    (!taskId || result.taskId === taskId) &&
    (!projectId || result.projectId === projectId) &&
    result.artifactCount > 0
      ? result
      : undefined;
  function open(execution: Execution, source: HTMLElement) {
    rememberFocus(source);
    openResult(execution.id);
  }
  const hero = featured && items.length === 1 && !query.hasNextPage ? items[0] : null;
  return (
    <>
      {hero?.media && (
        <div className="generation-hero">
          {hero.media.kind !== 'image' ? (
            <MediaPreview media={hero.media} name={hero.workflowName} autoPlay />
          ) : (
            <span
              className="artifact-zoom"
              tabIndex={-1}
              onClick={(event) => open(hero, event.currentTarget)}
            >
              <MediaPreview media={hero.media} name={hero.workflowName} />
            </span>
          )}
          <div className="collection-actions">
            <Button
              size="small"
              variant="primary"
              onClick={(event) => open(hero, event.currentTarget)}
            >
              {t('executionCollection.viewAndPublish')}
            </Button>
            {canEditWorkspace &&
              hero.artifactCount === 1 &&
              hero.media.kind === 'image' &&
              hero.coverArtifactId && (
                <ContinueInpaint
                  key={hero.coverArtifactId}
                  artifact={{ id: hero.coverArtifactId, media: hero.media }}
                  sourceWorkflowId={hero.workflowId}
                  projectId={projectId}
                />
              )}
            {hero.artifactCount === 1 ? (
              <Button size="small" asChild>
                <a href={mediaUrl(hero.media.video || hero.media.src, 'download', 'true')} download>
                  <DownloadIcon />
                  {t('artifactCollection.downloadOriginal')}
                </a>
              </Button>
            ) : (
              <span className="muted">{countLabel(hero)}</span>
            )}
          </div>
        </div>
      )}
      <div ref={fallbackRef} tabIndex={-1} hidden={!!hero?.media}>
        <MediaCollection
          query={query}
          label={t('executionCollection.myResults')}
          resetKey={JSON.stringify([
            workspaceScope,
            workflowId,
            versionId,
            taskId,
            filters,
            projectId,
          ])}
          scrollRoot={scrollRoot}
          fillSparse={!!scrollRoot}
          referenceWidth={referenceWidth}
          view={executionCard(!!workflowId)}
          onOpen={open}
          emptyLabel={
            quietEmpty
              ? undefined
              : t(filters ? 'workspaceResults.noMatches' : 'executionCollection.noResultsYet')
          }
          emptyAction={
            !filters &&
            !workflowId &&
            !taskId && (
              <Button size="small" asChild>
                <Link
                  to={
                    projectId
                      ? projectsPath(workspaceScope, projectId) + '?tab=tasks'
                      : workspacePath(workspaceScope, 'tasks')
                  }
                >
                  {t('executionCollection.viewTask')}
                </Link>
              </Button>
            )
          }
        />
      </div>
      {resultId && !selected && !lookup.isPending && (
        <div className="inline-status" role="alert">
          {lookup.error?.message || t('executionCollection.thisResultIsUnavailable')}
          <Button size="small" onClick={closeResult}>
            {t('executionCollection.backToResults')}
          </Button>
        </div>
      )}
      {selected && (
        <ExecutionDialog
          initialExecution={selected}
          pages={query}
          select={(execution) => openResult(execution.id)}
          onClose={closeResult}
          restoreFocus={restoreFocus}
          onReplay={onReplay}
          showSourceTask={!taskId}
          projectId={projectId}
        />
      )}
    </>
  );
}
