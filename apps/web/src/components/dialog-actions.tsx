import type { ReactNode } from 'react';
import { AlertDialog, Button, Dialog } from '@comfyshop/ui';
import { t } from '../app/i18n';

export function DialogActions({
  busy,
  error,
  alert,
  children,
}: {
  busy: boolean;
  error: string;
  alert?: boolean;
  children: ReactNode;
}) {
  const Cancel = alert ? AlertDialog.Cancel : Dialog.Close;
  return (
    <>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="compact-dialog-footer">
        <Cancel asChild>
          <Button disabled={busy}>{t('deleteButton.cancel')}</Button>
        </Cancel>
        {children}
      </div>
    </>
  );
}
