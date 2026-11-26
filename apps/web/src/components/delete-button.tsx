import { t } from '../app/i18n.ts';
import { useRef, useState } from 'react';
import { TrashIcon } from '@radix-ui/react-icons';
import { AlertDialog, Button, IconButton } from '@comfyshop/ui';
import { ConfirmationContent } from './confirmation-content';
import { useNotify } from './notify';
import type { NoticeAction } from './notify';

export function DeleteButton<Result>({
  label,
  description,
  disabled,
  triggerClassName,
  done,
  undo,
  standalone,
  onDelete,
  onDeleted,
}: {
  label: string;
  description: string;
  disabled?: boolean;
  triggerClassName?: string;
  /** 删除成功后的提示文字。 */
  done?: string;
  /** 提示条上的撤销操作，接收删除接口的返回值。 */
  undo?: (result: Result) => NoticeAction | undefined;
  standalone?: { onClose: () => void; restoreFocus: () => void };
  onDelete: () => Promise<Result>;
  onDeleted: (result: Result) => void;
}) {
  const [open, setOpen] = useState(!!standalone);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const deleted = useRef(false);
  const notify = useNotify();
  function changeOpen(next: boolean) {
    setOpen(next);
    if (!next) standalone?.onClose();
  }

  async function confirm() {
    if (pending) return;
    setPending(true);
    setError('');
    try {
      const result = await onDelete();
      deleted.current = true;
      changeOpen(false);
      onDeleted(result);
      if (done) notify(done, undo?.(result));
    } catch (error) {
      setError(error instanceof Error ? error.message : t('deleteButton.couldNotDelete'));
    } finally {
      setPending(false);
    }
  }

  return (
    <AlertDialog.Root
      open={open}
      onOpenChange={(next) => {
        if (pending) return;
        if (next) deleted.current = false;
        setError('');
        changeOpen(next);
      }}
    >
      {!standalone && (
        <AlertDialog.Trigger asChild>
          <IconButton label={label} disabled={disabled} className={triggerClassName}>
            <TrashIcon />
          </IconButton>
        </AlertDialog.Trigger>
      )}
      <ConfirmationContent
        title={label}
        description={description}
        busy={pending}
        error={error}
        onCloseAutoFocus={(event) => {
          // 成功后由上层详情或列表恢复焦点，原删除按钮可能已经移除。
          if (deleted.current) event.preventDefault();
          else if (standalone) {
            event.preventDefault();
            standalone.restoreFocus();
          }
        }}
      >
        <Button variant="danger" disabled={pending} onClick={() => void confirm()}>
          {pending ? t('deleteButton.deleting') : t('deleteButton.confirmDeletion')}
        </Button>
      </ConfirmationContent>
    </AlertDialog.Root>
  );
}
