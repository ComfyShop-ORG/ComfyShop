import { createContext, useContext } from 'react';

/** 提示条上的附带操作，例如撤销刚才的删除。 */
export type NoticeAction = { label: string; run: () => void | Promise<void> };
export type NotifyFn = (message: string, action?: NoticeAction) => void;

export const Notify = createContext<NotifyFn>(() => {});

/** 在当前弹框或页面显示通知。由应用外壳提供。 */
export function useNotify() {
  return useContext(Notify);
}
