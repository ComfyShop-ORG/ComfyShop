import type { ComponentPropsWithoutRef, ReactNode } from 'react';
import { AlertDialog, AlertDialogContent } from '@comfyshop/ui';
import { DialogActions } from './dialog-actions';

export function ConfirmationContent({
  title,
  description,
  busy,
  error,
  children,
  ...props
}: Omit<ComponentPropsWithoutRef<typeof AlertDialogContent>, 'title' | 'children'> & {
  title: ReactNode;
  description: ReactNode;
  busy: boolean;
  error: string;
  children: ReactNode;
}) {
  return (
    <AlertDialogContent {...props}>
      <div className="confirm-content">
        <div className="compact-dialog-heading">
          <AlertDialog.Title>{title}</AlertDialog.Title>
        </div>
        <AlertDialog.Description className="form-hint">{description}</AlertDialog.Description>
        <DialogActions alert busy={busy} error={error}>
          {children}
        </DialogActions>
      </div>
    </AlertDialogContent>
  );
}
