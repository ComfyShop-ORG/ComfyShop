/** 查看工作机的联络、更新状态和平台任务。 */
import { locale } from '../../app/language.ts';
import { t } from '../../app/i18n.ts';
import { useRef, useState } from 'react';
import { skipToken, useQuery } from '@tanstack/react-query';
import { ApiError } from '@comfyshop/api-client';
import type { Replay } from '@comfyshop/api-client';
import { Button, Dialog, DialogClose, DialogContent, ProgressBar } from '@comfyshop/ui';
import { activePollMs } from '../../app/task-queries';
import { useWorkspace } from '../../app/use-workspace';
import { workspaceKey } from '../../app/workspace-scope';
import { TaskDetailsDialog } from '../../components/task-details';
import { useDialogFocus } from '../../components/use-dialog-focus';
import { comfyStatusLabel, taskHasExecutionProgress, taskStatusLabel } from '../../domain/types';
import { machineSystemLabel } from './machine-system';
import { machineUpdateLabel } from './machine-update';

const startupIssues = {
  comfy_connection: t('machineDetailsDialog.startupComfyConnection'),
  comfy_inventory: t('machineDetailsDialog.startupComfyInventory'),
  platform_connection: t('machineDetailsDialog.startupPlatformConnection'),
};

export function MachineDetailsDialog({
  machineId,
  name,
  onClose,
  restoreFocus,
  onReplay,
}: {
  machineId: string;
  name: string;
  onClose: () => void;
  restoreFocus: () => void;
  onReplay: (replay: Replay) => void;
}) {
  const { api, state, workspaceScope } = useWorkspace();
  const { titleRef, focusProps } = useDialogFocus(restoreFocus);
  const taskSource = useRef<HTMLButtonElement>(null);
  const [taskId, setTaskId] = useState<string>();
  const details = useQuery({
    queryKey: ['machines', state.userId, 'detail', machineId, ...workspaceKey(workspaceScope)],
    queryFn: ({ signal }) => api.machine(machineId, signal),
    enabled: !!state.userId,
    staleTime: 0,
    refetchInterval: ({ state }) => {
      if (state.error instanceof ApiError && state.error.status === 404) return false;
      return state.data?.currentTask || state.data?.queuedCount ? activePollMs : 10000;
    },
  });
  const task = useQuery({
    queryKey: ['tasks', 'detail', state.userId, taskId, ...workspaceKey(workspaceScope)],
    queryFn: taskId && state.userId ? ({ signal }) => api.task(taskId, signal) : skipToken,
    staleTime: 0,
  });
  const data = details.isError ? undefined : details.data;
  const currentTask = data?.currentTask;
  const showProgress = currentTask && taskHasExecutionProgress('running', currentTask.stage);
  const machine = data?.machine;
  const lastSeen = machine && machine.lastSeen !== null ? new Date(machine.lastSeen) : null;
  const catalogSyncedAt = machine?.catalogSyncedAt ? new Date(machine.catalogSyncedAt) : null;
  const startupIssueAt = machine?.startupIssueAt ? new Date(machine.startupIssueAt) : null;

  return (
    <Dialog.Root open onOpenChange={(open) => !open && onClose()}>
      <DialogContent size="form" className="machine-details-dialog" {...focusProps}>
        <div className="compact-dialog-heading">
          <Dialog.Title ref={titleRef} tabIndex={-1}>
            {machine?.name ?? name}
          </Dialog.Title>
          <DialogClose label={t('common.close')} />
        </div>
        {details.isPending && (
          <p className="form-hint" role="status">
            {t('machineDetailsDialog.loadingWorkMachineDetails')}
          </p>
        )}
        {details.error && (
          <div className="inline-status" role="alert">
            {details.error.message}
            <Button size="small" onClick={() => void details.refetch()}>
              {t('app.retry')}
            </Button>
          </div>
        )}
        {data && machine && (
          <>
            <dl className="machine-facts">
              <div className="machine-facts-device">
                <dt>{t('machineDetailsDialog.device')}</dt>
                <dd>{machine.device || t('machineDetailsDialog.unreported')}</dd>
              </div>
              <div>
                <dt>{t('machineDetailsDialog.operatingSystem')}</dt>
                <dd>{machineSystemLabel(machine.operatingSystem)}</dd>
              </div>
              <div>
                <dt>{t('machineDetailsDialog.runtimeVersion')}</dt>
                <dd title={machine.runtime?.build ?? undefined}>
                  {machine.runtime?.version ?? t('machineDetailsDialog.unknownVersion')}
                </dd>
              </div>
              <div>
                <dt>{t('machineDetailsDialog.nodeCount')}</dt>
                <dd>
                  {lastSeen
                    ? t('machineDetailsDialog.count', machine.nodeCount)
                    : t('machineDetailsDialog.notSynced')}
                </dd>
              </div>
              <div>
                <dt>{t('machineDetailsDialog.platformConnection')}</dt>
                <dd>{t(machine.online ? 'machinesPage.online' : 'machinesPage.offline')}</dd>
              </div>
              <div>
                <dt>{t('machineDetailsDialog.comfyStatus')}</dt>
                <dd>
                  {machine.busy && machine.comfyStatus === 'busy'
                    ? t('machinesPage.busy')
                    : comfyStatusLabel(machine.comfyStatus)}
                </dd>
              </div>
              <div>
                <dt>{t('machineDetailsDialog.recentStartupIssue')}</dt>
                <dd>
                  {machine.startupIssue
                    ? startupIssues[machine.startupIssue]
                    : t('machineDetailsDialog.noStartupIssue')}
                  {startupIssueAt && (
                    <>
                      {' · '}
                      <time dateTime={startupIssueAt.toISOString()}>
                        {startupIssueAt.toLocaleString(locale)}
                      </time>
                    </>
                  )}
                </dd>
              </div>
              <div>
                <dt>{t('machineDetailsDialog.catalogSyncedAt')}</dt>
                <dd>
                  {catalogSyncedAt ? (
                    <time dateTime={catalogSyncedAt.toISOString()}>
                      {catalogSyncedAt.toLocaleString(locale)}
                    </time>
                  ) : (
                    t('machineDetailsDialog.notSynced')
                  )}
                </dd>
              </div>
              <div>
                <dt>{t('machineDetailsDialog.lastSeen')}</dt>
                <dd>
                  {lastSeen ? (
                    <time dateTime={lastSeen.toISOString()}>{lastSeen.toLocaleString(locale)}</time>
                  ) : (
                    t('machineDetailsDialog.neverConnected')
                  )}
                </dd>
              </div>
              <div>
                <dt>{t('machineDetailsDialog.updateStatus')}</dt>
                <dd className={machine.update?.status === 'failed' ? 'form-error' : undefined}>
                  {machineUpdateLabel(machine.update) ??
                    (machine.updateAvailable
                      ? t('machineDetailsDialog.updateAvailable')
                      : t('machineDetailsDialog.noUpdatesRecorded'))}
                </dd>
              </div>
              <div>
                <dt>{t('machineDetailsDialog.queuedTasks')}</dt>
                <dd>{t('machineDetailsDialog.count', data.queuedCount)}</dd>
              </div>
              <div>
                <dt>{t('machineDetailsDialog.acceptingTasks')}</dt>
                <dd>
                  {machine.revoked
                    ? t('machineDetailsDialog.revoked')
                    : machine.paused
                      ? t('machineDetailsDialog.paused')
                      : t('machineDetailsDialog.enabled')}
                </dd>
              </div>
            </dl>
            <section>
              <div className="task-progress-heading">
                <h3>{t('machineDetailsDialog.currentTask')}</h3>
                {currentTask && (
                  <span className="muted">
                    {taskStatusLabel('running', currentTask.stage)}
                    {showProgress && ` · ${currentTask.progress}%`}
                  </span>
                )}
              </div>
              {currentTask ? (
                <div className="machine-current-task">
                  <strong>{currentTask.workflowName}</strong>
                  {showProgress && (
                    <ProgressBar
                      label={t('taskDetails.taskProgress')}
                      value={currentTask.progress}
                    />
                  )}
                  <Button
                    key={currentTask.id}
                    ref={taskSource}
                    size="small"
                    aria-haspopup="dialog"
                    disabled={!!taskId && task.isPending}
                    onClick={() => setTaskId(currentTask.id)}
                  >
                    {t('machineDetailsDialog.viewTaskDetails')}
                  </Button>
                </div>
              ) : (
                <p className="form-hint">{t('machineDetailsDialog.noRunningTask')}</p>
              )}
            </section>
          </>
        )}
        {taskId && task.isPending && (
          <p className="form-hint" role="status">
            {t('machineDetailsDialog.loadingTaskDetails')}
          </p>
        )}
        {taskId && task.error && (
          <div className="inline-status" role="alert">
            {task.error.message}
            <Button size="small" onClick={() => void task.refetch()}>
              {t('app.retry')}
            </Button>
          </div>
        )}
        {taskId && task.data && (
          <TaskDetailsDialog
            task={task.data}
            onClose={() => setTaskId(undefined)}
            restoreFocus={() =>
              (taskSource.current ?? titleRef.current)?.focus({ preventScroll: true })
            }
            onReplay={onReplay}
          />
        )}
      </DialogContent>
    </Dialog.Root>
  );
}
