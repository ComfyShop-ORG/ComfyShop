/** 页面路由与登录边界。工作流详情可从列表以弹框打开，也可直接通过链接进入。 */
import { t } from './i18n.ts';
import { lazy, Suspense, useEffect, useState } from 'react';
import type { ComponentProps, ReactNode } from 'react';
import { Link, Navigate, Route, Routes, useLocation, useParams } from 'react-router';
import { Button } from '@comfyshop/ui';
import type { ReplayAction } from '../domain/types';
import type { Workflow } from '../domain/types';
import { RequireSession } from '../features/auth/require-session';
import type { RequireAuth } from '../features/auth/login-dialog';
import { AuthorPage, PublicTeamPage } from '../features/authors/author-page';
import { CatalogPage } from '../features/catalog/catalog-page';
import { WorkflowCollection } from '../features/catalog/workflow-collection';
import { SkillInstallPage } from '../features/skill/skill-install-page';
import { MyWorkflows, WorkspacePage, workspaceTabs } from '../features/workspace/workspace-page';
import { WorkspaceBoundary } from '../features/workspace/workspace-boundary';
import { workflowRouteState } from './workflow-route';
import {
  projectsRoute,
  sharedProjectsRoute,
  workspacePath,
  workspaceRoutes,
} from './workspace-scope';

// 预取完成后直接使用已加载的组件。`lazy` 第一次渲染总会先显示占位，
// React 随后至少等待约 300 毫秒才换成内容，点开卡片时会明显停顿。
let loadedWorkflowPage: Awaited<ReturnType<typeof importWorkflowPage>>['default'] | undefined;
const importWorkflowPage = () => import('../features/workflows/shared-workflow-page');
const loadWorkflowPage = async () => {
  const page = await importWorkflowPage();
  loadedWorkflowPage = page.default;
  return page;
};
const LazyWorkflowPage = lazy(loadWorkflowPage);

function WorkflowPage(props: ComponentProps<typeof LazyWorkflowPage>) {
  // 页面打开后保持同一组件，避免预取完成后的上层更新重建工作流草稿。
  const [Page] = useState(() => loadedWorkflowPage ?? LazyWorkflowPage);
  return <Page {...props} />;
}

const MachinesPage = lazy(() => import('../features/machines/machines-page'));
const MachineLinkDialog = lazy(() => import('../features/machines/machine-link-dialog'));
const AssetLibraryPage = lazy(() => import('../features/assets/asset-library-page'));
const ProjectsPage = lazy(() => import('../features/projects/projects-page'));
const WorkCollection = lazy(() =>
  import('../components/work-collection').then(({ WorkCollection }) => ({
    default: WorkCollection,
  })),
);
const TaskList = lazy(() =>
  import('../components/task-list').then(({ TaskList }) => ({ default: TaskList })),
);
const WorkspaceResults = lazy(() =>
  import('../features/workspace/workspace-results').then(({ WorkspaceResults }) => ({
    default: WorkspaceResults,
  })),
);

function PageNotFound() {
  return (
    <main className="page">
      <div className="inline-status">
        {t('appRoutes.pageNotFound')}
        <Button asChild size="small">
          <Link to="/">{t('appRoutes.backToWorkflows')}</Link>
        </Button>
      </div>
    </main>
  );
}

function LegacyTeamWorkspaceRedirect() {
  const tab = useParams().tab?.toLowerCase();
  const { search, hash } = useLocation();
  if (tab && !workspaceTabs.some(({ id }) => id === tab)) return <PageNotFound />;
  return <Navigate replace to={{ pathname: workspacePath(undefined, tab), search, hash }} />;
}

