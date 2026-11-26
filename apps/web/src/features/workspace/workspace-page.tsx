import { Suspense, useContext } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router';
import { Button, Select, Tabs, TabsList } from '@comfyshop/ui';
import { t } from '../../app/i18n';
import { useWorkflowListFilters } from '../../app/use-workflow-list-filters';
import { useWorkspace } from '../../app/use-workspace';
import { ScopedWorkspace, workspacePath, workspaceTargetFromPath } from '../../app/workspace-scope';
import { PageToolbar, TabbedToolbar } from '../../components/page-toolbar';
import { workflowCategoryMenu } from '../../domain/workflow-categories';
import { ActiveMark } from '../../motion';
import { WorkflowCollection } from '../catalog/workflow-collection';
import { WorkflowImport } from './workflow-import';
import { WorkspaceSharing } from './workspace-sharing';
import { WorkspaceBoundary } from './workspace-boundary';
import { TeamSettings } from './team-settings';

export const workspaceTabs = [
  { id: 'favorites', label: t('workspacePage.favorites') },
  { id: 'workflows', label: t('app.workflows') },
  { id: 'artworks', label: t('workCollection.works') },
  { id: 'results', label: t('taskDetails.results') },
  { id: 'assets', label: t('assetLibrary.title') },
  { id: 'tasks', label: t('workspacePage.tasks') },
] as const;

export function MyWorkflows() {
  const { category, setCategory } = useWorkflowListFilters();
  const { canEditWorkspace } = useWorkspace();
  return (
    <>
      <PageToolbar className="workflow-list-tools">
        <Select
          label={t('catalogPage.workflowCategory')}
          options={workflowCategoryMenu}
          value={category}
          onValueChange={setCategory}
        />
        {canEditWorkspace && <WorkflowImport categoryFilter={category} />}
      </PageToolbar>
      <WorkflowCollection scope="mine" category={category} onReset={() => setCategory('all')} />
    </>
  );
}

export function WorkspacePage({ onExitTeam }: { onExitTeam: () => void }) {
  const target = workspaceTargetFromPath(useLocation().pathname);
  const tabs = <WorkspaceTabs onExitTeam={onExitTeam} />;
  return target?.kind === 'shared' ? (
    <WorkspaceBoundary target={target}>{tabs}</WorkspaceBoundary>
  ) : (
    tabs
  );
}

function WorkspaceTabs({ onExitTeam }: { onExitTeam: () => void }) {
  const scoped = useContext(ScopedWorkspace);
  const shared = scoped?.target.kind === 'shared';
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const lastSegment = pathname.split('/').filter(Boolean).at(-1)?.toLowerCase();
  const tab = workspaceTabs.find(({ id }) => id === lastSegment)?.id ?? 'favorites';
  function changeTab(value: string) {
    const next = workspacePath(scoped?.target, value);
    if (pathname !== next) void navigate(next);
  }
  return (
    <main className="page">
      {shared && (
        <h1 className="workspace-shared-title">{t('workspaceSharing.ownerTitle', scoped.label)}</h1>
      )}
      <Tabs.Root value={tab} onValueChange={changeTab}>
        <TabbedToolbar
          actions={
            !shared &&
            (scoped?.team ? (
              <TeamSettings team={scoped.team} onExitTeam={onExitTeam} />
            ) : (
              <WorkspaceSharing />
            ))
          }
          navigation={
            <TabsList className="filter-group" aria-label={t('workspacePage.myContent')}>
              {workspaceTabs.map((item) => (
                <Tabs.Trigger key={item.id} value={item.id} asChild>
                  <Button variant="ghost">
                    {item.id === tab && <ActiveMark group="workspace-tabs" />}
                    {item.label}
                  </Button>
                </Tabs.Trigger>
              ))}
            </TabsList>
          }
        >
          {workspaceTabs.map(({ id }) => (
            <Tabs.Content key={id} value={id}>
              {id === tab && (
                <Suspense fallback={null}>
                  <Outlet key={scoped?.target.id ?? 'mine'} />
                </Suspense>
              )}
            </Tabs.Content>
          ))}
        </TabbedToolbar>
      </Tabs.Root>
    </main>
  );
}
