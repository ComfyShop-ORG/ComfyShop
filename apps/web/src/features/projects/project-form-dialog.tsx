import { useId, useState } from 'react';
import { Button, Dialog, DialogClose, DialogContent, Field, Input, TextArea } from '@comfyshop/ui';
import type { Project } from '@comfyshop/api-client';
import { t } from '../../app/i18n';
import { useWorkspace } from '../../app/use-workspace';
import { DialogActions } from '../../components/dialog-actions';
import { useAction } from '../../components/use-action';
import { useProjectCache } from './project-queries';

export function ProjectFormDialog({
  project,
  onClose,
  onSaved,
  restoreFocus,
}: {
  project?: Project;
  onClose: () => void;
  onSaved: (project: Project) => void;
  restoreFocus: () => void;
}) {
  const { api } = useWorkspace();
  const cache = useProjectCache();
  const { busy, error, run } = useAction();
  const [name, setName] = useState(project?.name ?? '');
  const [description, setDescription] = useState(project?.description ?? '');
  const id = useId();
  const body = { name: name.trim(), description: description.trim() };
  const unchanged =
    project && body.name === project.name && body.description === project.description;
  const disabled = !body.name || unchanged || busy;
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open && !busy) onClose();
      }}
    >
      <DialogContent
        size="form"
        aria-describedby={undefined}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          restoreFocus();
        }}
        onInteractOutside={(event) => {
          if (busy) event.preventDefault();
        }}
        onEscapeKeyDown={(event) => {
          if (busy) event.preventDefault();
        }}
      >
        <form
          className="project-form"
          onSubmit={(event) => {
            event.preventDefault();
            event.stopPropagation();
            if (disabled) return;
            void run(async () => {
              const saved = project
                ? await api.updateProject(project.id, body)
                : await api.createProject(body);
              void cache.save(saved);
              onSaved(saved);
            });
          }}
        >
          <div className="compact-dialog-heading">
            <Dialog.Title>{t(project ? 'projects.edit' : 'projects.create')}</Dialog.Title>
            <DialogClose label={t('common.close')} disabled={busy} />
          </div>
          <Field label={t('projects.name')} htmlFor={id}>
            <Input
              id={id}
              required
              maxLength={80}
              value={name}
              onChange={(event) => setName(event.target.value)}
              disabled={busy}
            />
          </Field>
          <Field label={t('projects.description')} htmlFor={id + '-description'}>
            <TextArea
              id={id + '-description'}
              rows={3}
              maxLength={480}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              disabled={busy}
            />
          </Field>
          <DialogActions busy={busy} error={error}>
            <Button type="submit" variant="primary" disabled={disabled}>
              {t(project ? 'machinesPage.save' : 'projects.create')}
            </Button>
          </DialogActions>
        </form>
      </DialogContent>
    </Dialog.Root>
  );
}