export function AppRoutes({
  search,
  clearSearch,
  openWorkflow,
  onReplay,
  restoreHomeFocus,
  restoreSessionFocus,
  restoreWorkflowFocus,
  requireAuth,
  notify,
  openSpaceSwitcher,
  onExitTeam,
}: {
  search: string;
  clearSearch: () => void;
  openWorkflow: (workflow: Workflow, source: HTMLElement) => void;
  onReplay: ReplayAction;
  restoreHomeFocus: () => void;
  restoreSessionFocus: () => void;
  restoreWorkflowFocus: (backgroundKey: string) => void;
  requireAuth: RequireAuth;
  notify: (message: string) => void;
  openSpaceSwitcher: (source: HTMLElement) => void;
  onExitTeam: () => void;
}) {
  const location = useLocation();
  const overlay = workflowRouteState(location);
  // 首屏之后预先取回工作流详情的代码，第一次点开卡片时不必等待下载。
  useEffect(() => {
    const timer = window.setTimeout(() => void loadWorkflowPage(), 1200);
    return () => window.clearTimeout(timer);
  }, []);
  const catalog = <CatalogPage search={search} clearSearch={clearSearch} />;
  const details = (
    <Suspense
      fallback={
        <div className="inline-status" role="status">
          {t('appRoutes.loadingWorkflow')}
        </div>
      }
    >
      <WorkflowPage
        overlay={overlay ?? undefined}
        restoreFocus={
          overlay ? () => restoreWorkflowFocus(overlay.background.key) : restoreHomeFocus
        }
        requireAuth={requireAuth}
        notify={notify}
      />
    </Suspense>
  );
  const workspacePages: Record<(typeof workspaceTabs)[number]['id'], ReactNode> = {
    favorites: <WorkflowCollection scope="favorites" />,
    workflows: <MyWorkflows />,
    artworks: <WorkCollection scope="mine" onReplay={onReplay} />,
    results: <WorkspaceResults onReplay={onReplay} />,
    assets: <AssetLibraryPage />,
    tasks: <TaskList openWorkflow={openWorkflow} onReplay={onReplay} />,
  };
  const workspaceChildren = (
    <>
      <Route index element={<Navigate replace to="favorites" />} />
      {workspaceTabs.map(({ id }) => (
        <Route key={id} path={id} element={workspacePages[id]} />
      ))}
    </>
  );
  const workspace = <WorkspacePage onExitTeam={onExitTeam} />;
  const projects = (
    <Suspense
      fallback={
        <div className="inline-status" role="status">
          {t('common.loading')}
        </div>
      }
    >
      <ProjectsPage openWorkflow={openWorkflow} onReplay={onReplay} />
    </Suspense>
  );
  return (
    <>
      <Routes location={overlay?.background ?? location}>
        <Route index element={catalog} />
        <Route path="skill" element={<SkillInstallPage />} />
        {/* 重置链接显示工作流库，设置新密码的弹框由 App 打开。 */}
        <Route path="reset-password" element={catalog} />
        {/* 确认邮件里的链接同样显示工作流库，确认弹框由 App 打开。 */}
        <Route path="confirm-email" element={catalog} />
        <Route
          path="authors/:name"
          element={<AuthorPage onReplay={onReplay} requireAuth={requireAuth} />}
        />
        <Route
          path="teams/:teamId"
          element={<PublicTeamPage onReplay={onReplay} requireAuth={requireAuth} />}
        />
        <Route
          path="workflows/:workflowId"
          element={
            <>
              {catalog}
              {details}
            </>
          }
        />
        <Route element={<RequireSession restoreFocus={restoreSessionFocus} />}>
          <Route path={`${projectsRoute}/:projectId?`} element={projects} />
          <Route path={`${sharedProjectsRoute}/:projectId?`} element={projects} />
          <Route path={workspaceRoutes.personal} element={workspace}>
            {workspaceChildren}
          </Route>
          <Route path={workspaceRoutes.shared} element={workspace}>
            {workspaceChildren}
          </Route>
          <Route path={`${workspaceRoutes.team}/:tab?`} element={<LegacyTeamWorkspaceRedirect />} />
          <Route
            path="machines"
            element={
              <Suspense fallback={null}>
                <MachinesPage onReplay={onReplay} />
              </Suspense>
            }
          />
          <Route
            path="machines/link"
            element={
              <Suspense fallback={null}>
                <MachinesPage onReplay={onReplay} />
                <MachineLinkDialog openSpaceSwitcher={openSpaceSwitcher} />
              </Suspense>
            }
          />
        </Route>
        <Route path="*" element={<PageNotFound />} />
      </Routes>
      {overlay && (
        <Routes>
          <Route
            path="workflows/:workflowId"
            element={
              overlay.workspace ? (
                <WorkspaceBoundary target={overlay.workspace} overlay>
                  {details}
                </WorkspaceBoundary>
              ) : (
                details
              )
            }
          />
        </Routes>
      )}
    </>
  );
}
