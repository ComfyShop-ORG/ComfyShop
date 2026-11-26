/** 网页筛选值和任务文案。状态原始取值由平台 API 定义。 */
import { t } from '../app/i18n.ts';
import type { Machine, Replay, Task, TaskProgress, Workflow } from '@comfyshop/api-client';

export type { Workflow, Task, Media } from '@comfyshop/api-client';
/** all 表示不限分类。 */
export type Category = 'all' | Workflow['category'];
/** updated 按更新时间排序，popular 优先按收藏数排序。 */
export type Sort = 'updated' | 'popular';
export type WorkflowFilters = {
  scope: 'public' | 'mine' | 'favorites';
  category: Category;
  search: string;
  sort: Sort;
  /** 只看这位作者的工作流，值为账号名。 */
  author?: string;
  publicTeamId?: string;
  projectId?: string;
  inpaintArtifactId?: string;
};
export const taskStatus = {
  queued: t('types.queued'),
  running: t('types.generating'),
  succeeded: t('taskList.completed'),
  failed: t('taskList.failed'),
  cancelled: t('taskList.canceled'),
} as const;

export function isTaskActive(status?: Task['status']) {
  return status === 'queued' || status === 'running';
}

const runningStages: Record<string, string> = {
  cloud_waiting: t('connection.waiting'),
  cloud_queued: t('connection.queued'),
  cloud_running: t('connection.running'),
  preflight: t('types.checkingDependencies'),
  connecting: t('types.connectingToComfyui'),
  reconnecting: t('types.connectionLostRetrying'),
  waiting_for_comfy: t('types.waitingForComfyui'),
  uploading: t('types.uploadingOutputs'),
};

export function taskProgressSnapshot(
  task: Task,
  progress?: TaskProgress,
): Task & { officialTakeover?: TaskProgress['officialTakeover'] } {
  return progress && progress.updated >= task.updated ? { ...task, ...progress } : task;
}

/** 由工作机的阶段区分连接、实际执行和回传。 */
export function taskStatusLabel(
  status: keyof typeof taskStatus,
  stage: string,
  takeover?: TaskProgress['officialTakeover'],
) {
  if (status !== 'running') return taskStatus[status];
  if (takeover === 'waiting') return t('taskDetails.officialTakeoverWaiting');
  const label = Object.hasOwn(runningStages, stage) ? runningStages[stage] : taskStatus.running;
  return takeover === 'resumed' ? t('taskDetails.officialTakeoverResumed', label) : label;
}

export function taskHasExecutionProgress(
  status: keyof typeof taskStatus,
  stage: string,
  takeover?: TaskProgress['officialTakeover'],
) {
  return status === 'running' && stage === 'executing' && takeover !== 'waiting';
}

/** 排队任务还没被领取的原因，取值由平台 API 定义。 */
const waitReasons = {
  service_waiting: t('connection.waitingWorker'),
  machine_unassigned: t('types.noWorkMachineAssigned'),
  machine_paused: t('types.workMachinePausedWaitingForIt'),
  machine_offline: t('types.waitingForTheWorkMachineTo'),
  machine_busy: t('types.workMachineBusyWaitingForIt'),
  machine_updating: t('machineUpdate.updating'),
  comfy_unreachable: t('machinesPage.comfyUnreachable'),
  comfy_busy: t('machinesPage.comfyBusy'),
  official_no_recent_poll: t('taskDetails.officialNoRecentPoll'),
  official_busy: t('taskDetails.officialBusy'),
  official_waiting: t('taskDetails.officialWaiting'),
} as const;

export function taskWaitLabel(
  progress?: Pick<TaskProgress, 'waitReason' | 'queueAhead'>,
  official = false,
) {
  const reason = progress?.waitReason && waitReasons[progress.waitReason];
  const ahead = progress?.queueAhead;
  if (official) {
    const place = ahead == null ? '' : t('taskDetails.officialQueueAhead', ahead);
    return [reason || waitReasons.official_waiting, place].filter(Boolean).join(' · ');
  }
  const place =
    ahead === 0 ? t('taskDetails.headOfQueue') : ahead && t('taskDetails.queueAhead', ahead);
  return [reason, place].filter(Boolean).join(' · ') || t('generationStage.waitingForAWorkMachine');
}

export function cloudCancelLabel(status: NonNullable<Task['cloudCancel']>) {
  const labels = {
    accepted: 'connection.cancelAccepted',
    unconfirmed: 'connection.cancelUnconfirmed',
    not_submitted: 'connection.notSubmitted',
  } as const;
  return t(labels[status]);
}

export function comfyStatusLabel(status: Machine['comfyStatus']) {
  switch (status) {
    case 'idle':
      return t('machinesPage.comfyIdle');
    case 'busy':
      return t('machinesPage.comfyBusy');
    case 'unreachable':
      return t('machinesPage.comfyUnreachable');
    default:
      return t('machinesPage.comfyUnknown');
  }
}

export const recoveryLabels = {
  pending: t('taskDetails.recoveryWaiting'),
  unverified: t('taskDetails.recoveryWaiting'),
  uploading: t('taskDetails.recoveryUploading'),
  rerunnable: t('taskDetails.recoveryRerunnable'),
  scheduled: t('taskDetails.recoveryScheduled'),
} as const;

export function retryableIndices(progress?: TaskProgress): number[] {
  return (
    progress?.executions
      .filter(({ recovery }) => recovery === 'rerunnable')
      .map(({ index }) => index) ?? []
  );
}

/** 把一次执行或作品的参数载入生成表单。`source` 是触发按钮，表单关闭后焦点回到这里。 */
export type ReplayAction = (replay: Replay, source: HTMLElement) => void;
