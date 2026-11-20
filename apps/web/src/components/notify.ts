import { createContext, useContext } from 'react';

/** 提示条上的附带操作，例如撤销刚才的删除。 */
export type NoticeAction = { label: string; run: () => void | Promise<void> };
export type NotifyFn = (message: string, action?: NoticeAction) => void;

export const Notify = createContext<NotifyFn>(() => {});

/** 在页面右下角显示一条短提示。由应用外壳提供，弹框内的组件可以直接使用。 */
export function useNotify() {
  return useContext(Notify);
}
