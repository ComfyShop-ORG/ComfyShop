import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Button, Dialog, DialogClose, DialogContent } from '@comfyshop/ui';
import { t } from '../../app/i18n';
import { useWorkspace } from '../../app/use-workspace';
import { DialogActions } from '../../components/dialog-actions';
import { useAction } from '../../components/use-action';
import { ProjectSelect } from './project-select';

export function TaskProjectButton({
  taskId,
  ownerId,
  projectId,
  disabled,
  onChanged,
}: {
  taskId: string;
  ownerId?: string | null;
  projectId?: string | null;
  disabled?: boolean;
  onChanged?: (projectId: string | null) => void;
}) {
  const { api, state, canEditWorkspace, canManageWorkspace } = useWorkspace();
  const queries = useQueryClient();
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const { error, busy, run, clearError } = useAction();
  if (!state.userId || (!canManageWorkspace && (!canEditWorkspace || ownerId !== state.userId)))
    return null;
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        if (busy) return;
        if (next) {
          setSelected(projectId ?? null);
          clearError();
        }
        setOpen(next);
      }}
    >
      <Dialog.Trigger asChild>
        <Button size="small" disabled={disabled}>
          {t('projects.assign')}
        </Button>
      </Dialog.Trigger>
      {open && (
        <DialogContent size="form">
          <form
            className="project-form"
            onSubmit={(event) => {
              event.preventDefault();
              event.stopPropagation();
              if (busy || selected === (projectId ?? null)) return;
              void run(async () => {
                await api.changeTaskProject(taskId, selected);
                setOpen(false);
                onChanged?.(selected);
                void Promise.all(
                  [
                    'tasks',
                    'task-activity',
                    'executions',
                    'execution-detail',
                    'works',
                    'workflow-route-replay',
                    'team-events',
                  ].map((key) => queries.invalidateQueries({ queryKey: [key] })),
                );
              });
            }}
          >
            <div className="compact-dialog-heading">
              <Dialog.Title>{t('projects.assign')}</Dialog.Title>
              <DialogClose label={t('common.close')} disabled={busy} />
            </div>
            <Dialog.Description className="form-hint">
              {t('projects.assignDescription')}
            </Dialog.Description>
            <ProjectSelect value={selected} onChange={setSelected} disabled={busy} />
            <DialogActions error={error} busy={busy}>
              <Button
                type="submit"
                variant="primary"
                disabled={busy || selected === (projectId ?? null)}
              >
                {t('machinesPage.save')}
              </Button>
            </DialogActions>
          </form>
        </DialogContent>
      )}
    </Dialog.Root>
  );
}
