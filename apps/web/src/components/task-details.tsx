/** 任务详情弹框，分别展示活动进度、提交时的参数和已完成的执行结果。 */
import { locale } from '../app/language.ts';
import { cloudCancelLabel, isTaskActive } from '../domain/types';
import { t } from '../app/i18n.ts';
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { TaskProgress } from '@comfyshop/api-client';
import {
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  ProgressBar,
  Tabs,
  TabsList,
} from '@comfyshop/ui';
import { useTaskProgress, useWorkspace } from '../app/use-workspace';
import { assetUsageKey } from '../features/assets/asset-queries';
import { TaskProjectButton } from '../features/projects/task-project-button';
import {
  recoveryLabels,
  retryableIndices,
  taskHasExecutionProgress,
  taskProgressSnapshot,
  taskStatus,
  taskStatusLabel,
  taskWaitLabel,
} from '../domain/types';
import type { Task } from '../domain/types';
import { ExecutionCollection } from './execution-collection';
import type { ReplayAction } from '../domain/types';
import { RecordedInputs } from './recorded-inputs';
import { useDialogFocus } from './use-dialog-focus';
import { DeleteButton } from './delete-button';
import { durationLabel } from './generation-stage';
import { CancelTaskButton } from './task-state';
import { RetryExecutionsButton, TaskQueueActions } from './task-queue-actions';

const takeoverOutcomes = {
  waiting: t('taskDetails.takeoverWaitOngoing'),
  resumed: t('taskDetails.takeoverWaitResumed'),
  ended: t('taskDetails.takeoverWaitEnded'),
};

