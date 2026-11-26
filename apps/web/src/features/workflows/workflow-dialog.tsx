/** 工作流详情弹框，管理浏览切换、当前表单草稿和任务入口。 */
import { t } from '../../app/i18n.ts';
import { refreshPublishedContent } from '../../app/publication-queries';
import { useEffect, useId, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useHref } from 'react-router';
import {
  DotsHorizontalIcon,
  DownloadIcon,
  EnterFullScreenIcon,
  ExitFullScreenIcon,
} from '@radix-ui/react-icons';
import {
  Button,
  Dialog,
  DialogClose,
  DropdownMenu,
  IconButton,
  Select,
  Tabs,
  TabsList,
} from '@comfyshop/ui';
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
import type {
  CollectionNavigation,
  CollectionPages,
} from '../../components/use-collection-navigation';
import { useDialogFocus } from '../../components/use-dialog-focus';
import { useExecutions, useTaskProgress, useTasks, useWorkspace } from '../../app/use-workspace';
import { workflowPath } from '../../app/workflow-route';
import type { InpaintDraft } from '../../app/workflow-route';
import type { ItemDirection } from '../../data/collection-position';
import { downloadJson } from '../../data/download';
import type { Task, Workflow } from '../../domain/types';
import { isTaskActive } from '../../domain/types';
import type { AuthSession, InputValue, Replay, Work, WorkflowVersion } from '@comfyshop/api-client';
import type { RequireAuth } from '../auth/login-dialog';
import { CopyToTeam } from '../workspace/team-switcher';
import { RunForm } from './run-form';
import { WorkflowMetadata } from './workflow-metadata';
import type { RunIntent } from './run-form';
import { PublishWorkflowButton } from './publish-workflow-button';
import { WorkflowSettings } from './workflow-settings';

type WorkflowDraft = {
  executionCount: number;
  inputValues: Record<string, InputValue> | null;
  hiddenInputValues: Record<string, InputValue>;
  machineId: string | null;
  intent?: RunIntent;
};

const emptyDraft: WorkflowDraft = {
  executionCount: 1,
  inputValues: null,
  hiddenInputValues: {},
  machineId: null,
};

export type WorkflowTab = 'works' | 'results';

function PublishFromResults({
  workflow,
  label,
  onOpen,
}: {
  workflow: Workflow;
  label: string;
  onOpen: () => void;
}) {
  const results = useExecutions(workflow.id, undefined, workflow.versionId);
  if (!results.data?.pages.some((page) => page.items.some(({ artifactCount }) => artifactCount)))
    return null;
  return (
    <Button size="small" onClick={onOpen}>
      {label}
    </Button>
  );
}

