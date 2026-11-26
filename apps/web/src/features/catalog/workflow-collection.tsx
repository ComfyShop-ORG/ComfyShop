import { t } from '../../app/i18n.ts';
import { useContext } from 'react';
import type { ReactNode } from 'react';
import { ScopedWorkspace, workspacePath } from '../../app/workspace-scope';
import { Link } from 'react-router';
import { Button } from '@comfyshop/ui';
import { MediaMasonry } from '@comfyshop/media';
import type { MediaRendererProps } from '@comfyshop/media';
import { CardActions } from '../../components/card-actions';
import { WorkflowCard } from '../../components/media-cards';
import { CollectionStatus } from '../../components/collection-status';
import { collectionFeed } from '../../components/use-collection-navigation';
import { useWorkflowPages } from '../../app/use-workspace';
import type { Workflow, WorkflowFilters } from '../../domain/types';

function PublicWorkflowCard(props: MediaRendererProps<Workflow>) {
  return <WorkflowCard {...props} showTeam />;
}

export function WorkflowCollection({
  scope = 'public',
  category = 'all',
  search = '',
  sort = 'updated',
  author,
  publicTeamId,
  projectId,
  inpaintArtifactId,
  scrollRoot,
  cardAction,
  onSelect,
  onReset,
}: Partial<WorkflowFilters> & {
  onReset?: () => void;
  scrollRoot?: HTMLElement;
  cardAction?: ((workflow: Workflow) => ReactNode) | null;
  onSelect?: (workflow: Workflow) => void;
}) {
  const actions = useContext(CardActions);
  const scoped = useContext(ScopedWorkspace);
  const filters = {
    scope,
    category,
    search,
    sort,
    author,
    publicTeamId,
    projectId,
    inpaintArtifactId,
  };
  const { pages: query, resetKey } = useWorkflowPages(filters);
  const feed = collectionFeed(query);
  const label = projectId
    ? t('app.workflows')
    : scope === 'mine'
      ? t('workflowCollection.myWorkflows')
      : scope === 'favorites'
        ? t('workflowCollection.favoriteWorkflows')
        : t('workflowCollection.publicWorkflows');
  return (
    <>
      <CardActions.Provider
        value={{
          ...actions,
          workflowAction: onSelect ? null : cardAction,
          openWorkflow:
            onSelect ?? ((workflow, source) => actions.openWorkflow(workflow, source, filters)),
        }}
      >
        <MediaMasonry
          {...feed}
          loadingLabel={t('common.loading')}
          label={label}
          render={
            !onSelect && scope === 'public' && !author && !publicTeamId
              ? PublicWorkflowCard
              : WorkflowCard
          }
          resetKey={resetKey}
          scrollRoot={scrollRoot}
        />
      </CardActions.Provider>
      <CollectionStatus
        pending={query.isPending}
        error={query.error}
        empty={!feed.items.length}
        retry={query.refetch}
        label={
          search
            ? t('workflowCollection.noMatches')
            : category !== 'all'
              ? t('workflowCollection.noCategoryMatches')
              : author
                ? t('workflowCollection.thisAuthorHasNoPublishedWorkflows')
                : scope === 'favorites'
                  ? t('workflowCollection.noFavoritesYet')
                  : t(projectId ? 'projects.noWorkflows' : 'workflowCollection.noWorkflowsYet')
        }
        action={
          scope === 'favorites' && scoped?.target.kind !== 'shared' ? (
            <Button asChild size="small">
              <Link to={scoped ? workspacePath(scoped.target, 'workflows') : '/'}>
                {t('workflowCollection.browseWorkflows')}
              </Link>
            </Button>
          ) : onReset && (search || author || category !== 'all') ? (
            <Button size="small" onClick={onReset}>
              {search
                ? t('workflowCollection.clearSearch')
                : author
                  ? t('workflowCollection.browseAllWorkflows')
                  : t('workflowCollection.viewAll')}
            </Button>
          ) : null
        }
      />
    </>
  );
}
