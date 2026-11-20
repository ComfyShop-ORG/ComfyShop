/** 工作流详情弹框，管理浏览切换、当前表单草稿和任务入口。 */
import { useEffect, useId, useRef, useState } from 'react';
import type { RefObject } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useHref } from 'react-router';
import { DownloadIcon } from '@radix-ui/react-icons';
import { Button, Dialog, DialogClose, IconButton, Tabs } from '@comfyshop/ui';
import { CancelTaskButton, TaskState } from '../../components/task-state';
import { TaskDetailsDialog } from '../../components/task-details';
import { ExecutionCollection } from '../../components/execution-collection';
import { GenerationStage, RetryButton } from '../../components/generation-stage';
import { WorkCollection } from '../../components/work-collection';
import { BrowseDialogContent } from '../../components/browse-dialog-content';
import { EmptyState } from '../../components/collection-status';
import { DeleteButton } from '../../components/delete-button';
import { CopyLink } from '../../components/copy-link';
import { useCollectionNavigation } from '../../components/use-collection-navigation';
import type { CollectionPages } from '../../components/use-collection-navigation';
import { useDialogFocus } from '../../components/use-dialog-focus';
import { useTasks, useWorkspace } from '../../app/use-workspace';
import { workflowPath } from '../../app/workflow-route';
import { downloadJson } from '../../data/download';
import type { Task, Workflow } from '../../domain/types';
import type { InputValue, Replay } from '@comfyshop/api-client';
import type { RequireAuth } from '../auth/login-dialog';
import { RunForm } from './run-form';
import type { RunIntent } from './run-form';
import { PublishWorkflowButton } from './publish-workflow-button';
import { WorkflowSettings } from './workflow-settings';

type WorkflowDraft = {
  replay: Replay | null;
  executionCount: number;
  inputValues: Record<string, InputValue> | null;
  machineId: string | null;
  intent?: RunIntent;
};

type WorkflowDetailsProps = {
  workflow: Workflow;
  initialReplay?: Replay;
  initialReplayError?: string;
  /** 访客在作品上点「载入参数」后登录时，由外层页面载入参数。 */
  replayAfterSignIn?: (source: { workId: string }) => void;
  requireAuth: RequireAuth;
  notify: (message: string) => void;
};

export default function WorkflowDialog({
  pages,
  onSelect,
  onClose,
  restoreFocus,
  ...details
}: WorkflowDetailsProps & {
  pages?: CollectionPages<Workflow>;
  onSelect: (workflow: Workflow, isCurrent: () => boolean) => Promise<void>;
  onClose: () => void;
  restoreFocus: () => void;
}) {
  const { workflow, initialReplay } = details;
  const { titleRef, focusProps } = useDialogFocus(restoreFocus);
  const [drafts, setDrafts] = useState<Record<string, WorkflowDraft>>({});
  const [operations, setOperations] = useState<ReadonlySet<string>>(() => new Set());
  const navigation = useCollectionNavigation(pages, workflow.id, onSelect, operations.size > 0);
  // 在本次弹框内切换工作流时保留草稿，版本及重跑来源各用自己的草稿。
  const draftKey = JSON.stringify([
    workflow.id,
    workflow.versionId,
    initialReplay?.sourceExecutionId,
    initialReplay?.sourceWorkId,
  ]);
  const initialDraft: WorkflowDraft = {
    replay: initialReplay ?? null,
    executionCount: 1,
    inputValues: null,
    machineId: null,
  };
  const queries = useQueryClient();
  const { items, history } = useTasks(workflow.id);
  const refreshed = useRef(new Map<string, string>());
  const latestSuccess = items.find((task) => task.status === 'succeeded')?.id;
  useEffect(() => {
    if (latestSuccess && refreshed.current.get(workflow.id) !== latestSuccess) {
      refreshed.current.set(workflow.id, latestSuccess);
      void queries.invalidateQueries({ queryKey: ['workflows'] });
      void queries.invalidateQueries({ queryKey: ['artifacts'] });
    }
  }, [latestSuccess, queries, workflow.id]);
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <BrowseDialogContent
        className="workflow-dialog"
        itemId={workflow.id}
        titleRef={titleRef}
        navigation={navigation}
        {...focusProps}
      >
        <WorkflowPanel
          key={draftKey}
          {...details}
          titleRef={titleRef}
          tasks={items}
          tasksComplete={!history.isPending && !history.hasNextPage}
          onClose={onClose}
          draft={drafts[draftKey] ?? initialDraft}
          updateDraft={(update) =>
            setDrafts((prior) => {
              const draft = prior[draftKey] ?? initialDraft;
              return { ...prior, [draftKey]: { ...draft, ...update(draft) } };
            })
          }
          operations={operations}
          onPendingChange={(operation, busy) =>
            setOperations((prior) => {
              const next = new Set(prior);
              if (busy) next.add(operation);
              else next.delete(operation);
              return next;
            })
          }
        />
      </BrowseDialogContent>
    </Dialog.Root>
  );
}

