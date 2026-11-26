/** 任务状态的共用呈现：状态与进度、失败原因，以及排队任务的取消入口。 */
import { t } from '../app/i18n.ts';
import { useId, useRef } from 'react';
import type { TaskProgress } from '@comfyshop/api-client';
import { Button, Dialog, DialogClose, DialogContent, ProgressBar } from '@comfyshop/ui';
import { useWorkspace } from '../app/use-workspace';
import {
  cloudCancelLabel,
  taskHasExecutionProgress,
  taskProgressSnapshot,
  taskStatusLabel,
} from '../domain/types';
import type { Task } from '../domain/types';
import { StatusMark, taskTone } from './status-mark';
import { useNotify } from './notify';
import { useAction } from './use-action';

function TaskErrorDetails({ name, error }: { name: string; error: string }) {
  const title = useRef<HTMLHeadingElement>(null);
  const descriptionId = useId();
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <Button
          variant="ghost"
          size="small"
          className="task-error-trigger"
          aria-label={t('taskState.viewErrorDetailsFor', name)}
        >
          {t('taskDetails.errorDetails')}
        </Button>
      </Dialog.Trigger>
      <DialogContent
        size="compact"
        className="task-error-dialog"
        aria-describedby={descriptionId}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          title.current?.focus();
        }}
      >
        <div className="compact-dialog-heading">
          <Dialog.Title ref={title} tabIndex={-1}>
            {t('taskDetails.errorDetails')}
          </Dialog.Title>
          <DialogClose label={t('common.close')} />
        </div>
        <pre id={descriptionId} className="task-error-detail">
          {error}
        </pre>
      </DialogContent>
    </Dialog.Root>
  );
}

/**
 * 取消排队中的任务，或停止执行中的任务。已经完整回传的执行保留为结果。
 * 任务恰好在此刻结束时平台拒绝操作，原因显示在按钮旁。
 */
export function CancelTaskButton({
  task,
}: {
  task: Pick<Task, 'id' | 'workflowName' | 'status' | 'worker' | 'owner'>;
}) {
  const { workspace, canCancelTask } = useWorkspace();
  const running = task.status === 'running';
  const stopping = running && task.worker.connection === 'machine';
  const { busy, error, run } = useAction(
    stopping ? t('taskState.couldNotStop') : t('taskState.couldNotCancel'),
    task.id,
  );
  const notify = useNotify();
  if (!canCancelTask(task)) return null;
  return (
    <>
      <Button
        size="small"
        variant="ghost"
        disabled={busy}
        aria-label={t(stopping ? 'taskState.stopFor' : 'taskState.cancelFor', task.workflowName)}
        onClick={() =>
          void run(async () => {
            const result = await workspace.cancelTask(task.id);
            // 还没开始执行的任务可以回到队列，已经在执行的只能重新提交。
            if (running)
              notify(
                result.cloudCancel
                  ? cloudCancelLabel(result.cloudCancel)
                  : t(stopping ? 'taskState.generationStopped' : 'taskState.taskCanceled'),
              );
            else
              notify(t('taskState.taskCanceled'), {
                label: t('executionDialog.undo'),
                run: () => workspace.resumeTask(task.id),
              });
          })
        }
      >
        {stopping
          ? busy
            ? t('taskState.stopping')
            : t('taskState.stop')
          : busy
            ? t('taskState.canceling')
            : t('deleteButton.cancel')}
      </Button>
      {error && (
        <span className="form-error" role="alert">
          {error}
        </span>
      )}
    </>
  );
}

export function TaskState({ task: current, progress }: { task: Task; progress?: TaskProgress }) {
  const task = taskProgressSnapshot(current, progress);
  const showProgress = taskHasExecutionProgress(task.status, task.stage, task.officialTakeover);
  return (
    <div className="task-state">
      <span className="task-status">
        <StatusMark tone={taskTone[task.status]} />
        <span>
          {taskStatusLabel(task.status, task.stage, task.officialTakeover)}
          {showProgress && ` ${task.progress}%`}
        </span>
        {showProgress && (
          <ProgressBar value={task.progress} label={t('generationStage.generationProgress')} />
        )}
      </span>
      {task.status === 'failed' && task.error && (
        <TaskErrorDetails name={task.workflowName} error={task.error} />
      )}
    </div>
  );
}
