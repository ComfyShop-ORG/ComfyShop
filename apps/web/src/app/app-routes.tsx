/** 页面路由与登录边界。工作流详情可从列表以弹框打开，也可直接通过链接进入。 */
import { lazy, Suspense, useEffect, useState } from 'react';
import type { ComponentProps, ReactNode } from 'react';
import { Link, Navigate, Route, Routes, useLocation } from 'react-router';
import { Button } from '@comfyshop/ui';
import type { ReplayAction } from '../domain/types';
import type { Workflow } from '../domain/types';
import { RequireSession } from '../features/auth/require-session';
import type { RequireAuth } from '../features/auth/login-dialog';
import { AuthorPage } from '../features/authors/author-page';
import { CatalogPage } from '../features/catalog/catalog-page';
import { WorkflowCollection } from '../features/catalog/workflow-collection';
import { SkillInstallPage } from '../features/skill/skill-install-page';
import { WorkspacePage, workspaceTabs } from '../features/workspace/workspace-page';
import { workflowRouteState } from './workflow-route';

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
const WorkCollection = lazy(() =>
  import('../components/work-collection').then(({ WorkCollection }) => ({
    default: WorkCollection,
  })),
);
const TaskList = lazy(() =>
  import('../components/task-list').then(({ TaskList }) => ({ default: TaskList })),
);
const ExecutionCollection = lazy(() =>
  import('../components/execution-collection').then(({ ExecutionCollection }) => ({
    default: ExecutionCollection,
  })),
);

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
          正在读取工作流
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
    workflows: <WorkflowCollection scope="mine" />,
    artworks: <WorkCollection scope="mine" onReplay={onReplay} />,
    results: <ExecutionCollection onReplay={onReplay} />,
    tasks: <TaskList openWorkflow={openWorkflow} onReplay={onReplay} />,
  };
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
          path="workflows/:workflowId"
          element={
            <>
              {catalog}
              {details}
            </>
          }
        />
        <Route element={<RequireSession restoreFocus={restoreSessionFocus} />}>
          <Route path="workspace" element={<WorkspacePage notify={notify} />}>
            <Route index element={<Navigate replace to="favorites" />} />
            {workspaceTabs.map(({ id }) => (
              <Route key={id} path={id} element={workspacePages[id]} />
            ))}
          </Route>
          <Route
            path="machines"
            element={
              <Suspense fallback={null}>
                <MachinesPage />
              </Suspense>
            }
          />
          <Route
            path="machines/link"
            element={
              <Suspense fallback={null}>
                <MachinesPage />
                <MachineLinkDialog />
              </Suspense>
            }
          />
        </Route>
        <Route
          path="*"
          element={
            <main className="page">
              <div className="inline-status">
                页面不存在
                <Button asChild size="small">
                  <Link to="/">返回工作流</Link>
                </Button>
              </div>
            </main>
          }
        />
      </Routes>
      {overlay && (
        <Routes>
          <Route path="workflows/:workflowId" element={details} />
        </Routes>
      )}
    </>
  );
}
