import { useContext, useDeferredValue, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router';
import { ArchiveIcon, ArrowTopRightIcon, PlusIcon } from '@radix-ui/react-icons';
import { Button, SearchField, Select, Tabs, TabsList, VisuallyHidden } from '@comfyshop/ui';
import type { Project, ProjectListItem } from '@comfyshop/api-client';
import { MediaMasonry } from '@comfyshop/media';
import type { MediaRendererProps } from '@comfyshop/media';
import { t } from '../../app/i18n';
import { locale } from '../../app/language';
import { useWorkspace } from '../../app/use-workspace';
import { projectsPath, ScopedWorkspace, workspaceTargetFromPath } from '../../app/workspace-scope';
import { CollectionStatus } from '../../components/collection-status';
import { MediaCardContent } from '../../components/media-cards';
import { PageToolbar, TabbedToolbar } from '../../components/page-toolbar';
import { TaskList } from '../../components/task-list';
import { collectionFeed } from '../../components/use-collection-navigation';
import { WorkCollection } from '../../components/work-collection';
import type { ReplayAction } from '../../domain/types';
import { ActiveMark } from '../../motion';
import { WorkspaceBoundary, WorkspaceAccessStatus } from '../workspace/workspace-boundary';
import { WorkspaceResults } from '../workspace/workspace-results';
import { ProjectFormDialog } from './project-form-dialog';
import { ProjectManageMenu } from './project-manage-menu';
import { ProjectMaterials } from './project-materials';
import { ProjectMenu } from './project-menu';
import { projectKey, useProject, useProjectPages } from './project-queries';
import { WorkflowPicker } from '../catalog/workflow-picker';
import type { OpenWorkflow } from '../catalog/workflow-picker';

const tabs = [
  { id: 'results', label: t('taskDetails.results') },
  { id: 'works', label: t('workCollection.works') },
  { id: 'tasks', label: t('workspacePage.tasks') },
  { id: 'workflows', label: t('app.workflows') },
  { id: 'assets', label: t('projects.referenceAssets') },
] as const;

type ProjectActions = { openWorkflow: OpenWorkflow; onReplay: ReplayAction };

export default function ProjectsPage(props: ProjectActions) {
  const { pathname } = useLocation();
  const { projectId } = useParams();
  const target = workspaceTargetFromPath(pathname);
  const page = projectId ? (
    <ProjectPage key={projectId} id={projectId} {...props} />
  ) : (
    <ProjectList />
  );
  return target?.kind === 'shared' ? (
    <WorkspaceBoundary target={target}>{page}</WorkspaceBoundary>
  ) : (
    page
  );
}

function ProjectList() {
  const { workspaceScope, state, canEditWorkspace } = useWorkspace();
  const scoped = useContext(ScopedWorkspace);
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const archived = params.get('archived') === '1';
  const create = useRef<HTMLButtonElement>(null);
  const [creating, setCreating] = useState(false);
  const [text, setText] = useState('');
  const search = useDeferredValue(text.trim());
  const query = useProjectPages({ search, archived });
  const feed = collectionFeed(query);
  const empty = archived ? 'projects.emptyArchived' : 'projects.empty';
  return (
    <main className="page">
      {scoped?.target.kind === 'shared' ? (
        <h1 className="workspace-shared-title">{t('workspaceSharing.ownerTitle', scoped.label)}</h1>
      ) : (
        <VisuallyHidden.Root asChild>
          <h1>{t('projects.title')}</h1>
        </VisuallyHidden.Root>
      )}
      <PageToolbar className="project-index-toolbar">
        <SearchField
          aria-label={t('projects.search')}
          placeholder={t('projects.search')}
          clearLabel={t('app.clearSearch')}
          maxLength={80}
          value={text}
          onValueChange={setText}
        />
        <Select
          label={t('projects.status')}
          value={archived ? 'archived' : 'active'}
          options={[
            { value: 'active', label: t('projects.active') },
            { value: 'archived', label: t('projects.archived') },
          ]}
          onValueChange={(value) => setParams(value === 'archived' ? { archived: '1' } : {})}
        />
        {canEditWorkspace && (
          <Button ref={create} variant="primary" onClick={() => setCreating(true)}>
            <PlusIcon aria-hidden="true" />
            {t('projects.create')}
          </Button>
        )}
      </PageToolbar>
      <MediaMasonry
        {...feed}
        label={t('projects.title')}
        loadingLabel={t('common.loading')}
        render={ProjectCard}
        resetKey={JSON.stringify([...projectKey(state.userId, workspaceScope), search, archived])}
      />
      <CollectionStatus
        pending={query.isPending}
        error={query.error}
        empty={!feed.items.length}
        label={t(search ? 'projects.noMatches' : empty)}
        retry={query.refetch}
      />
      {creating && (
        <ProjectFormDialog
          onClose={() => setCreating(false)}
          onSaved={(project) => {
            setCreating(false);
            void navigate(projectsPath(workspaceScope, project.id));
          }}
          restoreFocus={() => create.current?.focus({ preventScroll: true })}
        />
      )}
    </main>
  );
}

function ProjectCard({ data, index, width }: MediaRendererProps<ProjectListItem>) {
  const target = useContext(ScopedWorkspace)?.target;
  const created = new Date(data.created);
  return (
    <article className="media-card project-card">
      <Link className="media-card-open" to={projectsPath(target, data.id)} aria-label={data.name}>
        <MediaCardContent
          media={null}
          coverImage={data.cover}
          placeholder={<ArchiveIcon />}
          index={index}
          width={width}
        />
        <span className="project-card-summary">
          <span className="project-card-title">
            <strong>{data.name}</strong>
            <ArrowTopRightIcon aria-hidden="true" />
          </span>
          {data.description && <span className="project-card-description">{data.description}</span>}
          <time dateTime={created.toISOString()}>
            {created.toLocaleDateString(locale, { dateStyle: 'medium' })}
          </time>
        </span>
      </Link>
    </article>
  );
}

function ProjectPage({ id, ...actions }: ProjectActions & { id: string }) {
  const { workspaceScope } = useWorkspace();
  const query = useProject(id);
  if (query.isError || !query.data)
    return (
      <WorkspaceAccessStatus error={query.error}>
        <Button asChild size="small">
          <Link to={projectsPath(workspaceScope)}>{t('projects.title')}</Link>
        </Button>
      </WorkspaceAccessStatus>
    );
  return <ProjectDetail project={query.data} {...actions} />;
}

function ProjectDetail({ project, openWorkflow, onReplay }: ProjectActions & { project: Project }) {
  const { canEditWorkspace, canManageWorkspace } = useWorkspace();
  const archived = project.archivedAt !== null;
  const [params, setParams] = useSearchParams();
  const requested = params.get('tab');
  const tab =
    requested === 'materials'
      ? 'workflows'
      : (tabs.find(({ id }) => id === requested)?.id ?? 'results');
  return (
    <main className="page">
      <div className="project-detail-heading">
        <div className="project-detail-title">
          <ProjectMenu project={project} tab={tab} />
          <h1>{project.name}</h1>
          <ProjectManageMenu project={project} />
        </div>
        {archived && <span className="form-hint">{t('projects.archived')}</span>}
        {project.description && <p className="muted">{project.description}</p>}
      </div>
      <Tabs.Root
        value={tab}
        onValueChange={(value) =>
          setParams({ tab: value }, { replace: true, preventScrollReset: true })
        }
      >
        <TabbedToolbar
          className="project-toolbar"
          actions={
            canEditWorkspace &&
            !archived && (
              <WorkflowPicker label={t('projects.generate')} primary onSelect={openWorkflow} />
            )
          }
          navigation={
            <TabsList className="filter-group" aria-label={t('projects.content')}>
              {tabs.map((item) => (
                <Tabs.Trigger key={item.id} value={item.id} asChild>
                  <Button variant="ghost">
                    {tab === item.id && <ActiveMark group="project-tabs" />}
                    {item.label}
                  </Button>
                </Tabs.Trigger>
              ))}
            </TabsList>
          }
        >
          <Tabs.Content value="results">
            {tab === 'results' && <WorkspaceResults projectId={project.id} onReplay={onReplay} />}
          </Tabs.Content>
          <Tabs.Content value="works">
            {tab === 'works' && (
              <WorkCollection
                projectId={project.id}
                scope="mine"
                onReplay={onReplay}
                emptyAction={
                  canManageWorkspace ? (
                    <Button
                      size="small"
                      onClick={() => setParams({ tab: 'results' }, { replace: true })}
                    >
                      {t('workCollection.publishAWorkFromResults')}
                    </Button>
                  ) : null
                }
              />
            )}
          </Tabs.Content>
          <Tabs.Content value="tasks">
            {tab === 'tasks' && (
              <TaskList projectId={project.id} openWorkflow={openWorkflow} onReplay={onReplay} />
            )}
          </Tabs.Content>
          {(['workflows', 'assets'] as const).map((kind) => (
            <Tabs.Content key={kind} value={kind}>
              {tab === kind && <ProjectMaterials project={project} kind={kind} />}
            </Tabs.Content>
          ))}
        </TabbedToolbar>
      </Tabs.Root>
    </main>
  );
}
