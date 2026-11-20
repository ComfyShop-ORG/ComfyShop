import { useRef, useState } from 'react';
import { TrashIcon } from '@radix-ui/react-icons';
import { AlertDialog, AlertDialogContent, Button, IconButton } from '@comfyshop/ui';
import { useNotify } from './notify';
import type { NoticeAction } from './notify';

export function DeleteButton<Result>({
  label,
  description,
  disabled,
  done,
  undo,
  onDelete,
  onDeleted,
}: {
  label: string;
  description: string;
  disabled?: boolean;
  /** 删除成功后的提示文字。 */
  done?: string;
  /** 提示条上的撤销操作，接收删除接口的返回值。 */
  undo?: (result: Result) => NoticeAction | undefined;
  onDelete: () => Promise<Result>;
  onDeleted: (result: Result) => void;
}) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const deleted = useRef(false);
  const notify = useNotify();

  async function confirm() {
    if (pending) return;
    setPending(true);
    setError('');
    try {
      const result = await onDelete();
      deleted.current = true;
      setOpen(false);
      onDeleted(result);
      if (done) notify(done, undo?.(result));
    } catch (error) {
      setError(error instanceof Error ? error.message : '删除失败');
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
        setOpen(next);
      }}
    >
      <AlertDialog.Trigger asChild>
        <IconButton label={label} disabled={disabled}>
          <TrashIcon />
        </IconButton>
      </AlertDialog.Trigger>
      <AlertDialogContent
        onCloseAutoFocus={(event) => {
          // 成功后由上层详情或列表恢复焦点，原删除按钮可能已经移除。
          if (deleted.current) event.preventDefault();
        }}
      >
        <div className="confirm-content">
          <div className="compact-dialog-heading">
            <AlertDialog.Title>{label}</AlertDialog.Title>
          </div>
          <AlertDialog.Description className="form-hint">{description}</AlertDialog.Description>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <div className="compact-dialog-footer">
            <AlertDialog.Cancel asChild>
              <Button disabled={pending}>取消</Button>
            </AlertDialog.Cancel>
            <Button variant="danger" disabled={pending} onClick={() => void confirm()}>
              {pending ? '删除中' : '确认删除'}
            </Button>
          </div>
        </div>
      </AlertDialogContent>
    </AlertDialog.Root>
  );
}
