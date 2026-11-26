import { useId, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Button, Dialog, DialogClose, DialogContent, Field, Input, Select } from '@comfyshop/ui';
import type { Machine, WorkerType } from '@comfyshop/api-client';
import { t } from '../../app/i18n';
import { useWorkspace } from '../../app/use-workspace';
import { useAction } from '../../components/use-action';

export function ConnectionDialog({
  type,
  machine,
  onClose,
}: {
  type: WorkerType;
  machine?: Machine;
  onClose: () => void;
}) {
  const { api } = useWorkspace();
  const queries = useQueryClient();
  const id = useId();
  const sites = Object.entries(type.sites).map(([value, label]) => ({ value, label }));
  const [scope, setScope] = useState(machine?.worker.scope ?? sites[0]?.value ?? '');
  const [name, setName] = useState(machine?.name ?? '');
  const [key, setKey] = useState('');
  const { busy, error, run } = useAction();
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open && !busy) onClose();
      }}
    >
      <DialogContent size="form">
        <div className="compact-dialog-heading">
          <Dialog.Title>
            {machine ? t('connection.settings') : t('connection.add', type.label)}
          </Dialog.Title>
          <DialogClose disabled={busy} label={t('common.close')} />
        </div>
        <Dialog.Description className="form-hint">
          {t('connection.billing', type.label)}
        </Dialog.Description>
        <form
          className="machine-form"
          onSubmit={(event) => {
            event.preventDefault();
            void run(async () => {
              await api.saveConnection(
                { kind: type.kind, name: name.trim(), scope, apiKey: key.trim() },
                machine?.id,
              );
              setKey('');
              await queries.invalidateQueries({ queryKey: ['machines'] });
              onClose();
            });
          }}
        >
          <Field htmlFor={id + '-name'} label={t('publishWorkDialog.name')}>
            <Input
              id={id + '-name'}
              required
              maxLength={80}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </Field>
          <Field htmlFor={id + '-site'} label={t('connection.site')}>
            <Select
              id={id + '-site'}
              label={t('connection.site')}
              value={scope}
              disabled={busy || !!machine}
              onValueChange={setScope}
              options={sites}
            />
          </Field>
          <Field htmlFor={id + '-key'} label="API Key">
            <Input
              id={id + '-key'}
              name="api-key"
              autoComplete="new-password"
              type="password"
              maxLength={512}
              required
              value={key}
              onChange={(event) => setKey(event.target.value)}
            />
          </Field>
          {machine && <p className="form-hint">{t('connection.replaceKey')}</p>}
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <div className="compact-dialog-footer">
            <Button
              variant="primary"
              type="submit"
              disabled={busy || !key.trim() || !name.trim() || !scope}
            >
              {t('machinesPage.save')}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog.Root>
  );
}