function WorkflowPanel({
  workflow,
  initialReplay,
  initialReplayError,
  replayAfterSignIn,
  requireAuth,
  notify,
  titleRef,
  tasks,
  tasksComplete,
  onClose,
  draft,
  updateDraft,
  operations,
  onPendingChange,
}: WorkflowDetailsProps & {
  titleRef: RefObject<HTMLHeadingElement | null>;
  tasks: Task[];
  /** 这个工作流的任务历史是否已全部读取。 */
  tasksComplete: boolean;
  onClose: () => void;
  draft: WorkflowDraft;
  updateDraft: (update: (draft: WorkflowDraft) => Partial<WorkflowDraft>) => void;
  operations: ReadonlySet<string>;
  onPendingChange: (operation: string, busy: boolean) => void;
}) {
  const { api, state } = useWorkspace();
  const queries = useQueryClient();
  const { replay } = draft;
  const activeWorkflow = replay?.workflow ?? workflow;
  const sharePath = useHref(workflowPath(workflow.id));
  const [tab, setTab] = useState(initialReplay ? 'results' : 'works');
  const [scrollRoot, setScrollRoot] = useState<HTMLDivElement | null>(null);
  const [resultTaskId, setResultTaskId] = useState<string | undefined>();
  const [submission, setSubmission] = useState<{ task: Task; userId: string | null }>();
  const [taskDetails, setTaskDetails] = useState<{
    task: Task;
    source: HTMLElement;
    userId: string | null;
  } | null>(null);
  const submittedTask = submission?.userId === state.userId ? submission?.task : undefined;
  const currentTask = state.user
    ? submittedTask
      ? (tasks.find((task) => task.id === submittedTask.id) ?? submittedTask)
      : tasks[0]
    : undefined;
  const formId = useId();
  // 浏览器标签显示当前工作流，关闭弹框后恢复站点名称。
  useEffect(() => {
    const site = document.title;
    document.title = `${activeWorkflow.name} · ComfyShop`;
    return () => {
      document.title = site;
    };
  }, [activeWorkflow.name]);
  // 这次提交在弹框打开期间结束时提示一次，用户可能正在看别的标签。
  const watched = useRef<{ id: string; status: Task['status'] } | undefined>(undefined);
  useEffect(() => {
    const previous = watched.current;
    watched.current = currentTask && { id: currentTask.id, status: currentTask.status };
    if (!currentTask || previous?.id !== currentTask.id) return;
    const wasActive = previous.status === 'queued' || previous.status === 'running';
    if (wasActive && currentTask.status === 'succeeded') notify('生成完成');
    if (wasActive && currentTask.status === 'failed') notify('生成失败');
  }, [currentTask, notify]);
  // 「我的结果」只看某次提交时，在结果上方呈现这次提交的进度、用时或失败原因。
  const stagedTask = resultTaskId
    ? (tasks.find((task) => task.id === resultTaskId) ??
      (submittedTask?.id === resultTaskId ? submittedTask : undefined))
    : undefined;
  const ownDraft = workflow.owner === state.userId && !workflow.published;
  // 历史没读完时无法确定有没有成功记录，交给平台在发布时判断。
  const versionSucceeded =
    tasks.some((task) => task.versionId === workflow.versionId && task.status === 'succeeded') ||
    (tasksComplete ? false : undefined);
  function loadReplay(next: Replay) {
    updateDraft(() => ({ replay: next, executionCount: 1, inputValues: null }));
    notify('已载入参数');
  }
  async function download() {
    try {
      const result = await api.graph(workflow.id, activeWorkflow.versionId);
      downloadJson(result.graph, `${activeWorkflow.name}.json`);
    } catch (error) {
      notify(error instanceof Error ? error.message : '下载失败');
    }
  }
  return (
    <>
      <header className="workflow-dialog-heading">
        <div className="breadcrumb">
          <span aria-hidden="true">工作流</span>
          <span aria-hidden="true">/</span>
          <Dialog.Title ref={titleRef} tabIndex={-1}>
            {activeWorkflow.name}
          </Dialog.Title>
        </div>
        <div className="dialog-heading-actions">
          <span className="version">v{activeWorkflow.version}</span>
          <IconButton
            label={state.user ? '下载 JSON' : '登录后下载 JSON'}
            onClick={(event) => requireAuth(event.currentTarget, download, '登录后下载工作流文件')}
          >
            <DownloadIcon />
          </IconButton>
          <CopyLink href={sharePath} title="工作流链接" />
          {workflow.owner === state.userId && (
            <WorkflowSettings workflow={workflow} disabled={operations.size > 0} notify={notify} />
          )}
          {workflow.owner === state.userId && (
            <DeleteButton
              label="删除工作流"
              done="已删除工作流"
              undo={() => ({
                label: '撤销',
                run: async () => {
                  await api.restoreWorkflow(workflow.id);
                  await Promise.all(
                    ['workflows', 'workspace', 'works'].map((key) =>
                      queries.invalidateQueries({ queryKey: [key] }),
                    ),
                  );
                },
              })}
              description={`将移除「${workflow.name}」并下架关联的公开作品。历史任务和成品可在「我的」查看。`}
              disabled={operations.size > 0}
              onDelete={() => api.deleteWorkflow(workflow.id)}
              onDeleted={() => {
                onClose();
                queries.removeQueries({
                  queryKey: ['workflows', 'detail'],
                  predicate: ({ queryKey }) => queryKey[3] === workflow.id,
                });
                void Promise.all([
                  queries.invalidateQueries({
                    queryKey: ['workflows'],
                    predicate: ({ queryKey }) => queryKey[1] !== 'detail',
                  }),
                  queries.invalidateQueries({ queryKey: ['workspace'] }),
                  queries.invalidateQueries({
                    queryKey: ['works'],
                    predicate: ({ queryKey }) =>
                      queryKey[3] === 'public' &&
                      (queryKey[2] === undefined || queryKey[2] === workflow.id),
                  }),
                ]);
              }}
            />
          )}
          <DialogClose />
        </div>
      </header>
      {initialReplayError && (
        <div className="inline-status" role="alert">
          {initialReplayError}
        </div>
      )}
      <div className="workflow-dialog-body">
        <section className="workflow-viewer">
          <Tabs.Root
            className="viewer-tabs"
            value={tab}
            onValueChange={(value) => {
              if (value === 'results') setResultTaskId(undefined);
              setTab(value);
            }}
          >
            <Tabs.List className="viewer-tab-list" aria-label="工作流内容">
              {[
                { id: 'works', label: '作品' },
                { id: 'results', label: '我的结果' },
              ].map((item) => (
                <Tabs.Trigger key={item.id} value={item.id} asChild>
                  <Button variant="ghost" size="small">
                    {item.label}
                  </Button>
                </Tabs.Trigger>
              ))}
            </Tabs.List>
            <div className="viewer-scroll" ref={setScrollRoot}>
              <Tabs.Content value="works" className="gallery-panel">
                <WorkCollection
                  workflowId={workflow.id}
                  scrollRoot={scrollRoot}
                  emptyAction={
                    state.user && (
                      <Button
                        size="small"
                        onClick={() => {
                          setResultTaskId(undefined);
                          setTab('results');
                        }}
                      >
                        从我的结果发布作品
                      </Button>
                    )
                  }
                  onReplay={loadReplay}
                  replayAfterSignIn={replayAfterSignIn}
                  requireAuth={requireAuth}
                />
              </Tabs.Content>
              <Tabs.Content value="results" className="gallery-panel">
                {state.user ? (
                  <>
                    {resultTaskId && (
                      <div className="result-scope">
                        <span className="muted">只显示本次提交</span>
                        <Button
                          variant="ghost"
                          size="small"
                          onClick={() => setResultTaskId(undefined)}
                        >
                          查看这个工作流的全部结果
                        </Button>
                      </div>
                    )}
                    {stagedTask && (
                      <GenerationStage
                        task={stagedTask}
                        media={activeWorkflow.media}
                        retry={
                          <RetryButton
                            formId={formId}
                            failed={stagedTask.status === 'failed'}
                            disabled={operations.size > 0}
                          />
                        }
                      />
                    )}
                    <div
                      className={
                        stagedTask?.status === 'succeeded' ? 'generation-results' : undefined
                      }
                    >
                      <ExecutionCollection
                        workflowId={workflow.id}
                        taskId={resultTaskId}
                        scrollRoot={scrollRoot}
                        quietEmpty={!!stagedTask && stagedTask.status !== 'succeeded'}
                        featured={stagedTask?.status === 'succeeded'}
                        onReplay={loadReplay}
                      />
                    </div>
                  </>
                ) : (
                  <EmptyState
                    label="登录后查看此工作流的生成结果。"
                    action={
                      <Button
                        size="small"
                        onClick={(event) =>
                          requireAuth(event.currentTarget, undefined, '登录后查看你的生成结果')
                        }
                      >
                        登录后查看结果
                      </Button>
                    }
                  />
                )}
              </Tabs.Content>
            </div>
          </Tabs.Root>
        </section>
        <RunForm
          key={activeWorkflow.versionId}
          formId={formId}
          workflow={activeWorkflow}
          publishAction={
            ownDraft && <PublishWorkflowButton workflow={workflow} hasSuccess={versionSucceeded} />
          }
          taskSummary={
            currentTask && (
              <div className="current-task">
                <TaskState task={currentTask} />
                {(currentTask.status === 'queued' || currentTask.status === 'running') && (
                  <CancelTaskButton task={currentTask} />
                )}
                <Button
                  variant="ghost"
                  size="small"
                  onClick={() => {
                    setResultTaskId(currentTask.id);
                    setTab('results');
                    scrollRoot?.scrollIntoView({ block: 'nearest' });
                  }}
                >
                  结果
                </Button>
                <Button
                  size="small"
                  onClick={(event) =>
                    setTaskDetails({
                      task: currentTask,
                      source: event.currentTarget,
                      userId: state.userId,
                    })
                  }
                >
                  任务详情
                </Button>
              </div>
            )
          }
          selectedMachine={draft.machineId}
          onMachineChange={(machineId) => updateDraft(() => ({ machineId }))}
          executionCount={draft.executionCount}
          onExecutionCountChange={(executionCount) => updateDraft(() => ({ executionCount }))}
          inputValues={draft.inputValues}
          onInputValuesChange={(update) =>
            updateDraft((prior) => ({ inputValues: update(prior.inputValues) }))
          }
          intent={draft.intent}
          onIntentChange={(intent) => updateDraft(() => ({ intent }))}
          operations={operations}
          onPendingChange={onPendingChange}
          replaySource={
            replay
              ? {
                  executionId: replay.sourceExecutionId ?? undefined,
                  workId: replay.sourceWorkId ?? undefined,
                }
              : undefined
          }
          onReset={() =>
            updateDraft(() => ({ replay: null, inputValues: null, executionCount: 1 }))
          }
          requireAuth={requireAuth}
          onRun={(task) => {
            setSubmission({ task, userId: state.userId });
            setResultTaskId(task.id);
            setTab('results');
            notify('已加入队列');
          }}
        />
      </div>
      {state.userId && taskDetails?.userId === state.userId && (
        <TaskDetailsDialog
          task={taskDetails.task}
          onClose={() => setTaskDetails(null)}
          onDeleted={() => {
            if (taskDetails.task.id === submission?.task.id) setSubmission(undefined);
            setTaskDetails(null);
          }}
          restoreFocus={() => {
            const target = taskDetails.source.isConnected ? taskDetails.source : titleRef.current;
            target?.focus({ preventScroll: true });
          }}
          onReplay={(next) => {
            setTaskDetails(null);
            loadReplay(next);
          }}
        />
      )}
    </>
  );
}
