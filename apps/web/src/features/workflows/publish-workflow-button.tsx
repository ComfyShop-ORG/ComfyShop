import { t } from '../../app/i18n.ts';
import { useId, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { Workflow } from '@comfyshop/api-client';
import { Button, Dialog, DialogClose, DialogContent } from '@comfyshop/ui';
import { useWorkspace } from '../../app/use-workspace';
import { useAction } from '../../components/use-action';

export function PublishWorkflowButton({
  workflow,
  continueToWork,
  disabled,
  hasSuccess,
}: {
  workflow: Workflow;
  continueToWork?: () => void;
  disabled?: boolean;
  /** 当前版本是否已有成功的生成记录。未知时不传，由平台在提交时判断。 */
  hasSuccess?: boolean;
}) {
  const { workspace } = useWorkspace();
  const queries = useQueryClient();
  const [open, setOpen] = useState(false);
  const { busy, error, run } = useAction(t('publishWorkDialog.publishingFailed'));
  const descriptionId = useId();
  return (
    <Dialog.Root open={open} onOpenChange={(next) => !busy && setOpen(next)}>
      <Dialog.Trigger asChild>
        <Button size="small" variant={continueToWork ? 'primary' : 'secondary'} disabled={disabled}>
          {continueToWork
            ? t('publishWorkflowButton.publishWorkflowFirst')
            : t('publishWorkflowButton.publishWorkflow')}
        </Button>
      </Dialog.Trigger>
      <DialogContent size="form" aria-describedby={descriptionId}>
        <div className="compact-dialog-heading">
          <Dialog.Title>{t('publishWorkflowButton.publishWorkflow')}</Dialog.Title>
          <DialogClose label={t('common.close')} disabled={busy} />
        </div>
        <Dialog.Description id={descriptionId} className="form-hint">
          {continueToWork
            ? t('publishWorkflowButton.onceTheWorkflowIsPublicYou')
            : t('publishWorkflowButton.visitorsCanViewAndRunThis')}
        </Dialog.Description>
        {hasSuccess === false && (
          <p className="form-hint publish-requirement" role="status">
            {t('publishWorkflowButton.runThisWorkflowVersionSuccessfullyBefore')}
          </p>
        )}
        <form
          className="publish-form"
          onSubmit={(event) => {
            event.preventDefault();
            void run(async () => {
              await workspace.publishWorkflow(workflow.id);
              await queries.invalidateQueries({ queryKey: ['artifacts'] });
              setOpen(false);
              continueToWork?.();
            });
          }}
        >
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <div className="compact-dialog-footer">
            <Button type="submit" variant="primary" disabled={busy || hasSuccess === false}>
              {busy
                ? t('publishWorkDialog.publishing')
                : continueToWork
                  ? t('publishWorkflowButton.publishWorkflowAndContinue')
                  : t('publishWorkflowButton.publishWorkflow')}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog.Root>
  );
}