type WorkflowDetailsProps = {
  workflow: Workflow;
  fullscreen: boolean;
  onToggleFullscreen: () => void;
  currentVersionId?: string;
  versions: WorkflowVersion[];
  pendingVersionId?: string;
  onVersionChange: (versionId: string, tab: WorkflowTab) => void;
  initialTab?: WorkflowTab;
  linkedWork?: Work;
  onLinkedWorkClose: () => void;
  initialReplay?: Replay;
  initialInpaint?: InpaintDraft;
  projectId?: string;
  initialReplayError?: string;
  onReplayChange: (replay: Replay | null) => void;
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
  const { workflow, initialReplay, initialInpaint } = details;
  const { state } = useWorkspace();
  const queries = useQueryClient();
  const [operations, setOperations] = useState<ReadonlySet<string>>(() => new Set());
  const navigation = useCollectionNavigation(
    pages,
    workflow.id,
    onSelect,
    operations.size > 0 || !!details.pendingVersionId,
  );
  const versionId = initialReplay?.workflow.versionId ?? workflow.versionId;
  const versionKey = ['workflow-draft', state.userId, workflow.id, versionId] as const;
  const draftKey = [
    ...versionKey,
    initialReplay?.sourceExecutionId,
    initialReplay?.sourceWorkId,
    ...(initialInpaint ? [initialInpaint.key] : []),
  ] as const;
  const startingDraft: WorkflowDraft = initialInpaint
    ? {
        ...emptyDraft,
        machineId: initialInpaint.machineId,
        inputValues: initialInpaint.inputValues,
      }
    : emptyDraft;
  // 查询缓存只保存当前账号的会话草稿，关闭弹框后仍可恢复。
  const draft =
    useQuery({
      queryKey: draftKey,
      queryFn: () => startingDraft,
      enabled: false,
      staleTime: Infinity,
      gcTime: Infinity,
    }).data ?? startingDraft;
  function updateDraft(update: (draft: WorkflowDraft) => Partial<WorkflowDraft>) {
    if (!state.userId || queries.getQueryData<AuthSession>(['session'])?.user?.id !== state.userId)
      return;
    queries.setQueryData<WorkflowDraft>(draftKey, (prior = startingDraft) => ({
      ...prior,
      ...update(prior),
    }));
  }
  const { items, history } = useTasks(workflow.id, undefined, versionId);
  const refreshed = useRef(new Map<string, string>());
  const latestSuccess = items.find((task) => task.status === 'succeeded')?.id;
  useEffect(() => {
    if (latestSuccess && refreshed.current.get(versionId) !== latestSuccess) {
      refreshed.current.set(versionId, latestSuccess);
      void queries.invalidateQueries({ queryKey: ['workflows'] });
      void queries.invalidateQueries({ queryKey: ['artifacts'] });
    }
  }, [latestSuccess, queries, versionId]);
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <WorkflowPanel
        {...details}
        navigation={navigation}
        restoreFocus={restoreFocus}
        tasks={items}
        tasksComplete={!history.isPending && !history.hasNextPage}
        onClose={onClose}
        draft={draft}
        formContextKey={JSON.stringify(draftKey)}
        updateDraft={updateDraft}
        resetDraft={() => {
          const reset = { ...emptyDraft, machineId: draft.machineId };
          updateDraft(() => ({ ...reset, intent: undefined }));
          if (initialReplay) {
            queries.setQueryData([...versionKey, undefined, undefined], reset);
            details.onReplayChange(null);
          }
        }}
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
    </Dialog.Root>
  );
}

