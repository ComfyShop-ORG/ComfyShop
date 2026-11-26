/** 一次提交在工作流弹框里的现场：等待和生成时的占位与进度，结束后的用时或失败原因。 */
import { t } from '../app/i18n.ts';
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import type { Media } from '@comfyshop/api-client';
import { Button } from '@comfyshop/ui';
import { useTaskProgress } from '../app/use-workspace';
import {
  isTaskActive,
  retryableIndices,
  taskHasExecutionProgress,
  taskProgressSnapshot,
  taskStatusLabel,
  taskWaitLabel,
} from '../domain/types';
import type { Task } from '../domain/types';
import { StatusMark, taskTone } from './status-mark';
import { CancelTaskButton } from './task-state';
import { RetryExecutionsButton } from './task-queue-actions';

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
  const active = isTaskActive(task.status);
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
  task: current,
  media,
  retry,
}: {
  task: Task;
  media?: Media | null;
  retry?: ReactNode;
}) {
  const progress = useTaskProgress(current.id, current.status !== 'succeeded').data;
  const task = taskProgressSnapshot(current, progress);
  const active = isTaskActive(task.status);
  const elapsed = useElapsed(task);
  const executions = progress?.executions ?? [];
  const retryable = retryableIndices(progress);
  const finished = executions.filter(({ status }) => status === 'succeeded').length;
  const label = taskStatusLabel(task.status, task.stage, task.officialTakeover);
  const showProgress = taskHasExecutionProgress(task.status, task.stage, task.officialTakeover);
  if (active)
    return (
      <section className="generation-stage" aria-label={t('generationStage.generationProgress')}>
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
            style={{ height: `${showProgress ? task.progress : 0}%` }}
          />
          <div className="generation-readout" role="status">
            <span className="generation-state">
              <StatusMark tone={taskTone[task.status]} />
              {label}
            </span>
            {showProgress && <strong className="generation-percent">{task.progress}%</strong>}
            <span className="muted">
              {task.executionCount > 1 &&
                (task.worker.connection !== 'machine'
                  ? `${t('taskDetails.ofRunsComplete', finished, task.executionCount)} · `
                  : t(
                      'generationStage.runOf',
                      Math.min(finished + 1, task.executionCount),
                      task.executionCount,
                    ))}
              {task.status === 'queued'
                ? t('generationStage.waitingFor')
                : t('generationStage.elapsed')}{' '}
              {durationLabel(elapsed)}
            </span>
          </div>
        </div>
        <div className="generation-note">
          {(task.status === 'queued' || task.worker.connection !== 'platform') && (
            <span className="form-hint">
              {task.status === 'queued'
                ? taskWaitLabel(progress, task.worker.tracksTakeover)
                : (progress?.machineName ?? '')}
            </span>
          )}
          <CancelTaskButton task={task} />
        </div>
      </section>
    );
  return (
    <section className="generation-stage" aria-label={t('generationStage.results')}>
      <div className="generation-summary" data-status={task.status} role="status">
        <span className="generation-state">
          <StatusMark tone={taskTone[task.status]} />
          {task.status === 'failed' ? t('generationStage.generationFailed') : label}
          {task.status === 'succeeded' && (
            <span className="muted">{t('generationStage.elapsed2', durationLabel(elapsed))}</span>
          )}
        </span>
        {retryable.length > 0 ? (
          <RetryExecutionsButton
            taskId={task.id}
            service={task.worker.connection !== 'machine'}
            machineId={task.machineId}
            indices={retryable}
          />
        ) : task.status === 'succeeded' ? (
          retry
        ) : null}
      </div>
      {executions.some(({ recovery }) => recovery === 'uploading') ? (
        <p className="form-hint" role="status">
          {t('taskDetails.recoveryUploading')}
        </p>
      ) : executions.some(({ recovery }) => recovery === 'pending' || recovery === 'unverified') ? (
        <p className="form-hint" role="status">
          {t('taskDetails.recoveryWaiting')}
        </p>
      ) : null}
      {task.status === 'failed' && task.error && (
        <pre className="task-error-detail generation-error">{task.error}</pre>
      )}
    </section>
  );
}

/** 生成按钮之外的再次提交入口，沿用运行表单当前的参数。 */
export function RetryButton({ formId, disabled }: { formId: string; disabled?: boolean }) {
  return (
    <Button size="small" type="submit" form={formId} variant="secondary" disabled={disabled}>
      {t('generationStage.runAgain')}
    </Button>
  );
}
