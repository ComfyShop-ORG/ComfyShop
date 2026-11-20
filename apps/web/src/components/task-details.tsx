/** 任务详情弹框，分别展示活动进度、提交时的参数和已完成的执行结果。 */
import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Dialog, DialogClose, DialogContent, ProgressBar, Tabs } from '@comfyshop/ui';
import { activePollMs } from '../app/task-queries';
import { useWorkspace } from '../app/use-workspace';
import { taskStatus, taskStatusLabel, waitReasons } from '../domain/types';
import type { Task } from '../domain/types';
import { ExecutionCollection } from './execution-collection';
import type { ReplayAction } from '../domain/types';
import { RecordedInputs } from './recorded-inputs';
import { useDialogFocus } from './use-dialog-focus';
import { DeleteButton } from './delete-button';
import { durationLabel } from './generation-stage';
import { CancelTaskButton } from './task-state';

export function TaskDetailsDialog({
  task,
  initialTab = 'progress',
  onClose,
  onDeleted = onClose,
  restoreFocus,
  onReplay,
}: {
  task: Task;
  initialTab?: 'progress' | 'results';
  onClose: () => void;
  onDeleted?: () => void;
  restoreFocus: () => void;
  onReplay: ReplayAction;
}) {
  const { api, state } = useWorkspace();
  const queries = useQueryClient();
  const { titleRef, focusProps } = useDialogFocus(restoreFocus);
  const [scrollRoot, setScrollRoot] = useState<HTMLDivElement | null>(null);
  const query = useQuery({
    queryKey: ['task-progress', state.userId, task.id],
    enabled: !!state.userId,
    queryFn: ({ signal }) => api.taskProgress(task.id, signal),
    refetchInterval: ({ state }) => {
      const status = state.data?.status ?? task.status;
      return status === 'queued' || status === 'running' ? activePollMs : false;
    },
  });
  const snapshot = query.data ?? task;
  const active = snapshot.status === 'queued' || snapshot.status === 'running';
  const executions = query.data?.executions ?? [];
  const completed = executions.filter(({ status }) => status === 'succeeded').length;
  const waitReason = query.data?.waitReason;
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
            任务详情
          </Dialog.Title>
          <div className="dialog-heading-actions">
            {active && <CancelTaskButton task={{ ...task, status: snapshot.status }} />}
            {snapshot.status !== 'queued' && snapshot.status !== 'running' && (
              <DeleteButton
                label="删除任务记录"
                done="已删除任务记录"
                undo={() => ({
                  label: '撤销',
                  run: async () => {
                    await api.restoreTask(task.id);
                    await queries.invalidateQueries({ queryKey: ['tasks'] });
                  },
                })}
                description={`将从任务列表移除「${task.workflowName}」的这次任务。已生成的成品可在「结果」查看。`}
                onDelete={async () => {
                  await api.deleteTask(task.id);
                  await queries.invalidateQueries({ queryKey: ['tasks'] });
                }}
                onDeleted={() => {
                  onDeleted();
                  queries.removeQueries({ queryKey: ['task-progress', state.userId, task.id] });
                }}
              />
            )}
          </div>
          <DialogClose />
        </header>
        <div className="task-details-name">{task.workflowName}</div>
        <Tabs.Root className="dialog-tabs" defaultValue={initialTab}>
          <Tabs.List className="dialog-tab-list" aria-label="任务详情">
            <Tabs.Trigger value="progress" asChild>
              <Button size="small" variant="ghost">
                执行过程
              </Button>
            </Tabs.Trigger>
            <Tabs.Trigger value="inputs" asChild>
              <Button size="small" variant="ghost">
                提交参数
              </Button>
            </Tabs.Trigger>
            <Tabs.Trigger value="results" asChild>
              <Button size="small" variant="ghost">
                结果
              </Button>
            </Tabs.Trigger>
          </Tabs.List>
          <Tabs.Content value="progress" className="collection-scroll">
            <div className="task-progress-heading" aria-live="polite">
              <strong data-status={snapshot.status}>
                {taskStatusLabel(snapshot.status, snapshot.stage)}
              </strong>
              <span className="muted">{snapshot.progress}%</span>
            </div>
            <ProgressBar value={snapshot.progress} label="任务进度" />
            {snapshot.status === 'queued' && query.data && !query.error && (
              <p className="form-hint" role="status">
                {waitReason ? waitReasons[waitReason] : '等待工作机领取'}
              </p>
            )}
            <dl className="task-facts">
              <div>
                <dt>工作机</dt>
                <dd>{query.data?.machineName ?? (task.machineId ? '—' : '未分配')}</dd>
              </div>
              <div>
                <dt>提交时间</dt>
                <dd>{new Date(task.started).toLocaleString('zh-CN')}</dd>
              </div>
              <div>
                <dt>{active ? '最后更新' : '用时'}</dt>
                <dd>
                  {active
                    ? new Date(snapshot.updated).toLocaleString('zh-CN')
                    : durationLabel(snapshot.updated - task.started)}
                </dd>
              </div>
            </dl>
            {snapshot.error && (
              <section className="task-details-error">
                <h3>错误信息</h3>
                <pre className="task-error-detail">{snapshot.error}</pre>
              </section>
            )}
            {query.error && (
              <div className="inline-status" role="alert">
                {query.error.message}
                <Button size="small" onClick={() => void query.refetch()}>
                  重试
                </Button>
              </div>
            )}
            {query.isPending && (
              <div className="empty-state" role="status">
                正在读取执行记录
              </div>
            )}
            {!!executions.length && (
              <>
                <div className="task-progress-heading">
                  <h3>执行记录</h3>
                  <span className="muted">
                    已完成 {completed} / {task.executionCount} 次
                  </span>
                </div>
                <ul className="task-execution-list" aria-label="执行记录">
                  {executions.map((execution) => (
                    <li key={execution.id}>
                      <span>第 {execution.index + 1} 次执行</span>
                      <span data-status={execution.status}>
                        {execution.status === 'running' ? '执行中' : taskStatus[execution.status]}
                      </span>
                    </li>
                  ))}
                </ul>
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
