/** 在工作流、任务和媒体弹框中复用标题聚焦与关闭后的焦点恢复。 */
import { useRef } from 'react';

/**
 * @param restoreFocus 关闭后的焦点恢复函数。省略时使用 Radix 的默认行为。
 * @returns 挂在可聚焦弹框标题上的 `titleRef` 和传给弹框内容的 `focusProps`。
 */
export function useDialogFocus(restoreFocus?: () => void) {
  const titleRef = useRef<HTMLHeadingElement>(null);
  return {
    titleRef,
    focusProps: {
      onOpenAutoFocus(event: Event) {
        event.preventDefault();
        titleRef.current?.focus();
      },
      onCloseAutoFocus: restoreFocus
        ? (event: Event) => {
            event.preventDefault();
            restoreFocus();
          }
        : undefined,
    },
  };
}
