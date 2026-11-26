/** 工作机列表、详情和管理操作。 */
import { t } from '../../app/i18n.ts';
import { useEffect, useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import {
  Link2Icon,
  ChevronRightIcon,
  DotsHorizontalIcon,
  DownloadIcon,
  PlusIcon,
} from '@radix-ui/react-icons';
import {
  AlertDialog,
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  DropdownMenu,
  Field,
  IconButton,
  Input,
} from '@comfyshop/ui';
import { WorkflowImport } from '../workspace/workflow-import';
import { ConnectionDialog } from './connection-dialogs';
import type { Machine, MachineKey, WorkerType } from '@comfyshop/api-client';
import { useMachines, useWorkspace } from '../../app/use-workspace';
import { CollectionStatus } from '../../components/collection-status';
import { ConfirmationContent } from '../../components/confirmation-content';
import { StatusMark } from '../../components/status-mark';
import type { ReplayAction } from '../../domain/types';
import { comfyStatusLabel } from '../../domain/types';
import { MachineDetailsDialog } from './machine-details-dialog';
import { MachineSetup, workerPackage } from './machine-setup';
import { MachineSystemIcon } from './machine-system';
import { machineUpdateLabel } from './machine-update';
import { ListItem, ListPresence } from '../../motion';

const changeCopy = {
  rotate: {
    title: t('machinesPage.resetKey'),
    submit: t('machinesPage.confirmReset'),
    description: t('machinesPage.sOldKeyWillBeRevoked'),
  },
  revoke: {
    title: t('machinesPage.revokeWorkMachine'),
    submit: t('machinesPage.confirmRevocation'),
    description: t('machinesPage.sKeyWillBeRevokedImmediately'),
  },
  delete: {
    title: t('machinesPage.deleteWorkMachine'),
    submit: t('deleteButton.confirmDeletion'),
    description: t('machinesPage.willBeRemovedFromTheList'),
  },
};
type MachineChange = { machine: Machine; kind: keyof typeof changeCopy };
type MachineDialog =
  { kind: 'create' } | { kind: 'rename'; machine: Machine } | { kind: 'setup'; result: MachineKey };

function readinessLabel(machine: Machine) {
  if (machine.revoked || !machine.online) return t('machinesPage.unavailable');
  if (machine.paused) return t('machinesPage.tasksPaused');
  if (machine.update?.status === 'pending' || machine.update?.status === 'updating')
    return machineUpdateLabel(machine.update);
  if (machine.comfyStatus === 'unreachable') return comfyStatusLabel(machine.comfyStatus);
  if (machine.busy) return t('machinesPage.busy');
  return machine.comfyStatus === 'idle'
    ? t('machinesPage.acceptingTasks')
    : comfyStatusLabel(machine.comfyStatus);
}

export default function MachinesPage({ onReplay }: { onReplay: ReplayAction }) {
  const { api, state, workspace, workspaceTeam, canEditWorkspace, canManageWorkspace } =
    useWorkspace();
  const machines = useMachines(true, { live: true });
  const queries = useQueryClient();
  const [search, setSearch] = useSearchParams();
  const [dialog, setDialog] = useState<MachineDialog | null>(null);
  const [connection, setConnection] = useState<{ type: WorkerType; machine?: Machine } | null>(
    null,
  );
  const types = machines.data?.connectionTypes ?? [];
  const [name, setName] = useState('');
  const [selected, setSelected] = useState<{
    id: string;
    name: string;
    source: HTMLButtonElement;
    userId: string | null;
  } | null>(null);
  const [confirmation, setConfirmation] = useState<MachineChange | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const descriptionId = useId();
  const addButton = useRef<HTMLButtonElement>(null);
  const nameInput = useRef<HTMLInputElement>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const menuButtons = useRef(new Map<string, HTMLButtonElement>());
  const returnFocus = useRef<HTMLButtonElement | null>(null);
  const result = dialog?.kind === 'setup' ? dialog.result : null;
  const renaming = dialog?.kind === 'rename' ? dialog.machine : null;
  const linkedId = search.get('machine');
  const linked = machines.data?.items.find(({ id }) => id === linkedId);
  const detail =
    selected?.userId === state.userId && selected
      ? selected
      : linked && { id: linked.id, name: linked.name, source: null };
  function closeDetails() {
    setSelected(null);
    if (linkedId) {
      const next = new URLSearchParams(search);
      next.delete('machine');
      setSearch(next, { replace: true });
    }
  }
  useEffect(() => {
    if (result) title.current?.focus();
  }, [result]);
  async function action<Result>(run: () => Promise<Result>) {
    setBusy(true);
    setError('');
    try {
      const result = await run();
      await queries.invalidateQueries({ queryKey: ['machines'] });
      return { result };
    } catch (error) {
      setError(error instanceof Error ? error.message : t('app.theActionFailed'));
      return null;
    } finally {
      setBusy(false);
    }
  }
  function requestChange(machine: Machine, kind: MachineChange['kind']) {
    returnFocus.current = menuButtons.current.get(machine.id) ?? null;
    setError('');
    setConfirmation({ machine, kind });
  }
  function requestRename(machine: Machine) {
    returnFocus.current = menuButtons.current.get(machine.id) ?? null;
    setError('');
    setName(machine.name);
    setDialog({ kind: 'rename', machine });
  }
  function restoreFocus() {
    (returnFocus.current?.isConnected ? returnFocus.current : addButton.current)?.focus();
  }
  async function confirmChange(change: MachineChange) {
    const outcome = await action(async () => {
      if (change.kind === 'rotate') return api.rotateMachine(change.machine.id);
      if (change.kind === 'delete') await api.deleteMachine(change.machine.id);
      else await api.revokeMachine(change.machine.id);
      return null;
    });
    if (!outcome) return;
    setConfirmation(null);
    if (change.kind === 'delete') {
      returnFocus.current = addButton.current;
      return;
    }
    if (outcome.result) {
      setDialog({ kind: 'setup', result: outcome.result });
    }
    void Promise.all(
      ['tasks', 'task-activity', 'task-progress'].map((key) =>
        queries.invalidateQueries({ queryKey: [key] }),
      ),
    );
  }
  async function saveName() {
    const value = name.trim();
    if (busy || !value || value === renaming?.name) return;
    if (renaming) {
      const outcome = await action(() => api.renameMachine(renaming.id, value));
      if (outcome) {
        setDialog(null);
        void Promise.all([
          queries.invalidateQueries({ queryKey: ['tasks', state.userId] }),
          queries.invalidateQueries({ queryKey: ['task-progress', state.userId] }),
        ]);
      }
    } else {
      await action(async () => {
        setDialog({ kind: 'setup', result: await api.createMachine(value) });
      });
    }
  }
  async function changePause(machine: Machine) {
    await action(async () => {
      await api.setMachinePaused(machine.id, !machine.paused);
      void queries.invalidateQueries({ queryKey: ['task-progress', state.userId] });
    });
  }
  function machineMenu(machine: Machine, actions: ReactNode) {
    if (!canManageWorkspace) return null;
    return (
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <IconButton
            className="machine-actions"
            ref={(button) => {
              if (button) menuButtons.current.set(machine.id, button);
              else menuButtons.current.delete(machine.id);
            }}
            label={t('machinesPage.actionsFor', machine.name)}
          >
            <DotsHorizontalIcon />
          </IconButton>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            className="ui-menu"
            align="end"
            sideOffset={8}
            onCloseAutoFocus={(event) => {
              if (confirmation || renaming) event.preventDefault();
            }}
          >
            <DropdownMenu.Item
              className="ui-menu-item"
              disabled={busy}
              onSelect={() => requestRename(machine)}
            >
              {t('machinesPage.rename')}
            </DropdownMenu.Item>
            {actions}
            <DropdownMenu.Item
              className="ui-menu-item"
              disabled={busy}
              onSelect={() => requestChange(machine, machine.revoked ? 'delete' : 'revoke')}
            >
              {machine.revoked ? changeCopy.delete.title : changeCopy.revoke.title}
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    );
  }
  const confirmationCopy = confirmation && changeCopy[confirmation.kind];
  const setupMachine = result && machines.data?.items.find(({ id }) => id === result.machine.id);
  const available = machines.data?.workerRelease;
  const defaultMachineId = machines.data?.defaultMachineId;
  return (
    <main className="page machines-page">
      <div className="section-heading page-toolbar">
        <div>
          <h1>{t('app.workMachines')}</h1>
          {available && (
            <span className="form-hint">
              {t('machinesPage.latestAvailableVersion', available.version)}
            </span>
          )}
        </div>
        {canManageWorkspace && (
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <Button ref={addButton}>
                <PlusIcon />
                {t('machinesPage.addWorkMachine')}
              </Button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content className="ui-menu" align="end" sideOffset={8}>
                {types.map((type) => (
                  <DropdownMenu.Item
                    className="ui-menu-item"
                    key={type.kind}
                    onSelect={() => setConnection({ type })}
                  >
                    {t('connection.add', type.label)}
                  </DropdownMenu.Item>
                ))}
                <DropdownMenu.Item className="ui-menu-item" asChild>
                  <a href={workerPackage} download>
                    {t('machinesPage.downloadThePackageRunItAnd')}
                  </a>
                </DropdownMenu.Item>
                <DropdownMenu.Item className="ui-menu-item" asChild>
                  <Link to="/machines/link">{t('machineLinkDialog.enterConnectionCode')}</Link>
                </DropdownMenu.Item>
                <DropdownMenu.Item
                  className="ui-menu-item"
                  onSelect={() => {
                    returnFocus.current = addButton.current;
                    setName('');
                    setError('');
                    setDialog({ kind: 'create' });
                  }}
                >
                  {t('machinesPage.addManuallyAndDownloadAConfiguration')}
                </DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        )}
      </div>
      <div className="machine-list">
        <ListPresence>
          {machines.data?.items.map((machine) =>
            machine.worker.connection === 'account' ? (
              <ListItem className="machine-item" key={machine.id}>
                <span className="machine-icon" aria-hidden="true">
                  <Link2Icon />
                </span>
                <div className="machine-identity">
                  <strong className="machine-name">{machine.name}</strong>
                  <span>{machine.worker.label}</span>
                </div>
                <div className="machine-states">
                  <span className="machine-state">
                    <StatusMark tone={machine.revoked ? 'idle' : 'success'} />
                    {machine.revoked
                      ? t('machineDetailsDialog.revoked')
                      : types.find((type) => type.kind === machine.worker.kind)?.sites[
                          machine.worker.scope ?? ''
                        ]}
                  </span>
                  {canEditWorkspace && machine.worker.importsReference && !machine.revoked && (
                    <WorkflowImport machine={machine} />
                  )}
                </div>
                {machineMenu(
                  machine,
                  !machine.revoked && (
                    <DropdownMenu.Item
                      className="ui-menu-item"
                      disabled={busy}
                      onSelect={() => {
                        const type = types.find((type) => type.kind === machine.worker.kind);
                        if (type) setConnection({ type, machine });
                      }}
                    >
                      {t('connection.settings')}
                    </DropdownMenu.Item>
                  ),
                )}
              </ListItem>
            ) : (
              <ListItem className="machine-item" key={machine.id}>
                <MachineSystemIcon system={machine.operatingSystem} />
                <div className="machine-identity">
                  <div className="machine-heading">
                    <Button
                      size="small"
                      variant="ghost"
                      className="text-button machine-name"
                      aria-haspopup="dialog"
                      onClick={(event) =>
                        setSelected({
                          id: machine.id,
                          name: machine.name,
                          source: event.currentTarget,
                          userId: state.userId,
                        })
                      }
                    >
                      <span>{machine.name}</span>
                      <ChevronRightIcon aria-hidden="true" />
                    </Button>
                    {defaultMachineId === machine.id && (
                      <span className="muted">{t('machinesPage.default')}</span>
                    )}
                  </div>
                  <span className="muted">{machine.device || `${machine.keyPrefix}…`}</span>
                  <span className="muted" title={machine.runtime?.build ?? undefined}>
                    {machine.runtime
                      ? t('machinesPage.version', machine.runtime.version)
                      : t('machineDetailsDialog.unknownVersion')}
                    {machine.updateAvailable &&
                      available &&
                      t('machinesPage.updateToAvailable', available.version)}
                    {machine.update?.status === 'failed' && (
                      <span className="form-error" role="status">
                        {' · '}
                        {machineUpdateLabel(machine.update)}
                      </span>
                    )}
                  </span>
                </div>
                <div className="machine-states">
                  <span
                    className="machine-state"
                    role="status"
                    aria-label={t('machinesPage.connectionStatus')}
                  >
                    <StatusMark tone={machine.online ? 'success' : 'idle'} />
                    {machine.revoked
                      ? t('machineDetailsDialog.revoked')
                      : machine.online
                        ? t('machinesPage.online')
                        : machine.lastSeen === null
                          ? t('machinesPage.neverConnected')
                          : t('machinesPage.offline')}
                  </span>
                  <span
                    className={
                      machine.paused && !machine.revoked ? 'machine-state' : 'machine-state muted'
                    }
                    role="status"
                    aria-label={t('machineDetailsDialog.acceptingTasks')}
                  >
                    <StatusMark tone={!machine.revoked && machine.paused ? 'waiting' : 'idle'} />
                    {readinessLabel(machine)}
                  </span>
                </div>
                {machineMenu(
                  machine,
                  <>
                    {!machine.revoked && (
                      <DropdownMenu.Item
                        className="ui-menu-item"
                        disabled={busy}
                        onSelect={() => void changePause(machine)}
                      >
                        {machine.paused
                          ? t('machinesPage.resumeTasks')
                          : t('machinesPage.pauseTasks')}
                      </DropdownMenu.Item>
                    )}
                    {!machine.revoked && defaultMachineId !== machine.id && (
                      <DropdownMenu.Item
                        className="ui-menu-item"
                        disabled={busy}
                        onSelect={() => void action(() => workspace.setDefaultMachine(machine.id))}
                      >
                        {t('machinesPage.setAsDefault')}
                      </DropdownMenu.Item>
                    )}
                    {machine.updateAvailable && (
                      <DropdownMenu.Item
                        className="ui-menu-item"
                        disabled={busy}
                        onSelect={() => void action(() => api.updateMachine(machine.id))}
                      >
                        {t('machinesPage.updateToLatest')}
                      </DropdownMenu.Item>
                    )}
                    <DropdownMenu.Item
                      className="ui-menu-item"
                      disabled={busy}
                      onSelect={() => requestChange(machine, 'rotate')}
                    >
                      {changeCopy.rotate.title}
                    </DropdownMenu.Item>
                  </>,
                )}
              </ListItem>
            ),
          )}
        </ListPresence>
      </div>
      <CollectionStatus
        pending={machines.isPending}
        error={machines.error}
        empty={!machines.data?.items.length}
        retry={() => machines.refetch({ cancelRefetch: false })}
        label={
          workspaceTeam
            ? t('teams.noMachines')
            : types.length
              ? t('connection.empty')
              : t('machinesPage.generationRunsOnYourComfyuiDownload')
        }
        action={
          canManageWorkspace && (
            <Button asChild size="small" variant="primary">
              <a href={workerPackage} download>
                <DownloadIcon />
                {t('machineSetup.downloadWorkMachine')}
              </a>
            </Button>
          )
        }
      />
      {error && !dialog && !confirmation && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {connection && <ConnectionDialog {...connection} onClose={() => setConnection(null)} />}
      <AlertDialog.Root
        open={!!confirmation}
        onOpenChange={(value) => {
          if (!value && !busy) setConfirmation(null);
        }}
      >
        <ConfirmationContent
          title={confirmationCopy?.title}
          description={
            <>
              「{confirmation?.machine.name}」{confirmationCopy?.description}
            </>
          }
          busy={busy}
          error={error}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (!dialog) restoreFocus();
          }}
        >
          <Button
            variant={confirmation?.kind === 'delete' ? 'danger' : 'primary'}
            disabled={busy}
            onClick={() => {
              if (confirmation && !busy) void confirmChange(confirmation);
            }}
          >
            {busy ? t('accountDialog.processing') : confirmationCopy?.submit}
          </Button>
        </ConfirmationContent>
      </AlertDialog.Root>
      <Dialog.Root
        open={!!dialog}
        onOpenChange={(value) => {
          if (!value && !busy) {
            setDialog(null);
            setError('');
          }
        }}
      >
        <DialogContent
          size="form"
          aria-describedby={renaming ? undefined : descriptionId}
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            if (result) title.current?.focus();
            else nameInput.current?.focus();
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            restoreFocus();
          }}
        >
          <div className="compact-dialog-heading">
            <Dialog.Title ref={title} tabIndex={-1}>
              {result
                ? t('machinesPage.installAndConnectWorkMachine')
                : renaming
                  ? t('machinesPage.renameWorkMachine')
                  : t('machinesPage.addWorkMachineManually')}
            </Dialog.Title>
            <DialogClose label={t('common.close')} disabled={busy} />
          </div>
          {!renaming && (
            <Dialog.Description id={descriptionId} className="form-hint">
              {result
                ? t('machinesPage.theConfigurationForContainsItsApi', result.machine.name)
                : t('machinesPage.downloadTheWorkMachineAndIts')}
            </Dialog.Description>
          )}
          {result ? (
            <MachineSetup
              result={result}
              machine={setupMachine ?? result.machine}
              statusUnavailable={machines.isError}
            />
          ) : (
            <form
              className="machine-form"
              onSubmit={(event) => {
                event.preventDefault();
                void saveName();
              }}
            >
              <Field label={t('publishWorkDialog.name')} htmlFor="machine-name">
                <Input
                  ref={nameInput}
                  id="machine-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  maxLength={80}
                  required
                  readOnly={busy}
                  autoComplete="off"
                />
              </Field>
              <div className="compact-dialog-footer">
                <Button
                  type="submit"
                  variant="primary"
                  disabled={busy || !name.trim() || name.trim() === renaming?.name}
                >
                  {renaming
                    ? busy
                      ? t('avatarCropDialog.saving')
                      : t('machinesPage.save')
                    : busy
                      ? t('machinesPage.creating')
                      : t('machinesPage.create')}
                </Button>
              </div>
            </form>
          )}
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
        </DialogContent>
      </Dialog.Root>
      {state.userId && detail && (
        <MachineDetailsDialog
          machineId={detail.id}
          name={detail.name}
          onClose={closeDetails}
          restoreFocus={() =>
            (detail.source?.isConnected ? detail.source : addButton.current)?.focus({
              preventScroll: true,
            })
          }
          onReplay={(replay) => {
            const source = detail.source ?? addButton.current;
            closeDetails();
            if (source) onReplay(replay, source);
          }}
        />
      )}
    </main>
  );
}
