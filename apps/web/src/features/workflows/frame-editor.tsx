import type { ReactNode } from 'react';
import { ArrowLeftIcon, ArrowRightIcon, ResetIcon } from '@radix-ui/react-icons';
import { Button, Dialog, DialogContent, FieldHelp, IconButton } from '@comfyshop/ui';
import { t } from '../../app/i18n';
import { DialogActions } from '../../components/dialog-actions';
import { useDialogFocus } from '../../components/use-dialog-focus';

export function FrameHistoryTools({
  canUndo,
  canRedo,
  navigate,
  reset,
  changed,
}: {
  canUndo: boolean;
  canRedo: boolean;
  navigate: (delta: number) => void;
  reset: () => void;
  changed: boolean;
}) {
  return (
    <>
      <IconButton
        size="large"
        label={t('outpaint.undo')}
        disabled={!canUndo}
        onClick={() => navigate(-1)}
      >
        <ArrowLeftIcon />
      </IconButton>
      <IconButton
        size="large"
        label={t('outpaint.redo')}
        disabled={!canRedo}
        onClick={() => navigate(1)}
      >
        <ArrowRightIcon />
      </IconButton>
      <IconButton size="large" label={t('outpaint.reset')} disabled={!changed} onClick={reset}>
        <ResetIcon />
      </IconButton>
    </>
  );
}

export function FrameEditor({
  title,
  help,
  toolbar,
  status,
  children,
  onApply,
}: {
  title: string;
  help: string;
  toolbar?: ReactNode;
  status?: ReactNode;
  children: ReactNode;
  onApply?: () => void;
}) {
  const { titleRef, focusProps } = useDialogFocus();
  return (
    <DialogContent className="canvas-editor-dialog" {...focusProps}>
      <div className="canvas-editor-form">
        <div className="compact-dialog-heading canvas-editor-heading">
          <div className="canvas-editor-title">
            <Dialog.Title ref={titleRef} tabIndex={-1}>
              {title}
            </Dialog.Title>
            <FieldHelp
              label={t('common.fieldHelp', title)}
              help={help + ' ' + t('canvasView.help')}
            />
          </div>
          {toolbar}
          <DialogActions busy={false} error="">
            <Button variant="primary" disabled={!onApply} onClick={onApply}>
              {t('runParameterDialog.apply')}
            </Button>
          </DialogActions>
        </div>
        <div className="canvas-editor-body">
          {children}
          {status && <div className="canvas-editor-status">{status}</div>}
        </div>
      </div>
    </DialogContent>
  );
}
