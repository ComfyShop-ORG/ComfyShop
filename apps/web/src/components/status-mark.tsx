/** 状态色块：用同一组色调表达任务和工作机所处的状态。 */
import type { Task } from '../domain/types';

/** active 进行中，success 可用或已完成，waiting 等待，danger 失败，idle 未在工作。 */
export type StatusTone = 'active' | 'success' | 'waiting' | 'danger' | 'idle';

export const taskTone: Record<Task['status'], StatusTone> = {
  queued: 'waiting',
  running: 'active',
  succeeded: 'success',
  failed: 'danger',
  cancelled: 'idle',
};

export function StatusMark({ tone }: { tone: StatusTone }) {
  return <span className="status-mark" data-tone={tone} aria-hidden="true" />;
}
