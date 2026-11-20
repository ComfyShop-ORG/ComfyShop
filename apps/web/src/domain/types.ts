/** 网页筛选值和任务文案。状态原始取值由平台 API 定义。 */
import type { Replay, Workflow } from '@comfyshop/api-client';

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
};
export const taskStatus = {
  queued: '排队中',
  running: '生成中',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
} as const;

/** 任务运行时可细分为检查依赖或回传，其余直接显示任务状态。 */
export function taskStatusLabel(status: keyof typeof taskStatus, stage: string) {
  if (status === 'running' && stage === 'preflight') return '检查依赖';
  if (status === 'running' && stage === 'uploading') return '回传中';
  return taskStatus[status];
}

/** 排队任务还没被领取的原因，取值由平台 API 定义。 */
export const waitReasons = {
  machine_unassigned: '未分配工作机',
  machine_offline: '等待工作机上线',
  machine_busy: '工作机忙碌，等待领取',
} as const;

/** 把一次执行或作品的参数载入生成表单。`source` 是触发按钮，表单关闭后焦点回到这里。 */
export type ReplayAction = (replay: Replay, source: HTMLElement) => void;
