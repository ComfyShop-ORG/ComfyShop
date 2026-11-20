import { UploadIcon } from '@radix-ui/react-icons';
import { Suspense, useContext, useState } from 'react';
import { Outlet, useLocation, useMatch, useNavigate } from 'react-router';
import { Button, FileInput, Select, Tabs } from '@comfyshop/ui';
import type { Workflow } from '@comfyshop/api-client';
import { isEditorGraph, readWorkflow } from '../../data/workflow-import';
import { CardActions } from '../../components/card-actions';
import { useWorkspace } from '../../app/use-workspace';
import { ActiveMark } from '../../motion';
import { workflowCategories } from '../../domain/workflow-categories';

export const workspaceTabs = [
  { id: 'favorites', label: '收藏' },
  { id: 'workflows', label: '工作流' },
  { id: 'artworks', label: '作品' },
  { id: 'results', label: '结果' },
  { id: 'tasks', label: '任务' },
] as const;

export function WorkspacePage({ notify }: { notify: (message: string) => void }) {
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState('');
  const [importCategory, setImportCategory] = useState<Workflow['category'] | 'auto'>('auto');
  // 当前标签页自己的筛选放在标签栏右侧，与标签同行。
  const [toolbarSlot, setToolbarSlot] = useState<HTMLDivElement | null>(null);
  const { state, workspace } = useWorkspace();
  const actions = useContext(CardActions);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const tab = useMatch('/workspace/:tab')?.params.tab?.toLowerCase() ?? 'favorites';
  function changeTab(value: string) {
    if (pathname !== `/workspace/${value}`) void navigate(value);
  }
  return (
    <main className="page">
      <Tabs.Root value={tab} onValueChange={changeTab}>
        <div className="page-toolbar">
          <Tabs.List className="filter-group" aria-label="我的内容">
            {workspaceTabs.map((item) => (
              <Tabs.Trigger key={item.id} value={item.id} asChild>
                <Button variant="ghost" size="small">
                  {item.id === tab && <ActiveMark group="workspace-tabs" />}
                  {item.label}
                </Button>
              </Tabs.Trigger>
            ))}
          </Tabs.List>
          {tab === 'workflows' && (
            <div className="import-group">
              {importError && (
                <p className="form-error" role="alert">
                  {importError}
                </p>
              )}
              <Select
                className="sort-select"
                label="导入分类"
                value={importCategory}
                disabled={importing}
                onValueChange={(value) => setImportCategory(value as typeof importCategory)}
                options={[{ value: 'auto', label: '自动分类' }, ...workflowCategories]}
              />
              <FileInput
                accept=".json,application/json"
                aria-label="导入工作流"
                className="import-control"
                disabled={importing}
                onChange={(event) => {
                  const input = event.currentTarget;
                  void (async () => {
                    const file = input.files?.[0];
                    input.value = '';
                    if (!file || !state.user || importing) return;
                    setImporting(true);
                    setImportError('');
                    try {
                      const body = await readWorkflow(file);
                      const workflow = await workspace.importWorkflow({
                        ...body,
                        category: importCategory === 'auto' ? body.category : importCategory,
                      });
                      notify(
                        isEditorGraph(body.graph)
                          ? '已导入。这是编辑器格式，运行需要 API 格式'
                          : '已导入',
                      );
                      // 导入后直接打开，作者可以接着核对参数并运行。
                      actions.openWorkflow(workflow, input, {
                        scope: 'mine',
                        category: 'all',
                        search: '',
                        sort: 'updated',
                      });
                    } catch (error) {
                      setImportError(error instanceof Error ? error.message : '导入失败');
                    } finally {
                      setImporting(false);
                    }
                  })();
                }}
              >
                <UploadIcon />
                {importing ? '导入中' : '导入工作流'}
              </FileInput>
            </div>
          )}
          {tab === 'tasks' && <div className="toolbar-slot" ref={setToolbarSlot} />}
        </div>
        {workspaceTabs.map(({ id }) => (
          <Tabs.Content key={id} value={id}>
            {id === tab && (
              <Suspense fallback={null}>
                <Outlet context={toolbarSlot} />
              </Suspense>
            )}
          </Tabs.Content>
        ))}
      </Tabs.Root>
    </main>
  );
}
