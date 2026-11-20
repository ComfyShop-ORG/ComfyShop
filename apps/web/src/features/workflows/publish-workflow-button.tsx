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
  const { busy, error, run } = useAction('发布失败');
  const descriptionId = useId();
  return (
    <Dialog.Root open={open} onOpenChange={(next) => !busy && setOpen(next)}>
      <Dialog.Trigger asChild>
        <Button size="small" variant={continueToWork ? 'primary' : 'secondary'} disabled={disabled}>
          {continueToWork ? '先发布工作流' : '发布工作流'}
        </Button>
      </Dialog.Trigger>
      <DialogContent compact className="publish-dialog" aria-describedby={descriptionId}>
        <div className="compact-dialog-heading">
          <Dialog.Title>发布工作流</Dialog.Title>
          <DialogClose disabled={busy} />
        </div>
        <Dialog.Description id={descriptionId} className="form-hint">
          {continueToWork
            ? '公开工作流后，可以继续发布这次执行的成品。'
            : '发布后，访客可以查看并运行这个工作流。封面取自你公开的作品，可从「我的结果」选择成品发布。'}
        </Dialog.Description>
        {hasSuccess === false && (
          <p className="form-hint publish-requirement" role="status">
            当前版本还没有成功的生成记录。先生成一次，成功后即可发布。
          </p>
        )}
        <form
          className="publish-form"
          onSubmit={(event) => {
            event.preventDefault();
            void run(async () => {
              await workspace.publishWorkflow(workflow.id);
              await queries.invalidateQueries({ queryKey: ['artifacts'] });
              await queries.invalidateQueries({ queryKey: ['works'] });
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
              {busy ? '发布中' : continueToWork ? '发布工作流并继续' : '发布工作流'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog.Root>
  );
}