function WorkflowPanel({
  workflow,
  fullscreen,
  onToggleFullscreen,
  currentVersionId,
  versions,
  pendingVersionId,
  onVersionChange,
  initialTab,
  linkedWork,
  onLinkedWorkClose,
  initialReplay,
  projectId,
  initialReplayError,
  onReplayChange,
  replayAfterSignIn,
  requireAuth,
  notify,
  navigation,
  restoreFocus,
  tasks,
  tasksComplete,
  onClose,
  draft,
  formContextKey,
  updateDraft,
  resetDraft,
  operations,
  onPendingChange,
}: WorkflowDetailsProps & {
  navigation?: CollectionNavigation;
  restoreFocus: () => void;
  tasks: Task[];
  /** 当前版本的任务历史是否已全部读取。 */
  tasksComplete: boolean;
  onClose: () => void;
  draft: WorkflowDraft;
  formContextKey: string;
  updateDraft: (update: (draft: WorkflowDraft) => Partial<WorkflowDraft>) => void;
  resetDraft: () => void;
  operations: ReadonlySet<string>;
  onPendingChange: (operation: string, busy: boolean) => void;
}) {
  const { api, state, workspaceScope, workspaceTeam, canEditWorkspace, canManageWorkspace } =
    useWorkspace();
  const { titleRef, focusProps } = useDialogFocus(restoreFocus);
  const queries = useQueryClient();
  const replay = initialReplay;
  const activeWorkflow = replay?.workflow ?? workflow;
  const switchingVersion = !!pendingVersionId;
  const versionOptions = versions.map((version) => ({
    value: version.id,
    label: `v${version.number}${!version.published ? t('workflowDialog.draft') : version.id === currentVersionId ? t('workflowDialog.current') : ''}`,
  }));
  if (!versions.some((version) => version.id === activeWorkflow.versionId)) {
    const before = versions.findIndex((version) => version.number < activeWorkflow.version);
    versionOptions.splice(before === -1 ? versions.length : before, 0, {
      value: activeWorkflow.versionId,
      label: `v${activeWorkflow.version}`,
    });
  }
  const isCurrentVersion = activeWorkflow.versionId === currentVersionId;
  const sharePath = useHref(
    workflowPath(
      workflow.id,
      isCurrentVersion ? undefined : activeWorkflow.versionId,
      fullscreen ? 'fullscreen' : undefined,
    ),
  );
  const defaultTab = initialTab ?? (initialReplay ? 'results' : 'works');
  const [view, setView] = useState({ versionId: activeWorkflow.versionId, tab: defaultTab });
  const { tab } = view;
  function setTab(next: WorkflowTab) {
    setView({ versionId: activeWorkflow.versionId, tab: next });
  }
  const [manageDialog, setManageDialog] = useState<'edit' | 'delete'>();
  const moreAction = useRef<HTMLButtonElement>(null);
  const closeManage = () => setManageDialog(undefined);
  const restoreManageFocus = () => moreAction.current?.focus({ preventScroll: true });
  const [scrollRoot, setScrollRoot] = useState<HTMLDivElement | null>(null);
  const [resultTask, setResultTask] = useState<Pick<Task, 'id' | 'versionId'>>();
  const resultTaskId =
    resultTask?.versionId === activeWorkflow.versionId ? resultTask.id : undefined;
  const [submission, setSubmission] = useState<{ task: Task; userId: string | null }>();
  const [taskDetails, setTaskDetails] = useState<{
    task: Task;
    source: HTMLElement;
    userId: string | null;
  } | null>(null);
  // 切换版本时重置版本内的浏览状态，标题和下拉按钮保留原来的焦点目标。
  if (view.versionId !== activeWorkflow.versionId) {
    setTab(defaultTab);
    setResultTask(undefined);
    setSubmission(undefined);
    setTaskDetails(null);
    setManageDialog(undefined);
  }
  const submittedTask =
    submission?.userId === state.userId && submission?.task.versionId === activeWorkflow.versionId
      ? submission.task
      : undefined;
  const currentTask = state.user
    ? submittedTask
      ? (tasks.find((task) => task.id === submittedTask.id) ?? submittedTask)
      : tasks.find((task) => task.versionId === activeWorkflow.versionId)
    : undefined;
  const officialProgress = useTaskProgress(
    currentTask?.id ?? '',
    currentTask?.worker.tracksTakeover === true && currentTask.status === 'running',
  );
  const formId = useId();
  // 浏览器标签显示当前工作流，关闭弹框后恢复站点名称。
  useEffect(() => {
    const previousTitle = document.title;
    document.title = `${activeWorkflow.name} · ComfyShop`;
    return () => {
      document.title = previousTitle;
    };
  }, [activeWorkflow.name]);
  // 这次提交在弹框打开期间结束时提示一次，用户可能正在看别的标签。
  const watched = useRef<{ id: string; status: Task['status'] } | undefined>(undefined);
  useEffect(() => {
    const previous = watched.current;
    watched.current = currentTask && { id: currentTask.id, status: currentTask.status };
    if (!currentTask || previous?.id !== currentTask.id) return;
    const wasActive = isTaskActive(previous.status);
    if (wasActive && currentTask.status === 'succeeded')
      notify(t('workflowDialog.generationComplete'));
    if (wasActive && currentTask.status === 'failed') notify(t('generationStage.generationFailed'));
  }, [currentTask, notify]);
  // 「我的结果」只看某次提交时，在结果上方呈现这次提交的进度、用时或失败原因。
  const stagedTask = resultTaskId
    ? (tasks.find((task) => task.id === resultTaskId) ??
      (submittedTask?.id === resultTaskId ? submittedTask : undefined))
    : undefined;
  const ownsWorkflow = !workspaceScope && !workflow.teamId && workflow.owner === state.userId;
  const ownsTeamWorkflow = !!workspaceTeam && workflow.teamId === workspaceTeam.id;
  const canManage = isCurrentVersion && (ownsWorkflow || (ownsTeamWorkflow && canEditWorkspace));
  const canPublishWorkflow =
    isCurrentVersion && canManageWorkspace && (ownsWorkflow || ownsTeamWorkflow);
  const ownDraft = canPublishWorkflow && !activeWorkflow.published;
  const showRunForm = canEditWorkspace;
  const resultsLabel = workspaceTeam
    ? t('teams.results')
    : t(workspaceScope ? 'taskDetails.results' : 'executionCollection.myResults');
  // 历史没读完时无法确定有没有成功记录，交给平台在发布时判断。
  const versionSucceeded =
    tasks.some(
      (task) => task.versionId === activeWorkflow.versionId && task.status === 'succeeded',
    ) || (tasksComplete ? false : undefined);
  function loadReplay(next: Replay) {
    onReplayChange(next);
    notify(t('workflowDialog.parametersLoaded'));
  }
  async function download() {
    try {
      const result = await api.graph(workflow.id, activeWorkflow.versionId);
      downloadJson(result.graph, `${activeWorkflow.name}.json`);
    } catch (error) {
      notify(error instanceof Error ? error.message : t('workflowDialog.downloadFailed'));
    }
  }
  function moveVersion(direction: ItemDirection) {
    if (operations.size > 0 || versionOptions.length < 2) return false;
    const from = versionOptions.findIndex(
      ({ value }) => value === (pendingVersionId ?? activeWorkflow.versionId),
    );
    if (from < 0) return false;
    const next = versionOptions[from + direction];
    if (next) {
      if (document.activeElement?.closest('.workflow-dialog-body, .workflow-version-actions'))
        titleRef.current?.focus({ preventScroll: true });
      onVersionChange(next.value, tab);
    }
    return true;
  }
  const galleryReferenceWidth = fullscreen
    ? 'calc(100% - var(--ui-dialog-width) + var(--ui-dialog-normal-width))'
    : undefined;
  const viewer = (
    <section className="workflow-viewer">
      <Tabs.Root
        className="viewer-tabs"
        value={tab}
        onValueChange={(value) => {
          if (value === 'results') setResultTask(undefined);
          setTab(value === 'results' ? 'results' : 'works');
        }}
      >
        <TabsList className="viewer-tab-list" aria-label={t('workflowDialog.workflowContent')}>
          {[
            { id: 'works', label: t('workCollection.works') },
            { id: 'results', label: resultsLabel },
          ].map((item) => (
            <Tabs.Trigger key={item.id} value={item.id} asChild>
              <Button variant="ghost" size="small">
                {item.label}
              </Button>
            </Tabs.Trigger>
          ))}
        </TabsList>
        <div className="viewer-scroll" ref={setScrollRoot}>
          <Tabs.Content value="works" className="gallery-panel">
            <WorkCollection
              key={activeWorkflow.versionId}
              workflowId={workflow.id}
              versionId={activeWorkflow.versionId}
              scope={
                workspaceScope?.kind === 'shared' &&
                !workflow.teamId &&
                workflow.owner === workspaceScope.id
                  ? 'mine'
                  : 'public'
              }
              linkedWork={
                linkedWork?.versionId === activeWorkflow.versionId ? linkedWork : undefined
              }
              onLinkedWorkClose={onLinkedWorkClose}
              scrollRoot={scrollRoot}
              referenceWidth={galleryReferenceWidth}
              emptyAction={
                canManageWorkspace &&
                state.user && (
                  <PublishFromResults
                    workflow={activeWorkflow}
                    label={t(
                      workspaceTeam
                        ? 'workflowDialog.publishAWorkFromTeamResults'
                        : 'workflowDialog.publishAWorkFromMyResults',
                    )}
                    onOpen={() => {
                      setResultTask(undefined);
                      setTab('results');
                    }}
                  />
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
                    <span className="muted">{t('workflowDialog.thisSubmissionOnly')}</span>
                    <Button variant="ghost" size="small" onClick={() => setResultTask(undefined)}>
                      {t('workflowDialog.viewAllResultsForThisVersion')}
                    </Button>
                  </div>
                )}
                {stagedTask && (
                  <GenerationStage
                    task={stagedTask}
                    media={activeWorkflow.media}
                    retry={
                      showRunForm && <RetryButton formId={formId} disabled={operations.size > 0} />
                    }
                  />
                )}
                <div
                  className={stagedTask?.status === 'succeeded' ? 'generation-results' : undefined}
                >
                  <ExecutionCollection
                    key={activeWorkflow.versionId}
                    workflowId={workflow.id}
                    versionId={activeWorkflow.versionId}
                    taskId={resultTaskId}
                    scrollRoot={scrollRoot}
                    referenceWidth={galleryReferenceWidth}
                    quietEmpty={!!stagedTask && stagedTask.status !== 'succeeded'}
                    featured={stagedTask?.status === 'succeeded'}
                    onReplay={loadReplay}
                  />
                </div>
              </>
            ) : (
              <EmptyState
                label={t('workflowDialog.signInToViewGenerationResults')}
                action={
                  <Button
                    size="small"
                    onClick={(event) =>
                      requireAuth(
                        event.currentTarget,
                        undefined,
                        t('workflowDialog.signInToViewYourGeneration'),
                      )
                    }
                  >
                    {t('workflowDialog.signInToViewResults')}
                  </Button>
                }
              />
            )}
          </Tabs.Content>
        </div>
      </Tabs.Root>
    </section>
  );
  const content = (
    <>
      <header className="workflow-dialog-heading workflow-detail-heading">
        <div className="breadcrumb">
          <span aria-hidden="true">{t('app.workflows')}</span>
          <span aria-hidden="true">/</span>
          <Dialog.Title ref={titleRef} tabIndex={-1}>
            {activeWorkflow.name}
          </Dialog.Title>
        </div>
        <div className="dialog-heading-actions">
          {versionOptions.length > 1 ? (
            <Select
              className="workflow-version-select"
              label={t('recordedInputs.workflowVersion')}
              options={versionOptions}
              value={activeWorkflow.versionId}
              disabled={operations.size > 0}
              triggerProps={{ 'aria-busy': switchingVersion || undefined }}
              onValueChange={(versionId) => onVersionChange(versionId, tab)}
            />
          ) : (
            <span className="version">v{activeWorkflow.version}</span>
          )}
          <div className="workflow-version-actions" inert={switchingVersion}>
            <IconButton
              label={
                state.user
                  ? t('workflowDialog.downloadJson')
                  : t('workflowDialog.signInToDownloadJson')
              }
              onClick={(event) =>
                requireAuth(
                  event.currentTarget,
                  download,
                  t('workflowDialog.signInToDownloadTheWorkflow'),
                )
              }
            >
              <DownloadIcon />
            </IconButton>
            {(!workspaceScope || activeWorkflow.published) && (
              <CopyLink
                key={activeWorkflow.versionId}
                href={sharePath}
                title={t('workflowDialog.workflowLink')}
                shareTitle={activeWorkflow.published ? activeWorkflow.name : undefined}
                reserveShareSlot
              />
            )}
            {ownsWorkflow && (
              <CopyToTeam
                source={{ workflowId: workflow.id, versionId: activeWorkflow.versionId }}
              />
            )}
            {canManage ? (
              <DropdownMenu.Root>
                <DropdownMenu.Trigger asChild>
                  <IconButton
                    ref={moreAction}
                    label={t('workflowDialog.moreActions')}
                    disabled={operations.size > 0}
                  >
                    <DotsHorizontalIcon />
                  </IconButton>
                </DropdownMenu.Trigger>
                <DropdownMenu.Portal>
                  <DropdownMenu.Content
                    className="ui-menu"
                    sideOffset={8}
                    align="end"
                    onCloseAutoFocus={(event) => {
                      if (manageDialog) event.preventDefault();
                    }}
                  >
                    <DropdownMenu.Item
                      className="ui-menu-item"
                      onSelect={() => setManageDialog('edit')}
                    >
                      {t('workflowDialog.editWorkflow')}
                    </DropdownMenu.Item>
                    {canPublishWorkflow && (
                      <DropdownMenu.Item
                        className="ui-menu-item"
                        onSelect={() => setManageDialog('delete')}
                      >
                        {t('workflowDialog.deleteWorkflow')}
                      </DropdownMenu.Item>
                    )}
                  </DropdownMenu.Content>
                </DropdownMenu.Portal>
              </DropdownMenu.Root>
            ) : (
              ownsWorkflow && (
                <IconButton
                  className="workflow-manage-slot"
                  label={t('workflowDialog.moreActions')}
                  aria-hidden="true"
                  disabled
                />
              )
            )}
          </div>
          {canManage && manageDialog === 'edit' && (
            <WorkflowSettings
              workflow={activeWorkflow}
              notify={notify}
              onClose={closeManage}
              restoreFocus={restoreManageFocus}
            />
          )}
          {canPublishWorkflow && manageDialog === 'delete' && (
            <DeleteButton
              standalone={{ onClose: closeManage, restoreFocus: restoreManageFocus }}
              label={t('workflowDialog.deleteWorkflow')}
              done={t('workflowDialog.workflowDeleted')}
              undo={() => ({
                label: t('executionDialog.undo'),
                run: async () => {
                  await api.restoreWorkflow(workflow.id);
                  await Promise.all([
                    refreshPublishedContent(queries),
                    queries.invalidateQueries({ queryKey: ['workspace'] }),
                  ]);
                },
              })}
              description={t('workflowDialog.andItsPublicWorksWillBe', workflow.name)}
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
                  queries.invalidateQueries({ queryKey: ['public-team'] }),
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
        </div>
        <div className="workflow-window-actions">
          <IconButton
            className="workflow-fullscreen-toggle"
            label={t(fullscreen ? 'workflowDialog.exitFullscreen' : 'workflowDialog.fullscreen')}
            disabled={switchingVersion || navigation?.pending}
            onClick={onToggleFullscreen}
          >
            {fullscreen ? <ExitFullScreenIcon /> : <EnterFullScreenIcon />}
          </IconButton>
          <DialogClose label={t('common.close')} size="small" />
        </div>
      </header>
      {initialReplayError && (
        <div className="inline-status" role="alert">
          {initialReplayError}
        </div>
      )}
      {!showRunForm ? (
        <div className="workflow-dialog-body" inert={switchingVersion}>
          <div className="workflow-edit-scroll">
            {viewer}
            <div className="run-form-scroll">
              <WorkflowMetadata workflow={activeWorkflow} />
              {workspaceTeam?.role === 'reader' && (
                <div className="form-hint" role="status">
                  {t('teams.generationRequiresEditor')}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <RunForm
          key={formContextKey}
          switchingVersion={switchingVersion}
          viewer={viewer}
          formId={formId}
          workflow={activeWorkflow}
          initialProjectId={replay ? (replay.projectId ?? undefined) : projectId}
          publishAction={
            ownDraft && (
              <PublishWorkflowButton workflow={activeWorkflow} hasSuccess={versionSucceeded} />
            )
          }
          taskSummary={
            currentTask &&
            isTaskActive(currentTask.status) && (
              <div className="current-task">
                <TaskState task={currentTask} progress={officialProgress.data} />
                <div className="task-item-actions">
                  <CancelTaskButton task={currentTask} />
                  <Button
                    variant="ghost"
                    size="small"
                    onClick={() => {
                      setResultTask(currentTask);
                      setTab('results');
                      scrollRoot?.scrollIntoView({ block: 'nearest' });
                    }}
                  >
                    {t('taskDetails.results')}
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
                    {t('taskDetails.taskDetails')}
                  </Button>
                </div>
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
          hiddenInputValues={draft.hiddenInputValues}
          onHiddenInputValuesChange={(update) =>
            updateDraft((prior) => ({ hiddenInputValues: update(prior.hiddenInputValues) }))
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
          onReset={resetDraft}
          requireAuth={requireAuth}
          onRun={(task) => {
            setSubmission({ task, userId: state.userId });
            setResultTask(task);
            setTab('results');
            notify(t('workflowDialog.addedToQueue'));
          }}
        />
      )}
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
  return (
    <BrowseDialogContent
      className="workflow-dialog"
      data-fullscreen={fullscreen || undefined}
      itemId={activeWorkflow.versionId}
      titleRef={titleRef}
      navigation={navigation}
      onVerticalMove={moveVersion}
      onKeyDown={(event) => {
        // 已退出的嵌套预览仍可能处于焦点清理阶段。当前表单的 Esc 走同一个返回入口。
        if (
          event.key === 'Escape' &&
          !event.defaultPrevented &&
          !event.repeat &&
          !event.nativeEvent.isComposing &&
          event.target instanceof Element &&
          event.target.closest('[role="dialog"]') === event.currentTarget &&
          !event.currentTarget.closest('[aria-hidden="true"]')
        ) {
          event.preventDefault();
          onClose();
        }
      }}
      {...focusProps}
    >
      {content}
    </BrowseDialogContent>
  );
}
