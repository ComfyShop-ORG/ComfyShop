import { t } from '../app/i18n.ts';
import { useId, useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { Cross2Icon } from '@radix-ui/react-icons';
import { Button, IconButton, Toast, VisuallyHidden } from '@comfyshop/ui';
import type { NoticeAction } from './notify';

const dialogSelector = '.ui-dialog[role="dialog"], .ui-dialog[role="alertdialog"]';

/** 等上一层弹框退出后，把通知放进当前弹框的读屏范围和焦点范围。 */
function useNotificationDialog() {
  const [dialog, setDialog] = useState<HTMLElement | null>();
  useLayoutEffect(() => {
    const observer = new MutationObserver(update);
    function update() {
      observer.disconnect();
      observer.observe(document.body, { childList: true });
      // 共享弹框通过 Radix Portal 挂载到 body，最后一层显示在最上方。
      const dialogs = [...document.querySelectorAll<HTMLElement>(dialogSelector)];
      for (const element of dialogs)
        observer.observe(element, {
          attributes: true,
          attributeFilter: ['data-state', 'aria-hidden'],
        });
      const top = dialogs.at(-1);
      if (!top) setDialog(null);
      else if (top.dataset.state === 'open' && top.getAttribute('aria-hidden') !== 'true')
        setDialog(top);
      else setDialog(undefined);
    }
    update();
    return () => observer.disconnect();
  }, []);
  return dialog;
}

function NotificationStatus({ id, message }: { id: number; message?: string }) {
  const status = useRef<HTMLSpanElement>(null);
  useLayoutEffect(() => {
    const region = status.current;
    if (!region) return;
    region.textContent = '';
    if (!message) return;
    // 让读屏先看到空播报区和恢复后的弹框焦点，再更新文字。
    let contentFrame = 0;
    const readyFrame = requestAnimationFrame(() => {
      contentFrame = requestAnimationFrame(() => {
        region.textContent = message;
      });
    });
    return () => {
      cancelAnimationFrame(readyFrame);
      cancelAnimationFrame(contentFrame);
    };
  }, [id, message]);
  // 放在 body 直属层级，让 Radix 保留播报区时仍能隐藏下层弹框。
  return createPortal(
    <VisuallyHidden.Root ref={status} role="status" aria-live="assertive" aria-atomic="true" />,
    document.body,
  );
}

export function NotificationLayer({
  children,
  id,
  open,
  text,
  action,
  placement,
  onAction,
  onClose,
}: {
  children?: ReactNode;
  id: number;
  open: boolean;
  text: string;
  action?: NoticeAction;
  placement: 'top' | 'bottom';
  onAction: (run: NoticeAction['run']) => void;
  onClose: () => void;
}) {
  const dialog = useNotificationDialog();
  const messageId = useId();
  const viewport = useRef<HTMLOListElement>(null);
  // 操作沿用 Radix 的通知，播报统一由页面常驻的状态区域发出。
  const [radixAnnouncer] = useState(() => document.createDocumentFragment());
  const actionHint = action ? t('notification.pressF8ToGoToThe', action.label) : '';
  const message =
    open && dialog !== undefined
      ? [t('notification.notification'), text, actionHint].filter(Boolean).join(' ')
      : undefined;
  const notice = (
    <Toast.Provider
      label={t('notification.notification')}
      duration={2600}
      announcerContainer={radixAnnouncer}
    >
      <Toast.Root
        key={id}
        className="ui-toast"
        open={open}
        duration={action ? Infinity : undefined}
        onOpenChange={(next) => {
          if (next) return;
          // Radix 先将通知内的焦点交还到通知区，再回到仍打开的弹框。
          if (dialog && viewport.current?.contains(document.activeElement))
            dialog.focus({ preventScroll: true });
          onClose();
        }}
      >
        <Toast.Title id={messageId}>{text}</Toast.Title>
        {action && (
          <Toast.Action altText={actionHint} asChild>
            <Button
              size="small"
              aria-describedby={messageId}
              autoFocus={!!dialog}
              onClick={() => onAction(action.run)}
            >
              {action.label}
            </Button>
          </Toast.Action>
        )}
        <Toast.Close asChild>
          <IconButton label={t('notification.dismissNotification')}>
            <Cross2Icon />
          </IconButton>
        </Toast.Close>
      </Toast.Root>
      <Toast.Viewport
        ref={viewport}
        label={t('notification.notifications')}
        className="ui-toast-viewport"
        data-placement={placement}
      />
    </Toast.Provider>
  );
  return (
    <>
      {children}
      <NotificationStatus id={id} message={message} />
      {dialog === null && notice}
      {dialog && createPortal(<div className="ui-dialog-notifications">{notice}</div>, dialog)}
    </>
  );
}
