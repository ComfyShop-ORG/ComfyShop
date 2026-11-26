/** 排队换机和补跑共用工作机选择弹框。 */
import { useId, useRef, useState } from 'react';
import { Link } from 'react-router';
import { Button, Dialog, DialogContent, Field, Select } from '@comfyshop/ui';
import { t } from '../app/i18n.ts';
import { useMachines, useWorkspace } from '../app/use-workspace';
import { machineOption } from '../data/machine-option';
import { createRequestId } from '../data/request-id';
import { DialogActions } from './dialog-actions';
import { useNotify } from './notify';
import { useAction } from './use-action';

export function TaskQueueActions({
  taskId,
  machineId,
}: {
  taskId: string;
  machineId?: string | null;
}) {
  const { workspace } = useWorkspace();
  return (
    <div className="dialog-heading-actions">
      {machineId && (
        <Button asChild variant="ghost" size="small">
          <Link to={`/machines?${new URLSearchParams({ machine: machineId })}`}>
            {t('taskDetails.viewMachine')}
          </Link>
        </Button>
      )}
      <TaskMachineDialog
        title={t('taskDetails.changeMachine')}
        hint={t('taskDetails.changeMachineHint')}
        failed={t('taskDetails.changeMachineFailed')}
        exclude={machineId ?? undefined}
        confirm={(target) => workspace.changeTaskMachine(taskId, target)}
      />
    </div>
  );
}

export function RetryExecutionsButton({
  taskId,
  machineId,
  service,
  indices,
}: {
  taskId: string;
  machineId?: string | null;
  service: boolean;
  indices: number[];
}) {
  const { workspace, canManageWorkspace } = useWorkspace();
  const notify = useNotify();
  const request = useRef<{ fingerprint: string; key: string }>(null);
  const { busy, error, run } = useAction(t('taskDetails.retryExecutionsFailed'), taskId);
  async function submit(machineId?: string) {
    const fingerprint = JSON.stringify([machineId, indices]);
    if (request.current?.fingerprint !== fingerprint)
      request.current = { fingerprint, key: createRequestId() };
    const execution = { executionIndices: indices, idempotencyKey: request.current.key };
    await workspace.retryExecutions(
      taskId,
      machineId ? { ...execution, machineId } : { ...execution, service: true },
    );
    notify(t('taskDetails.retryExecutionsQueued'));
  }
  if (!canManageWorkspace) return null;
  if (service)
    return (
      <>
        <Button
          size="small"
          variant="secondary"
          disabled={busy}
          onClick={() => void run(() => submit())}
        >
          {t('taskDetails.retryExecutions', indices.length)}
        </Button>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
      </>
    );
  return (
    <TaskMachineDialog
      title={t('taskDetails.retryExecutions', indices.length)}
      hint={t('taskDetails.retryExecutionsHint')}
      failed={t('taskDetails.retryExecutionsFailed')}
      preferred={machineId ?? undefined}
      confirm={submit}
    />
  );
}

function TaskMachineDialog({
  title,
  hint,
  failed,
  exclude,
  preferred,
  confirm,
}: {
  title: string;
  hint: string;
  failed: string;
  exclude?: string;
  preferred?: string;
  confirm: (machineId: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState('');
  const id = useId();
  const machines = useMachines();
  const { busy, error, clearError, run } = useAction(failed);
  const options = (machines.data?.items ?? [])
    .filter(
      (machine) =>
        machine.worker.connection === 'machine' &&
        machine.id !== exclude &&
        machine.online &&
        !machine.revoked,
    )
    .map(machineOption);
  const eligible = options.some(({ value }) => value === target);
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        if (busy) return;
        setOpen(next);
        if (next) {
          setTarget(options.find(({ value }) => value === preferred)?.value ?? '');
          clearError();
        }
      }}
    >
      <Dialog.Trigger asChild>
        <Button variant="ghost" size="small">
          {title}
        </Button>
      </Dialog.Trigger>
      <DialogContent size="form">
        <form
          className="machine-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (eligible && !busy)
              void run(async () => {
                await confirm(target);
                setOpen(false);
              });
          }}
        >
          <div className="compact-dialog-heading">
            <Dialog.Title>{title}</Dialog.Title>
          </div>
          <Dialog.Description className="form-hint">{hint}</Dialog.Description>
          {options.length ? (
            <Field htmlFor={id} label={t('taskDetails.targetMachine')}>
              <Select
                id={id}
                label={t('taskDetails.targetMachine')}
                placeholder={t('runForm.selectAnOnlineWorkMachine')}
                value={target}
                options={options}
                disabled={busy}
                onValueChange={(value) => {
                  setTarget(value);
                  clearError();
                }}
              />
            </Field>
          ) : (
            <p className="form-hint" role="status">
              {machines.error?.message ??
                t(
                  machines.isPending
                    ? 'runForm.loadingWorkMachines'
                    : 'taskDetails.noOtherMachines',
                )}
            </p>
          )}
          <DialogActions busy={busy} error={error}>
            <Button type="submit" variant="primary" disabled={!eligible || busy}>
              {busy ? t('accountDialog.processing') : title}
            </Button>
          </DialogActions>
        </form>
      </DialogContent>
    </Dialog.Root>
  );
}