function TakeoverHistory({ history }: { history: NonNullable<TaskProgress['takeoverHistory']> }) {
  if (!history.waits.length) return null;
  const title = t('taskDetails.takeoverHistory');
  return (
    <section className="task-takeover-history" aria-label={title}>
      <div className="task-progress-heading">
        <h3>{title}</h3>
      </div>
      <ol className="task-execution-list">
        {history.waits.map((wait) => {
          const start = new Date(wait.startedAt);
          const end = wait.endedAt === null ? null : new Date(wait.endedAt);
          return (
            <li key={wait.number}>
              <div>
                <div>
                  {t('taskDetails.takeoverWaitNumber', wait.number)} ·{' '}
                  {takeoverOutcomes[wait.outcome]}
                </div>
                <div className="muted">
                  <time dateTime={start.toISOString()}>{start.toLocaleString(locale)}</time>
                  {' – '}
                  {end ? (
                    <time dateTime={end.toISOString()}>
                      {start.toDateString() === end.toDateString()
                        ? end.toLocaleTimeString(locale)
                        : end.toLocaleString(locale)}
                    </time>
                  ) : (
                    t('taskDetails.takeoverWaitNow')
                  )}
                </div>
              </div>
              <span>{t('taskDetails.takeoverWaitDuration', durationLabel(wait.durationMs))}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export function TaskDetailsDialog({
  task,
  initialTab = 'progress',
  onClose,
  onDeleted = onClose,
  restoreFocus,
  onReplay,
  onProjectChanged,
}: {
  task: Task;
  initialTab?: 'progress' | 'results';
  onClose: () => void;
  onDeleted?: () => void;
  restoreFocus: () => void;
  onReplay: ReplayAction;
  onProjectChanged?: (projectId: string | null) => void;
}) {
  const { api, state, workspaceScope, canManageWorkspace, canCancelTask } = useWorkspace();
  const queries = useQueryClient();
  const { titleRef, focusProps } = useDialogFocus(restoreFocus);
  const [scrollRoot, setScrollRoot] = useState<HTMLDivElement | null>(null);
  const [projectId, setProjectId] = useState(task.projectId);
  const query = useTaskProgress(task.id, true, task.worker.tracksTakeover);
  const snapshot = taskProgressSnapshot(task, query.data);
  const active = isTaskActive(snapshot.status);
  const takeover = snapshot.officialTakeover;
  const showProgress =
    snapshot.status === 'succeeded' ||
    taskHasExecutionProgress(snapshot.status, snapshot.stage, takeover);
  const executions = query.data?.executions ?? [];
  const completed = executions.filter(({ status }) => status === 'succeeded').length;
  const retryable = retryableIndices(query.data);
  const refreshAfterDeletion = () =>
    Promise.all([
      queries.invalidateQueries({ queryKey: ['tasks'] }),
      queries.invalidateQueries({ queryKey: assetUsageKey(state.userId, workspaceScope) }),
    ]);
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="result-dialog task-details-dialog" {...focusProps}>
        <header className="workflow-dialog-heading dialog-heading-wrap">
          <Dialog.Title ref={titleRef} tabIndex={-1}>
            {t('taskDetails.taskDetails')}
          </Dialog.Title>
          {(canCancelTask(task) || (!active && canManageWorkspace)) && (
            <div className="dialog-heading-actions">
              <TaskProjectButton
                taskId={task.id}
                ownerId={task.owner}
                projectId={projectId}
                onChanged={(next) => {
                  setProjectId(next);
                  onProjectChanged?.(next);
                }}
              />
              {active && <CancelTaskButton task={{ ...task, status: snapshot.status }} />}
              {!active && canManageWorkspace && (
                <DeleteButton
                  label={t('taskDetails.deleteTaskRecord')}
                  done={t('taskDetails.taskRecordDeleted')}
                  undo={() => ({
                    label: t('executionDialog.undo'),
                    run: async () => {
                      await api.restoreTask(task.id);
                      await refreshAfterDeletion();
                    },
                  })}
                  description={t('taskDetails.thisTaskForWillBeRemoved', task.workflowName)}
                  onDelete={async () => {
                    await api.deleteTask(task.id);
                    await refreshAfterDeletion();
                  }}
                  onDeleted={() => {
                    onDeleted();
                    queries.removeQueries({ queryKey: ['task-progress', state.userId, task.id] });
                  }}
                />
              )}
            </div>
          )}
          <DialogClose label={t('common.close')} size="small" />
        </header>
        <div className="task-details-name">{task.workflowName}</div>
        <Tabs.Root className="dialog-tabs" defaultValue={initialTab}>
          <TabsList className="dialog-tab-list" aria-label={t('taskDetails.taskDetails')}>
            <Tabs.Trigger value="progress" asChild>
              <Button size="small" variant="ghost">
                {t('taskDetails.activity')}
              </Button>
            </Tabs.Trigger>
            <Tabs.Trigger value="inputs" asChild>
              <Button size="small" variant="ghost">
                {t('taskDetails.submittedParameters')}
              </Button>
            </Tabs.Trigger>
            <Tabs.Trigger value="results" asChild>
              <Button size="small" variant="ghost">
                {t('taskDetails.results')}
              </Button>
            </Tabs.Trigger>
          </TabsList>
          <Tabs.Content value="progress" className="collection-scroll">
            <div className="task-progress-heading" aria-live="polite">
              <strong data-status={snapshot.status}>
                {taskStatusLabel(snapshot.status, snapshot.stage, takeover)}
              </strong>
              {showProgress && <span className="muted">{snapshot.progress}%</span>}
            </div>
            {showProgress && (
              <ProgressBar value={snapshot.progress} label={t('taskDetails.taskProgress')} />
            )}
            {snapshot.status === 'queued' && query.data && !query.error && (
              <>
                <p className="form-hint" role="status">
                  {taskWaitLabel(query.data, task.worker.tracksTakeover)}
                </p>
                {canManageWorkspace && task.worker.connection === 'machine' && (
                  <TaskQueueActions taskId={task.id} machineId={query.data.machineId} />
                )}
              </>
            )}
            {task.cloudCancel && (
              <p className="form-hint" role="status">
                {cloudCancelLabel(task.cloudCancel)}
              </p>
            )}
            <dl className="task-facts">
              {task.worker.connection !== 'platform' && (
                <div>
                  <dt>{t('app.workMachines')}</dt>
                  <dd>
                    {query.data?.machineName ??
                      task.machineName ??
                      (task.machineId ? '—' : t('taskDetails.unassigned'))}
                  </dd>
                </div>
              )}
              <div>
                <dt>{t('taskDetails.submitted')}</dt>
                <dd>{new Date(task.started).toLocaleString(locale)}</dd>
              </div>
              <div>
                <dt>{active ? t('taskDetails.lastUpdated') : t('taskDetails.elapsedTime')}</dt>
                <dd>
                  {active
                    ? new Date(snapshot.updated).toLocaleString(locale)
                    : durationLabel(snapshot.updated - task.started)}
                </dd>
              </div>
            </dl>
            {query.data?.takeoverHistory && (
              <TakeoverHistory history={query.data.takeoverHistory} />
            )}
            {snapshot.error && (
              <section className="task-details-error">
                <h3>{t('taskDetails.errorDetails')}</h3>
                <pre className="task-error-detail">{snapshot.error}</pre>
              </section>
            )}
            {query.error && (
              <div className="inline-status" role="alert">
                {query.error.message}
                <Button size="small" onClick={() => void query.refetch()}>
                  {t('app.retry')}
                </Button>
              </div>
            )}
            {query.isPending && (
              <div className="empty-state" role="status">
                {t('taskDetails.loadingRuns')}
              </div>
            )}
            {!!executions.length && (
              <>
                <div className="task-progress-heading">
                  <h3>{t('taskDetails.runs')}</h3>
                  <span className="muted">
                    {t('taskDetails.ofRunsComplete', completed, task.executionCount)}
                  </span>
                </div>
                <ul className="task-execution-list" aria-label={t('taskDetails.runs')}>
                  {executions.map((execution) => (
                    <li key={execution.id}>
                      <span>{t('taskDetails.run', execution.index + 1)}</span>
                      <span data-status={execution.status}>
                        {execution.recovery
                          ? recoveryLabels[execution.recovery]
                          : execution.status === 'running'
                            ? t('taskDetails.running')
                            : taskStatus[execution.status]}
                      </span>
                    </li>
                  ))}
                </ul>
                {retryable.length > 0 && (
                  <RetryExecutionsButton
                    taskId={task.id}
                    service={task.worker.connection !== 'machine'}
                    machineId={query.data?.machineId}
                    indices={retryable}
                  />
                )}
              </>
            )}
          </Tabs.Content>
          <Tabs.Content value="inputs" className="collection-scroll">
            <RecordedInputs taskId={task.id} values={task.inputValues} />
          </Tabs.Content>
          <Tabs.Content value="results" className="collection-scroll" ref={setScrollRoot}>
            <ExecutionCollection taskId={task.id} scrollRoot={scrollRoot} onReplay={onReplay} />
          </Tabs.Content>
        </Tabs.Root>
      </DialogContent>
    </Dialog.Root>
  );
}
