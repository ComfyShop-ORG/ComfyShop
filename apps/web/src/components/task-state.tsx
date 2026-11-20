/** 任务状态的共用呈现：状态与进度、失败原因，以及排队任务的取消入口。 */
import { useId, useRef } from 'react';
import { Button, Dialog, DialogClose, DialogContent, ProgressBar } from '@comfyshop/ui';
import { useWorkspace } from '../app/use-workspace';
import { taskStatusLabel } from '../domain/types';
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
          aria-label={`查看 ${name} 的错误信息`}
        >
          错误信息
        </Button>
      </Dialog.Trigger>
      <DialogContent
        compact
        className="task-error-dialog"
        aria-describedby={descriptionId}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          title.current?.focus();
        }}
      >
        <div className="compact-dialog-heading">
          <Dialog.Title ref={title} tabIndex={-1}>
            错误信息
          </Dialog.Title>
          <DialogClose />
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
export function CancelTaskButton({ task }: { task: Pick<Task, 'id' | 'workflowName' | 'status'> }) {
  const { workspace } = useWorkspace();
  const running = task.status === 'running';
  const { busy, error, run } = useAction(running ? '停止失败' : '取消失败', task.id);
  const notify = useNotify();
  return (
    <>
      <Button
        size="small"
        variant="ghost"
        disabled={busy}
        aria-label={`${running ? '停止' : '取消'} ${task.workflowName} 的${running ? '生成' : '排队任务'}`}
        onClick={() =>
          void run(async () => {
            await workspace.cancelTask(task.id);
            // 还没开始执行的任务可以回到队列，已经在执行的只能重新提交。
            if (running) notify('已停止生成');
            else
              notify('已取消任务', {
                label: '撤销',
                run: () => workspace.resumeTask(task.id),
              });
          })
        }
      >
        {running ? (busy ? '停止中' : '停止') : busy ? '取消中' : '取消'}
      </Button>
      {error && (
        <span className="form-error" role="alert">
          {error}
        </span>
      )}
    </>
  );
}

export function TaskState({ task }: { task: Task }) {
  return (
    <div className="task-state">
      <span className="task-status">
        <StatusMark tone={taskTone[task.status]} />
        <span>
          {taskStatusLabel(task.status, task.stage)}
          {task.status === 'running' && ` ${task.progress}%`}
        </span>
        {task.status === 'running' && <ProgressBar value={task.progress} label="生成进度" />}
      </span>
      {task.status === 'failed' && task.error && (
        <TaskErrorDetails name={task.workflowName} error={task.error} />
      )}
    </div>
  );
}
