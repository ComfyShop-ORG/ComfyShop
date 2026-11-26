import type { ReactNode } from 'react';
import { AlertDialog, Button } from '@comfyshop/ui';
import { t } from '../app/i18n';
import { ConfirmationContent } from './confirmation-content';

export type ConfirmationAction = {
  label: string;
  prompt: string;
  description: string;
  execute: () => Promise<void>;
  source: HTMLButtonElement | null;
  destructive?: boolean;
};

export function ActionConfirmation({
  action,
  busy,
  error,
  run,
  onClose,
  restoreFocus,
  primaryAction,
}: {
  action?: ConfirmationAction;
  busy: boolean;
  error: string;
  run: (operation: () => Promise<void>) => Promise<void>;
  onClose: () => void;
  restoreFocus: () => void;
  primaryAction?: ReactNode;
}) {
  return (
    <AlertDialog.Root open={!!action} onOpenChange={(open) => !open && !busy && onClose()}>
      {action && (
        <ConfirmationContent
          title={action.prompt}
          description={action.description}
          busy={busy}
          error={error}
          data-inline-notifications=""
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (action.source?.isConnected) action.source.focus();
            else restoreFocus();
          }}
        >
          {primaryAction ?? (
            <Button
              variant={action.destructive ? 'danger' : 'primary'}
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  await action.execute();
                  onClose();
                })
              }
            >
              {busy ? t('accountDialog.processing') : action.label}
            </Button>
          )}
        </ConfirmationContent>
      )}
    </AlertDialog.Root>
  );
}
