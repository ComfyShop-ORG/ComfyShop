/** 一次提交在工作流弹框里的现场：等待和生成时的占位与进度，结束后的用时或失败原因。 */
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { Media } from '@comfyshop/api-client';
import { Button } from '@comfyshop/ui';
import { activePollMs } from '../app/task-queries';
import { useWorkspace } from '../app/use-workspace';
import { taskStatusLabel, waitReasons } from '../domain/types';
import type { Task } from '../domain/types';
import { StatusMark, taskTone } from './status-mark';
import { CancelTaskButton } from './task-state';

const isActive = (status: Task['status']) => status === 'queued' || status === 'running';

/** 把毫秒时长写成「分:秒」，超过一小时写成「时:分:秒」。 */
export function durationLabel(milliseconds: number) {
  const seconds = Math.max(0, Math.round(milliseconds / 1000));
  const pad = (value: number) => String(value).padStart(2, '0');
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours
    ? `${hours}:${pad(minutes)}:${pad(seconds % 60)}`
    : `${minutes}:${pad(seconds % 60)}`;
}

/** 任务进行中每秒更新一次当前时间，结束后停在最后更新的时刻。 */
function useElapsed(task: Task) {
  const active = isActive(task.status);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active]);
  return (active ? Math.max(now, task.updated) : task.updated) - task.started;
}

/**
 * @param task 这次提交的任务，状态和进度由调用方随活动轮询更新。
 * @param media 用来确定占位比例的参考媒体，通常是工作流封面。没有时使用正方形。
 * @param retry 结束后的再次生成入口，由运行表单提供。
 */
export function GenerationStage({
  task,
  media,
  retry,
}: {
  task: Task;
  media?: Media | null;
  retry?: ReactNode;
}) {
  const { api, state } = useWorkspace();
  const active = isActive(task.status);
  const elapsed = useElapsed(task);
  const progress = useQuery({
    queryKey: ['task-progress', state.userId, task.id],
    enabled: !!state.userId && active,
    queryFn: ({ signal }) => api.taskProgress(task.id, signal),
    refetchInterval: active ? activePollMs : false,
  }).data;
  const executions = progress?.executions ?? [];
  const finished = executions.filter(({ status }) => status === 'succeeded').length;
  const label = taskStatusLabel(task.status, task.stage);
  if (active)
    return (
      <section className="generation-stage" aria-label="生成进度">
        <div
          className="generation-canvas"
          data-status={task.status}
          style={{
            aspectRatio:
              media?.width && media.height ? `${media.width} / ${media.height}` : '1 / 1',
          }}
        >
          <span
            className="generation-fill"
            style={{ height: `${task.status === 'running' ? task.progress : 0}%` }}
          />
          <div className="generation-readout" role="status">
            <span className="generation-state">
              <StatusMark tone={taskTone[task.status]} />
              {label}
            </span>
            {task.status === 'running' && (
              <strong className="generation-percent">{task.progress}%</strong>
            )}
            <span className="muted">
              {task.executionCount > 1 &&
                `第 ${Math.min(finished + 1, task.executionCount)} / ${task.executionCount} 次 · `}
              {task.status === 'queued' ? '已等待' : '已用时'} {durationLabel(elapsed)}
            </span>
          </div>
        </div>
        <div className="generation-note">
          <span className="form-hint">
            {task.status === 'running'
              ? (progress?.machineName ?? '')
              : progress?.waitReason
                ? waitReasons[progress.waitReason]
                : '等待工作机领取'}
          </span>
          <CancelTaskButton task={task} />
        </div>
      </section>
    );
  return (
    <section className="generation-stage" aria-label="生成结果">
      <div className="generation-summary" data-status={task.status} role="status">
        <span className="generation-state">
          <StatusMark tone={taskTone[task.status]} />
          {task.status === 'failed' ? '生成失败' : label}
          {task.status === 'succeeded' && (
            <span className="muted">用时 {durationLabel(elapsed)}</span>
          )}
        </span>
        {retry}
      </div>
      {task.status === 'failed' && task.error && (
        <pre className="task-error-detail generation-error">{task.error}</pre>
      )}
    </section>
  );
}

/** 生成按钮之外的再次提交入口，沿用运行表单当前的参数。 */
export function RetryButton({
  formId,
  failed,
  disabled,
}: {
  formId: string;
  failed: boolean;
  disabled?: boolean;
}) {
  return (
    <Button
      size="small"
      type="submit"
      form={formId}
      variant={failed ? 'primary' : 'secondary'}
      disabled={disabled}
    >
      {failed ? '重新生成' : '再生成一次'}
    </Button>
  );
}
